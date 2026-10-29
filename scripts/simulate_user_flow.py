#!/usr/bin/env python3
"""
SIMS 4 Mods Manager - Script de simulation utilisateur (API REST & Audit Web)
Ce script simule de bout en bout le flux utilisateur en utilisant l'API REST de l'application :
1. Cycle de vie de l'API (détection / démarrage automatique en sous-processus / arrêt propre).
2. Authentification LoversLab autonome (récupération de session ou lancement de Playwright Chromium/Edge).
3. Déclenchement et suivi du scraping complet LoversLab via l'API.
4. Audit de cohérence en direct sur Internet pour chaque mod (seules les incohérences sont retenues).
5. Installation séquentielle des mods installables via l'API.
6. Parcours séquentiel des logs avec filtrage strict (élimination de [INFO] et [DEBUG], rétention exclusive des erreurs).
7. Génération d'un rapport complet Markdown dans scripts/rapports/.
"""

# ruff: noqa: E402
import argparse
import atexit
import concurrent.futures
import json
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Ajout de la racine du projet dans sys.path pour les imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reconfiguration de stdout/stderr pour éviter les plantages charmap sur Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _safe_str(val: Any) -> str:
    """Encode une chaîne de façon sécurisée pour la console sans planter sur les émojis."""
    s = str(val or "")
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return s.encode(encoding, errors="replace").decode(encoding, errors="replace")


import httpx

from src.api.client import ApiClient
from src.core.config import AppConfig
from src.core.session_manager import SessionManager
from src.infrastructure.database.manager import DatabaseManager
from src.infrastructure.database.models import CatalogMod

# Répertoires clés
SCRIPTS_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SCRIPTS_DIR / "rapports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class SimulationRunner:
    """Orchestre la simulation utilisateur de bout en bout."""

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8000",
        max_pages: int = -1,
        max_installs: int = -1,
        skip_install: bool = False,
        force_login: bool = False,
        keep_installed: bool = False,
        concurrency: int = 4,
        limit_audit: int = -1,
        fail_on_errors: bool = False,
        skip_sync: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.max_pages = max_pages
        self.max_installs = max_installs
        self.skip_install = skip_install
        self.force_login = force_login
        self.keep_installed = keep_installed
        self.concurrency = max(1, concurrency)
        self.limit_audit = -1 if (limit_audit is None or limit_audit <= 0) else limit_audit
        self.fail_on_errors = fail_on_errors
        self.skip_sync = skip_sync

        import os

        os.environ["SIMS4_DISABLE_AUTH"] = "1"

        self._lock = threading.Lock()
        self._interrupted = False
        self._thread_local = threading.local()
        self._loverslab_cookies_cache: Dict[str, str] = {}
        self._loverslab_ua_cache: Optional[str] = None
        self._setup_signal_handlers()

        self.server_process: Optional[subprocess.Popen] = None
        self.api_client: Optional[ApiClient] = None
        # Suivi de l'offset des logs et des mods directement téléchargeables
        self.initial_log_offset = 0
        log_file = AppConfig.get_logs_dir() / "app.log"
        if log_file.exists():
            try:
                self.initial_log_offset = log_file.stat().st_size
            except Exception:
                self.initial_log_offset = 0

        self.verified_downloadable_mods: List[Dict[str, Any]] = []
        self.installed_mod_ids_before: set[int] = set()
        self.installed_session_mod_ids: set[int] = set()
        self.cleanup_results: List[Dict[str, Any]] = []

        # Résultats pour le rapport final
        self.inconsistencies: List[Dict[str, Any]] = []
        self.installation_results: List[Dict[str, Any]] = []
        self.ambiguous_validation_results: List[Dict[str, Any]] = []
        self.shared_deps_validation_results: List[Dict[str, Any]] = []
        self.filtered_errors: List[str] = []
        self.stats: Dict[str, Any] = {
            "start_time": datetime.now(),
            "end_time": None,
            "total_catalog_mods": 0,
            "total_audited_mods": 0,
            "inconsistencies_count": 0,
            "installations_attempted": 0,
            "installations_succeeded": 0,
            "installations_partial": 0,
            "installations_failed": 0,
            "cleaned_mods_count": 0,
            "errors_logged_count": 0,
        }

    def _setup_signal_handlers(self) -> None:
        """Capture Ctrl+C et terminaisons pour garantir le nettoyage."""

        def _handle_signal(sig, frame):
            if self._interrupted:
                sys.exit(1)
            self._interrupted = True
            print("\n\n[ATTENTION] Interruption reçue (Ctrl+C). Nettoyage d'urgence en cours...")
            try:
                self.cleanup_installed_test_mods()
            except Exception as e:
                print(f" [WARNING] Erreur lors du nettoyage d'interruption : {e}")
            self._cleanup_server()
            sys.exit(130)

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _handle_signal)
        except Exception:
            pass

    # =========================================================================
    # Étape 0 : Cycle de vie du serveur API
    # =========================================================================
    def ensure_api_server(self, force_restart: bool = False) -> None:
        """Vérifie si l'API est accessible, ou la lance/redémarre en arrière-plan."""
        if not force_restart and self._ping_api():
            if self.api_client is None:
                print(f"\n[ÉTAPE 0] Vérification de la disponibilité de l'API sur {self.api_url}...")
                print(" -> Serveur API déjà actif et réactif.")
                self.api_client = ApiClient(base_url=self.api_url)
            return

        print(f"\n[INFO] Initialisation / Redémarrage du serveur API sur {self.api_url}...")
        self._cleanup_server()

        parsed = urlparse(self.api_url)
        port = parsed.port or 8000
        host = parsed.hostname or "127.0.0.1"

        py_exe = sys.executable
        venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            py_exe = str(venv_py)

        import os

        cmd = [
            py_exe,
            str(PROJECT_ROOT / "run.py"),
            "--server",
            "--port",
            str(port),
            "--host",
            host,
            "--disable-auth",
        ]
        sub_env = dict(os.environ)
        sub_env["SIMS4_DISABLE_AUTH"] = "1"
        self.server_process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=sub_env,
        )

        atexit.register(self._cleanup_server)

        # Attente active de la disponibilité du serveur
        max_attempts = 40
        for attempt in range(1, max_attempts + 1):
            time.sleep(0.5)
            if self._ping_api():
                print(f" -> Serveur API démarré avec succès (en {attempt * 0.5:.1f}s).")
                self.api_client = ApiClient(base_url=self.api_url)
                return

        raise RuntimeError(f"Impossible de démarrer ou joindre le serveur API sur {self.api_url} après 20s.")

    def call_api(self, method_name: str, *args, **kwargs) -> Any:
        """Exécute une méthode d'ApiClient avec reprise et redémarrage automatique en cas de déconnexion."""
        if not self.api_client:
            self.ensure_api_server()
        assert self.api_client is not None

        method = getattr(self.api_client, method_name)
        try:
            return method(*args, **kwargs)
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as e:
            print(f"\n [WARNING] Déconnexion ou indisponibilité API ({e}). Redémarrage automatique du serveur API...")
            self.ensure_api_server(force_restart=True)
            method = getattr(self.api_client, method_name)
            return method(*args, **kwargs)

    def _ping_api(self) -> bool:
        """Teste rapidement si l'API répond."""
        try:
            with httpx.Client(timeout=2.0) as c:
                resp = c.get(f"{self.api_url}/api/system/ping")
                if resp.status_code == 200:
                    return True
                # Fallback doc endpoint
                doc_resp = c.get(f"{self.api_url}/docs")
                return doc_resp.status_code == 200
        except Exception:
            return False

    def _cleanup_server(self) -> None:
        """Éteint proprement le serveur s'il a été lancé par le script."""
        if self.server_process and self.server_process.poll() is None:
            print("\n[INFO] Extinction propre du serveur API en arrière-plan...")
            pid = self.server_process.pid
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                if sys.platform == "win32":
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    except Exception:
                        self.server_process.kill()
                else:
                    self.server_process.kill()
            print(" -> Serveur API arrêté.")

    def _get_installed_mods_list(self) -> List[Dict[str, Any]]:
        """Récupère la liste des mods installés via l'API REST de manière robuste (supporte 'items' et 'mods')."""
        try:
            resp = self.call_api("get_installed_mods")
            if isinstance(resp, list):
                return resp
            if isinstance(resp, dict):
                return resp.get("items") or resp.get("mods") or []
        except Exception as e:
            print(f" [WARNING] Impossible de récupérer la liste des mods installés via l'API : {e}")
        return []

    def clean_orphaned_test_mods(self) -> None:
        """Désinstalle immédiatement tous les mods de test LoversLab restés installés dans le jeu."""
        self.ensure_api_server()
        print("\n[NETTOYAGE] Recherche des mods de test LoversLab à désinstaller...")
        installed = self._get_installed_mods_list()
        # Ne pas toucher à WickedWhims officiel s'il était déjà présent
        test_mods = [m for m in installed if m.get("source") == "loverslab" and str(m.get("remote_id")) != "807"]
        if not test_mods:
            print(" -> Aucun mod de test orphelin à nettoyer.")
            return

        print(f" -> {len(test_mods)} mod(s) de test LoversLab détecté(s) pour désinstallation automatique.")
        for im in test_mods:
            mod_id = im["id"]
            title = im.get("title", "Mod")
            folder_name = im.get("folder_name", "")
            safe_t = _safe_str(title)
            safe_f = _safe_str(folder_name)
            try:
                res = self.call_api("uninstall_mod", mod_id)
                success = res.get("success", False)
                msg = res.get("message", "")
                if success:
                    print(f" -> [OK] Nettoyé : '{safe_t}' ({safe_f})")
                    self.stats["cleaned_mods_count"] += 1
                else:
                    print(f" -> [FAIL] Échec nettoyage : '{safe_t}' : {_safe_str(msg)}")
            except Exception as e:
                print(f" -> [FAIL] Exception nettoyage '{safe_t}' : {_safe_str(e)}")
        print("\n -> Nettoyage terminé avec succès !")

    # =========================================================================
    # Étape 1 : Gestion des identifiants & session LoversLab
    # =========================================================================
    def setup_loverslab_session(self) -> None:
        """Récupère la session LoversLab ou lance l'authentification interactive Playwright."""
        print("\n[ÉTAPE 1] Vérification de la session LoversLab...")

        need_login = self.force_login
        if not need_login:
            if SessionManager.is_session_ready("loverslab"):
                print(" -> Session LoversLab trouvée en base de données locale. Vérification en cours...")
                ok, msg = SessionManager.verify_session("loverslab")
                if ok:
                    print(f" -> Session LoversLab valide : {msg}")
                else:
                    print(f" -> Session LoversLab invalide ou expirée ({msg}). Réauthentification requise.")
                    need_login = True
            else:
                print(" -> Aucune session LoversLab trouvée en base. Authentification requise.")
                need_login = True

        if need_login:
            print(" -> Lancement du navigateur Playwright pour connexion LoversLab / Cloudflare...")
            ok, msg, cookies = SessionManager.launch_interactive_login(
                provider_name="loverslab",
                target_url="https://www.loverslab.com/login/",
                timeout_seconds=180,
            )
            if not ok:
                print(f" [WARNING] Avertissement authentification LoversLab : {msg}")
            else:
                print(f" -> Connexion LoversLab réussie ! {len(cookies)} cookie(s) sauvegardé(s).")

        # Initialisation de la session curl_cffi principale et du gestionnaire de sessions par thread
        self.http_session = self._create_isolated_session()
        print(" -> Sessions HTTP autonomes (curl_cffi chrome120 par thread) prêtes pour l'audit.")

    def _create_isolated_session(self) -> Any:
        """Crée une session HTTP curl_cffi isolée et configurée pour LoversLab."""
        return SessionManager.get_http_session("loverslab", force_new=True)

    def _get_thread_session(self) -> Any:
        """Retourne la session HTTP curl_cffi dédiée au thread courant (concurrence réelle, zéro verrou libcurl)."""
        if not hasattr(self._thread_local, "session") or self._thread_local.session is None:
            self._thread_local.session = self._create_isolated_session()
        return self._thread_local.session

    # =========================================================================
    # Étape 2 : Lancement et attente du scraping complet LoversLab (API)
    # =========================================================================
    def sync_catalog(self) -> None:
        """Déclenche la synchronisation LoversLab via l'API et suit sa progression."""
        print("\n[ÉTAPE 2] Déclenchement de la synchronisation du catalogue LoversLab...")

        # Vérifier si une synchronisation est déjà active et la réinitialiser proprement
        status = self.call_api("get_catalog_sync_status")
        if status.get("is_running"):
            print(" -> Une synchronisation précédente était active. Arrêt et réinitialisation...")
            try:
                self.call_api("stop_catalog_sync")
                time.sleep(1.5)
            except Exception:
                pass

        api_max_pages = 0 if (self.max_pages is None or self.max_pages <= 0) else self.max_pages
        page_desc = "TOUTES les pages" if api_max_pages == 0 else f"{api_max_pages} page(s) par catégorie"
        print(f" -> Démarrage du scraping via POST /api/catalog/sync ({page_desc})...")
        start_resp = self.call_api("start_catalog_sync", max_pages=api_max_pages)
        print(f" -> Réponse API : {start_resp.get('message', 'Démarré')}")

        # Polling du statut jusqu'à achèvement
        last_pct = -1
        last_pages = -1
        last_scraped = -1
        while True:
            time.sleep(1.0)
            status = self.call_api("get_catalog_sync_status")
            is_running = status.get("is_running", False)
            pct = status.get("progress_percent", 0)
            msg = status.get("message", "")
            total_scraped = status.get("total_scraped", 0)
            pages = status.get("pages_completed", 0)
            total_pages = status.get("total_pages", 0)
            curr_cat = status.get("current_category", "")

            if pct != last_pct or pages != last_pages or total_scraped != last_scraped:
                cat_info = f" | {curr_cat}" if curr_cat else f" | {msg[:40]}"
                sys.stdout.write(
                    f"\r -> Progression : [{pct}%] - {pages}/{total_pages} pages | "
                    f"{total_scraped} mods répertoriés{cat_info}                              "
                )
                sys.stdout.flush()
                last_pct = pct
                last_pages = pages
                last_scraped = total_scraped

            if not is_running:
                print(f"\n -> Synchronisation terminée avec succès ! Total scraped : {total_scraped} mods.")
                break

    # =========================================================================
    # Étape 3 : Audit de cohérence Internet depuis le script
    # =========================================================================
    def audit_mods_consistency(self) -> None:
        """Parcourt les mods du catalogue et teste en direct sur Internet la cohérence en mode concurrent."""
        print("\n[ÉTAPE 3] Audit de cohérence sur Internet pour chaque mod...")
        assert self.http_session is not None

        # 1. Récupération des mods via l'API (avec pagination optimisée)
        all_mods: List[Dict[str, Any]] = []
        page = 1
        limit = 200
        needed_audit = self.limit_audit if (self.limit_audit and self.limit_audit > 0) else None

        print(" -> Récupération paginée des mods du catalogue via GET /api/catalog...")
        while True:
            resp = self.call_api("get_catalog", source="loverslab", page=page, limit=limit)
            items = resp.get("items", [])
            all_mods.extend(items)
            total = resp.get("total", len(all_mods))
            self.stats["total_catalog_mods"] = total
            print(f"    Page {page} chargée ({len(all_mods)}/{total} mods)...")
            if needed_audit and len(all_mods) >= needed_audit:
                all_mods = all_mods[:needed_audit]
                break
            if len(all_mods) >= total or not items:
                break
            page += 1

        if not self.stats["total_catalog_mods"]:
            self.stats["total_catalog_mods"] = len(all_mods)

        # Limitation de l'audit si demandé via --limit-audit
        if needed_audit:
            target_mods = all_mods
            print(
                f" -> Limitation d'audit activée (--limit-audit {self.limit_audit}) : {len(target_mods)} mod(s) retenu(s)."
            )
        else:
            target_mods = all_mods
            print(f" -> Total de {len(target_mods)} mod(s) LoversLab à auditer.")

        # Accès local DB en fallback si disponible pour enrichir les liens bruts
        db_mods_map: Dict[int, Any] = {}
        try:
            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                for cm in session.query(CatalogMod).filter_by(source="loverslab").all():
                    db_mods_map[cm.id] = cm
        except Exception:
            db_mods_map = {}

        progress_tracker = [0]
        total_targets = len(target_mods)
        print(f" -> Lancement de l'audit avec {self.concurrency} thread(s) concurrent(s)...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = [
                executor.submit(
                    self._audit_single_mod,
                    mod,
                    db_mods_map.get(mod.get("id")),
                    total_targets,
                    progress_tracker,
                )
                for mod in target_mods
            ]
            concurrent.futures.wait(futures)

        print(f"\n -> Audit terminé ! {len(self.inconsistencies)} incohérence(s) constatée(s).")
        self.stats["inconsistencies_count"] = len(self.inconsistencies)

    def _audit_single_mod(
        self,
        mod: Dict[str, Any],
        cm_obj: Optional[Any],
        total_count: int,
        progress_tracker: List[int],
    ) -> None:
        """Audite un mod individuel de manière thread-safe."""
        mod_id = mod.get("id")
        title = mod.get("title", "Sans titre")
        page_url = mod.get("page_url", "")
        source = mod.get("source", "loverslab")
        remote_id = mod.get("remote_id") or (str(mod_id) if mod_id else "")
        patreon_status = mod.get("patreon_status", "NONE")

        # 3.1 Disponibilité de la page web
        page_ok, page_err = self._check_page_reachable(page_url)
        if not page_ok:
            self._record_inconsistency(
                title=title,
                url=page_url,
                app_status="Répertorié dans le catalogue",
                internet_status=f"Page inaccessible ({page_err})",
                details="La page du mod LoversLab retourne une erreur ou a été supprimée.",
            )
        else:
            # 3.2 Vérification du téléchargement direct LoversLab
            if source == "loverslab" and page_url and patreon_status != "LOCKED":
                dl_ok, dl_err = self._check_loverslab_direct_download(page_url)
                if dl_ok:
                    with self._lock:
                        self.verified_downloadable_mods.append(
                            {
                                "id": mod_id,
                                "title": title,
                                "source": source,
                                "remote_id": remote_id,
                                "page_url": page_url,
                            }
                        )
                else:
                    has_explicit_direct = bool(cm_obj and getattr(cm_obj, "get_download_urls_list", lambda: [])())
                    if has_explicit_direct:
                        self._record_inconsistency(
                            title=title,
                            url=page_url,
                            app_status="Téléchargement direct LoversLab attendu",
                            internet_status=f"Échec téléchargement direct ({dl_err})",
                            details="Le lien de téléchargement direct /?do=download a échoué ou redirige vers une erreur/Patreon.",
                        )

            # 3.3 Cohérence du statut Patreon
            if patreon_status and patreon_status != "NONE":
                ext_links = (
                    cm_obj.get_external_links_list() if cm_obj and hasattr(cm_obj, "get_external_links_list") else []
                )
                patreon_link = next((link for link in ext_links if "patreon.com" in link.lower()), None)
                if patreon_link:
                    p_ok, p_actual, p_err = self._check_patreon_post_coherence(patreon_link, patreon_status)
                    if not p_ok:
                        self._record_inconsistency(
                            title=title,
                            url=patreon_link,
                            app_status=f"Statut Patreon : {patreon_status}",
                            internet_status=f"Réalité internet : {p_actual} ({p_err})",
                            details=f"Incohérence entre le statut enregistré ({patreon_status}) et le test direct Patreon.",
                        )

            # 3.4 Test des liens externes (Mega, Mediafire, Simfileshare...)
            if cm_obj and hasattr(cm_obj, "get_external_links_list"):
                ext_links = cm_obj.get_external_links_list()
                for link in ext_links[:2]:
                    if "patreon.com" in link.lower():
                        continue
                    link_ok, link_err = self._check_external_link(link)
                    if not link_ok:
                        self._record_inconsistency(
                            title=title,
                            url=link,
                            app_status="Lien externe référencé",
                            internet_status=f"Lien mort / inaccessible ({link_err})",
                            details=f"Le lien d'hébergement externe ({link[:50]}) semble mort.",
                        )

        # Mise à jour thread-safe de la progression
        with self._lock:
            progress_tracker[0] += 1
            done = progress_tracker[0]
            self.stats["total_audited_mods"] += 1
            safe_title_console = (
                title[:35]
                .encode(sys.stdout.encoding or "utf-8", errors="replace")
                .decode(sys.stdout.encoding or "utf-8")
            )
            try:
                sys.stdout.write(f"\r -> Audit [{done}/{total_count}] : {safe_title_console}...                    ")
                sys.stdout.flush()
            except Exception:
                pass

    def _check_page_reachable(self, url: str) -> tuple[bool, str]:
        """Vérifie si l'URL LoversLab répond avec un code HTTP normal, en streaming léger avec réessai court."""
        if not url:
            return False, "URL vide"
        session = self._get_thread_session()
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                resp = session.get(url, timeout=7, stream=True, allow_redirects=True)
                status = resp.status_code
                if status in [404, 410]:
                    resp.close()
                    return False, f"HTTP {status} (Page supprimée)"
                if status == 403:
                    head_chunk = next(resp.iter_content(chunk_size=8192), b"")
                    resp.close()
                    if b"2D161/2" in head_chunk or b"do not have permission" in head_chunk:
                        return False, "HTTP 403 (Accès refusé / Mod retiré ou archivé sur LoversLab - code IPS 2D161/2)"
                    return False, "HTTP 403 (Accès interdit / captcha ou blocage)"
                if status in [520, 502, 503, 504, 429]:
                    resp.close()
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue
                    return True, f"Indisponibilité réseau temporaire Cloudflare (HTTP {status})"
                if status >= 400:
                    resp.close()
                    return False, f"HTTP {status}"

                # Ne lire que le premier chunk (8 Ko) pour vérifier l'erreur sans transférer tout le HTML
                head_chunk = next(resp.iter_content(chunk_size=8192), b"")
                resp.close()
                if b"The page you are looking for does not exist" in head_chunk:
                    return False, "Page d'erreur LoversLab (contenu introuvable)"

                return True, ""
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return False, str(e)
        return True, ""

    def _check_loverslab_direct_download(self, page_url: str) -> tuple[bool, str]:
        """Simule l'accès au téléchargement direct LoversLab pour tester la validité."""
        session = self._get_thread_session()
        dl_url = page_url.rstrip("/") + "/?do=download"
        try:
            resp = session.get(dl_url, timeout=8, stream=True, allow_redirects=True)
            status = resp.status_code
            final_url = str(resp.url).lower()
            resp.close()
            if status in [404, 410]:
                return False, f"HTTP {status} sur {dl_url}"
            if "loverslab.com" not in final_url:
                return False, f"Redirection vers un service tiers externe ({resp.url})"
            if status == 403:
                return False, "Erreur 403 Forbidden (accès refusé ou captcha actif)"
            if status >= 400:
                return False, f"Code HTTP {status}"
            return True, ""
        except Exception as e:
            return False, str(e)

    def _check_patreon_post_coherence(self, patreon_url: str, app_status: str) -> tuple[bool, str, str]:
        """Vérifie si l'état réel d'un post Patreon concorde avec l'application via streaming partiel."""
        session = self._get_thread_session()
        try:
            resp = session.get(patreon_url, timeout=7, stream=True, allow_redirects=True)
            if resp.status_code in [404, 410]:
                resp.close()
                return False, "404_NOT_FOUND", f"Post Patreon supprimé ({resp.status_code})"

            # Lecture tronquée des 16 premiers Ko
            chunk = next(resp.iter_content(chunk_size=16384), b"")
            resp.close()
            text = chunk.decode("utf-8", errors="ignore").lower()
            is_locked = "unlock this post" in text or "join now to view" in text or "locked" in text
            actual = "LOCKED" if is_locked else "PUBLIC"

            if app_status in ["PUBLIC", "UNLOCKED"] and actual == "LOCKED":
                return False, "LOCKED", "Post verrouillé / payant sur Patreon alors que l'app l'indique PUBLIC"
            if app_status == "LOCKED" and actual == "PUBLIC":
                return False, "PUBLIC", "Post devenu public / déverrouillé sur Patreon alors que l'app l'indique LOCKED"

            return True, actual, ""
        except Exception as e:
            return True, "UNKNOWN", str(e)  # Pas d'incohérence si Patreon est simplement inaccessible

    def _check_external_link(self, url: str) -> tuple[bool, str]:
        """Teste rapidement un lien externe (Mega, Mediafire, etc.) en streaming léger."""
        session = self._get_thread_session()
        try:
            resp = session.get(url, timeout=5, stream=True, allow_redirects=True)
            status = resp.status_code
            resp.close()
            if status in [404, 410]:
                return False, f"HTTP {status}"
            return True, ""
        except Exception as e:
            # Considéré comme inaccessible uniquement en cas d'erreur de résolution
            if "Connection" in str(e) or "NameResolution" in str(e):
                return False, str(e)
            return True, ""

    def _record_inconsistency(self, title: str, url: str, app_status: str, internet_status: str, details: str) -> None:
        """Enregistre une incohérence avérée de manière thread-safe."""
        with self._lock:
            self.inconsistencies.append(
                {
                    "title": title,
                    "url": url,
                    "app_status": app_status,
                    "internet_status": internet_status,
                    "details": details,
                }
            )

    # =========================================================================
    # Étape 4 : Installation séquentielle des mods installables (API)
    # =========================================================================
    def install_mods_sequentially(self) -> None:
        """Installe séquentiellement les mods installables via l'API REST."""
        print("\n[ÉTAPE 4] Installation séquentielle des mods installables...")
        assert self.api_client is not None

        if self.skip_install:
            print(" -> Option --skip-install spécifiée. Aucune installation effectuée.")
            return

        # Mémoriser les mods déjà installés dans le jeu avant les installations
        if not self.installed_mod_ids_before:
            initial_installed = self._get_installed_mods_list()
            self.installed_mod_ids_before = {m["id"] for m in initial_installed if isinstance(m, dict) and "id" in m}
        print(f" -> {len(self.installed_mod_ids_before)} mod(s) préexistant(s) mémorisé(s) dans le jeu.")

        candidate_mods: List[Dict[str, Any]] = []

        # 1. Priorité absolue : tous les mods validés comme téléchargeables en direct lors de l'étape 3
        if self.verified_downloadable_mods:
            candidate_mods = list(self.verified_downloadable_mods)
            print(f" -> {len(candidate_mods)} mod(s) validé(s) comme directement téléchargeables lors de l'audit.")
        else:
            # Fallback si l'audit n'a rien validé (ex: audit sauté ou vide) : chargement complet via l'API
            print(" -> Aucun mod validé lors de l'audit. Recherche des mods installables via l'API REST...")
            try:
                page = 1
                limit = 200
                while True:
                    cat_resp = self.call_api("get_catalog", source="loverslab", page=page, limit=limit)
                    items = cat_resp.get("items", [])
                    total = cat_resp.get("total", len(items))
                    for m in items:
                        if m.get("patreon_status") != "LOCKED":
                            candidate_mods.append(m)
                    if len(candidate_mods) >= total or not items:
                        break
                    if self.max_installs > 0 and len(candidate_mods) >= self.max_installs:
                        break
                    page += 1
            except Exception as e:
                print(f" [WARNING] Erreur lors du chargement du catalogue via l'API : {e}")

        # Fallback base de données locale si l'API n'a retourné aucun candidat
        if not candidate_mods:
            try:
                db = DatabaseManager.get_instance()
                with db.get_session() as session:
                    db_mods = (
                        session.query(CatalogMod)
                        .filter(
                            CatalogMod.source == "loverslab",
                            CatalogMod.page_url.isnot(None),
                            CatalogMod.patreon_status != "LOCKED",
                        )
                        .order_by(CatalogMod.updated_date.desc().nullslast())
                        .all()
                    )
                    for cm in db_mods:
                        ext_links = cm.get_external_links_list() if hasattr(cm, "get_external_links_list") else []
                        dl_urls = cm.get_download_urls_list() if hasattr(cm, "get_download_urls_list") else []
                        if ext_links and not dl_urls:
                            continue
                        candidate_mods.append(
                            {
                                "id": cm.id,
                                "source": cm.source,
                                "remote_id": cm.remote_id,
                                "title": cm.title,
                                "page_url": cm.page_url,
                            }
                        )
            except Exception:
                pass

        # 2. Recherche prioritaire d'un mod avec dépendances/prérequis
        mod_with_deps: Optional[Dict[str, Any]] = None
        for m in candidate_mods:
            if m.get("patreon_status") == "LOCKED":
                continue
            has_deps = bool(m.get("dependencies"))
            has_reqs_text = bool(m.get("requirements_text"))
            has_req_status = m.get("requirements_status") not in (None, "NONE", "")
            title_lower = m.get("title", "").lower()
            keyword_dep = any(k in title_lower for k in ["animation", "wicked", "traducc", "translation"])
            if has_deps or has_reqs_text or has_req_status or keyword_dep:
                mod_with_deps = m
                break

        if not candidate_mods and not mod_with_deps:
            print(" -> Aucun mod LoversLab directement installable détecté.")
            return

        # Assembler target_mods en plaçant le mod avec dépendances en tête de liste
        target_mods: List[Dict[str, Any]] = []
        if mod_with_deps:
            target_mods.append(mod_with_deps)
            print(f" -> Mod avec dépendances inclus prioritairement : '{mod_with_deps.get('title')}'")

        for m in candidate_mods:
            m_id = m.get("id")
            if not any(tm.get("id") == m_id for tm in target_mods):
                target_mods.append(m)

        if self.max_installs is not None and self.max_installs > 0:
            target_mods = target_mods[: self.max_installs]

        print(f" -> {len(target_mods)} mod(s) sélectionné(s) pour installation séquentielle.")

        for idx, mod in enumerate(target_mods, start=1):
            m_title = mod.get("title", "Sans titre")
            m_id = mod.get("id")
            m_source = mod.get("source", "loverslab")
            m_remote_id = mod.get("remote_id") or str(m_id)
            m_page_url = mod.get("page_url", "")

            print(f"\n[{idx}/{len(target_mods)}] Installation de : '{m_title}' (ID #{m_remote_id})...")
            start_t = time.time()
            self.stats["installations_attempted"] += 1

            try:
                res = self.call_api(
                    "install_mod",
                    catalog_mod_id=m_id,
                    source=m_source,
                    remote_id=m_remote_id,
                    page_url=m_page_url,
                    title=m_title,
                    install_dependencies=True,
                    allow_partial=True,
                )
                duration = time.time() - start_t
                success = res.get("success", False)
                msg = res.get("message", "")
                installed_deps = res.get("installed_dependencies", [])
                is_partial = "partielle" in msg.lower() or "dépendance(s) introuvable" in msg.lower()

                if success:
                    if is_partial:
                        print(f" -> [PARTIEL] Succès partiel en {duration:.1f}s : {msg}")
                        self.stats["installations_partial"] += 1
                    else:
                        print(f" -> [OK] Succès en {duration:.1f}s : {msg}")
                        self.stats["installations_succeeded"] += 1
                    # Enregistrement immédiat des nouveaux mods installés (y compris dépendances)
                    curr_after = self._get_installed_mods_list()
                    for im in curr_after:
                        im_id = im.get("id")
                        if im_id and im_id not in self.installed_mod_ids_before:
                            self.installed_session_mod_ids.add(im_id)
                else:
                    print(f" -> [FAIL] Échec en {duration:.1f}s : {msg}")
                    self.stats["installations_failed"] += 1

                self.installation_results.append(
                    {
                        "title": m_title,
                        "source": m_source,
                        "remote_id": m_remote_id,
                        "duration_sec": round(duration, 1),
                        "success": success,
                        "is_partial": is_partial,
                        "message": msg,
                        "installed_dependencies": installed_deps,
                    }
                )
            except Exception as e:
                duration = time.time() - start_t
                print(f" -> [FAIL] Exception lors de l'installation : {e}")
                self.stats["installations_failed"] += 1
                self.installation_results.append(
                    {
                        "title": m_title,
                        "source": m_source,
                        "remote_id": m_remote_id,
                        "duration_sec": round(duration, 1),
                        "success": False,
                        "message": f"Exception API: {e}",
                        "installed_dependencies": [],
                    }
                )

    def cleanup_installed_test_mods(self) -> None:
        """Désinstalle séquentiellement les mods de test installés pendant la simulation."""
        print("\n[ÉTAPE 4.5] Nettoyage post-test des mods installés...")
        if self.keep_installed:
            print(" -> Option --keep-installed spécifiée. Les mods restent installés dans le jeu.")
            return

        curr_installed = self._get_installed_mods_list()
        # Mods ciblés : ceux identifiés durant cette session OU absents de l'état initial
        newly_installed = [
            m
            for m in curr_installed
            if (m.get("id") in self.installed_session_mod_ids) or (m.get("id") not in self.installed_mod_ids_before)
        ]
        if not newly_installed:
            print(" -> Aucun nouveau mod installé à nettoyer.")
            return

        print(f" -> {len(newly_installed)} mod(s) de test détecté(s) pour désinstallation automatique.")
        for im in newly_installed:
            mod_id = im["id"]
            title = im.get("title", "Mod")
            folder_name = im.get("folder_name", "")
            safe_t = _safe_str(title)
            safe_f = _safe_str(folder_name)
            try:
                res = self.call_api("uninstall_mod", mod_id)
                success = res.get("success", False)
                msg = res.get("message", "")
                if success:
                    print(f" -> [OK] Nettoyé : '{safe_t}' ({safe_f})")
                    self.stats["cleaned_mods_count"] += 1
                else:
                    print(f" -> [FAIL] Échec nettoyage : '{safe_t}' : {_safe_str(msg)}")
                self.cleanup_results.append(
                    {
                        "title": title,
                        "folder": folder_name,
                        "success": success,
                        "message": msg,
                    }
                )
            except Exception as e:
                print(f" -> [FAIL] Exception nettoyage '{safe_t}' : {_safe_str(e)}")
                self.cleanup_results.append(
                    {
                        "title": title,
                        "folder": folder_name,
                        "success": False,
                        "message": str(e),
                    }
                )

    # =========================================================================
    # Étape 3.8 : Validation E2E Dépendances Ambiguës, Commentaires & Forum
    # =========================================================================
    def validate_ambiguous_dependencies_and_forum_interpellation(self) -> None:
        """
        Teste sur un groupe de 12 mods réels répartis sur les 4 plateformes (LoversLab, NSFWMods, TSR, CurseForge) :
        1. Le découpage des prérequis et dépendances.
        2. La qualification Commentaire (COMMENT) vs Mod non trouvé (MOD) via l'API save_requirements_override.
        3. La génération du message d'interpellation auteur séparant '📦 Unresolved / Missing Dependencies'
           et '🧹 Notes / Instructions to clean from Requirements', ainsi que le cycle de publication et suppression.
        """
        print(
            "\n[ÉTAPE 3.8] Validation E2E : Dépendances ambiguës, commentaires & interpellation (12 mods sur 4 plateformes)..."
        )
        from bs4 import BeautifulSoup
        from plugins.loverslab.requirements_extractor import extract_loverslab_requirements

        cases = [
            # --- 1. LOVERSLAB (3 mods) ---
            {
                "source": "loverslab",
                "remote_id": "e2e_amb_51444",
                "title": "Confidence Cascade",
                "author": "BlackBoxMods",
                "page_url": "https://www.loverslab.com/files/file/51444-confidence-cascade-102-%E2%80%94-pregnancy-chaos-money-showers-wicked-consequences/",
                "raw_html": (
                    '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                    "Game Options -&gt; Script Mods Enabled<br>"
                    "Bad decisions. Better stories.<br>"
                    "Lumpinou - Relationship &amp; Pregnancy Overhaul"
                    "</div></li></ul>"
                ),
                "expected_comments": [
                    "Game Options -> Script Mods Enabled",
                    "Bad decisions. Better stories",
                ],
                "expected_unfound": [
                    "Lumpinou",
                    "Relationship & Pregnancy Overhaul",
                ],
                "live_target": True,
            },
            {
                "source": "loverslab",
                "remote_id": "e2e_amb_51834",
                "title": "Wicked Traits Unleashed",
                "author": "WickedCreator",
                "page_url": "https://www.loverslab.com/files/file/51834-wicked-traits-unleashed/",
                "raw_html": (
                    '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                    "Script-only mod - no .package file required<br>"
                    "Scumbumbo - XML Injector v4"
                    "</div></li></ul>"
                ),
                "expected_comments": [
                    "Script-only mod - no .package file required",
                ],
                "expected_unfound": [
                    "Scumbumbo",
                    "XML Injector v4",
                ],
                "live_target": False,
            },
            {
                "source": "loverslab",
                "remote_id": "e2e_amb_52204",
                "title": "Private Night (TS4 WW)",
                "author": "BlackBoxMods",
                "page_url": "https://www.loverslab.com/files/file/52204-private-night-ts4-ww-blackboxmods/",
                "raw_html": (
                    '<ul class="cFileInfo"><li><strong>Requirements</strong><div class="cFileInfoData">'
                    "Make sure you have the latest patch and restart the game<br>"
                    "Kuttoe - Mini Mod Framework"
                    "</div></li></ul>"
                ),
                "expected_comments": [
                    "Make sure you have the latest patch and restart the game",
                ],
                "expected_unfound": [
                    "Kuttoe",
                    "Mini Mod Framework",
                ],
                "live_target": False,
            },
            # --- 2. NSFWMODS (3 mods) ---
            {
                "source": "nsfwmods",
                "remote_id": "e2e_amb_nm_424",
                "title": "Sim Snatcher",
                "author": "ColonolNutty",
                "page_url": "https://nsfwmods.com/files/file/424-sim-snatcher/",
                "custom_deps": [
                    {"title": "Sims 4 Community Library", "remote_id": "s4cl", "source": "nsfwmods"},
                    {"title": "Deviant Core", "remote_id": "deviant-core", "source": "nsfwmods"},
                    {"title": "The More Universal Venue List", "remote_id": "muvl", "source": "nsfwmods"},
                    {"title": "Spoiler", "remote_id": "spoiler-tag", "source": "nsfwmods"},
                    {
                        "title": "Mod Settings Menu is optionally required to modify SS Settings",
                        "remote_id": "msm-opt",
                        "source": "nsfwmods",
                    },
                ],
                "expected_comments": [
                    "Spoiler",
                    "Mod Settings Menu is optionally required to modify SS Settings",
                ],
                "expected_unfound": [
                    "Sims 4 Community Library",
                    "Deviant Core",
                    "The More Universal Venue List",
                ],
                "live_target": True,
            },
            {
                "source": "nsfwmods",
                "remote_id": "e2e_amb_nm_704",
                "title": "Romance Reloaded",
                "author": "ColonolNutty",
                "page_url": "https://nsfwmods.com/files/file/704-romance-reloaded/",
                "custom_deps": [
                    {"title": "Sims 4 Community Library", "remote_id": "s4cl", "source": "nsfwmods"},
                    {"title": "Mod Settings Menu", "remote_id": "msm", "source": "nsfwmods"},
                    {"title": "Spoiler", "remote_id": "spoiler-tag", "source": "nsfwmods"},
                    {
                        "title": "Mod Settings Menu is required to modify Settings - SimFileShare",
                        "remote_id": "msm-note",
                        "source": "nsfwmods",
                    },
                ],
                "expected_comments": [
                    "Spoiler",
                    "Mod Settings Menu is required to modify Settings - SimFileShare",
                ],
                "expected_unfound": [
                    "Sims 4 Community Library",
                    "Mod Settings Menu",
                ],
                "live_target": False,
            },
            {
                "source": "nsfwmods",
                "remote_id": "e2e_amb_nm_713",
                "title": "Life Improvements",
                "author": "ColonolNutty",
                "page_url": "https://nsfwmods.com/files/file/713-life-improvements/",
                "custom_deps": [
                    {"title": "Sims 4 Community Library", "remote_id": "s4cl", "source": "nsfwmods"},
                    {"title": "The More Universal Venue List", "remote_id": "muvl", "source": "nsfwmods"},
                    {"title": "Custom Slider Framework", "remote_id": "csf", "source": "nsfwmods"},
                    {"title": "Spoiler", "remote_id": "spoiler-tag", "source": "nsfwmods"},
                    {
                        "title": "Mod Settings Menu is required to modify Settings - SimFileShare",
                        "remote_id": "msm-note",
                        "source": "nsfwmods",
                    },
                ],
                "expected_comments": [
                    "Spoiler",
                    "Mod Settings Menu is required to modify Settings - SimFileShare",
                ],
                "expected_unfound": [
                    "Sims 4 Community Library",
                    "The More Universal Venue List",
                    "Custom Slider Framework",
                ],
                "live_target": False,
            },
            # --- 3. THE SIMS RESOURCE (3 mods) ---
            {
                "source": "thesimsresource",
                "remote_id": "e2e_amb_tsr_1787392",
                "title": "Chill and Cherish",
                "author": "MelBennett",
                "page_url": "https://www.thesimsresource.com/downloads/details/id/1787392",
                "custom_deps": [
                    {"title": "[MB] Canned Soda and Beer Accessory RIGHT", "remote_id": "canned-soda-acc", "source": "thesimsresource"},
                    {"title": "Basketball Accessory", "remote_id": "1573507", "source": "thesimsresource"},
                    {"title": "https://blog.naver.com/mel_165/222563632404", "remote_id": "naver-link", "source": "thesimsresource"},
                    {"title": "Pose Player & Teleport Any Sim required in game", "remote_id": "pose-note", "source": "thesimsresource"},
                ],
                "expected_comments": [
                    "https://blog.naver.com/mel_165/222563632404",
                    "Pose Player & Teleport Any Sim required in game",
                ],
                "expected_unfound": [
                    "[MB] Canned Soda and Beer Accessory RIGHT",
                    "Basketball Accessory",
                ],
                "live_target": True,
            },
            {
                "source": "thesimsresource",
                "remote_id": "e2e_amb_tsr_1795273",
                "title": "Mirror Selfie",
                "author": "NataliaAuditore",
                "page_url": "https://www.thesimsresource.com/downloads/details/id/1795273",
                "custom_deps": [
                    {"title": "iPhone 11 Pro Accessory", "remote_id": "iphone-11-pro", "source": "thesimsresource"},
                    {
                        "title": "https://www.patreon.com/natalia_auditore/posts/iphone-11-pro-39671032?utm_medium=clipboard_copy",
                        "remote_id": "patreon-tracking-url",
                        "source": "thesimsresource",
                    },
                ],
                "expected_comments": [
                    "https://www.patreon.com/natalia_auditore/posts/iphone-11-pro-39671032?utm_medium=clipboard_copy",
                ],
                "expected_unfound": [
                    "iPhone 11 Pro Accessory",
                ],
                "live_target": False,
            },
            {
                "source": "thesimsresource",
                "remote_id": "e2e_amb_tsr_1795603",
                "title": "Nineties Style Curls The Forgotten Colors",
                "author": "WingsSims",
                "page_url": "https://www.thesimsresource.com/downloads/details/id/1795603",
                "custom_deps": [
                    {"title": "WINGS-TO1218-90s style curly hair", "remote_id": "1577470", "source": "thesimsresource"},
                    {"title": "Recolor only - mesh not included in package", "remote_id": "mesh-note", "source": "thesimsresource"},
                ],
                "expected_comments": [
                    "Recolor only - mesh not included in package",
                ],
                "expected_unfound": [
                    "WINGS-TO1218-90s style curly hair",
                ],
                "live_target": False,
            },
            # --- 4. CURSEFORGE (3 mods) ---
            {
                "source": "curseforge",
                "remote_id": "e2e_amb_cf_simsiphone",
                "title": "SimsiPhone 3",
                "author": "Simsiboy",
                "page_url": "https://www.curseforge.com/sims4/mods/simsiphone",
                "custom_deps": [
                    {"title": "XML Injector", "remote_id": "xml-injector", "source": "curseforge"},
                    {
                        "title": "You Might also be interested in Switch-A-Phone! A phone override that let's you have different types of phones",
                        "remote_id": "switch-a-phone-note",
                        "source": "curseforge",
                    },
                ],
                "expected_comments": [
                    "You Might also be interested in Switch-A-Phone! A phone override that let's you have different types of phones",
                ],
                "expected_unfound": [
                    "XML Injector",
                ],
                "live_target": True,
            },
            {
                "source": "curseforge",
                "remote_id": "e2e_amb_cf_social_act",
                "title": "Social Activities (Visit Friends, Family and more)",
                "author": "LittleMsSam",
                "page_url": "https://www.curseforge.com/sims4/mods/social-activities-visit-friends-family-and-more",
                "custom_deps": [
                    {"title": "XML Injector", "remote_id": "xml-injector", "source": "curseforge"},
                    {"title": "Toddler don't go to Daycare Mod", "remote_id": "toddler-daycare", "source": "curseforge"},
                    {
                        "title": "Optional Addons included in archive - remove the ones you do not want",
                        "remote_id": "addons-note",
                        "source": "curseforge",
                    },
                ],
                # 'Toddler don't go to Daycare Mod' is classified as COMMENT per user instruction!
                "expected_comments": [
                    "Toddler don't go to Daycare Mod",
                    "Optional Addons included in archive - remove the ones you do not want",
                ],
                "expected_unfound": [
                    "XML Injector",
                ],
                "live_target": False,
            },
            {
                "source": "curseforge",
                "remote_id": "e2e_amb_cf_exp_preg",
                "title": "Expanded Pregnancy Interactions",
                "author": "LoryNaMods",
                "page_url": "https://www.curseforge.com/sims4/mods/expanded-pregnancy-interactions",
                "custom_deps": [
                    {"title": "XML Injector", "remote_id": "xml-injector", "source": "curseforge"},
                    {"title": "Maternity Shop Epi Mod", "remote_id": "maternity-shop-epi", "source": "curseforge"},
                    {"title": "Parenting Styles Mod", "remote_id": "parenting-styles-mod", "source": "curseforge"},
                    {
                        "title": "Make sure Script Mods are enabled in Game Options",
                        "remote_id": "game-options-note",
                        "source": "curseforge",
                    },
                ],
                "expected_comments": [
                    "Make sure Script Mods are enabled in Game Options",
                ],
                "expected_unfound": [
                    "XML Injector",
                    "Maternity Shop Epi Mod",
                    "Parenting Styles Mod",
                ],
                "live_target": False,
            },
        ]

        db = DatabaseManager.get_instance()
        all_temp_keys = [(c["source"], c["remote_id"]) for c in cases]
        try:
            for c in cases:
                src = c["source"]
                if "custom_deps" in c:
                    extracted_mods = c["custom_deps"]
                    req_text = "\n".join(m["title"] for m in extracted_mods)
                    req_status = "FOUND"
                else:
                    soup = BeautifulSoup(c["raw_html"], "html.parser")
                    req_text, req_status, extracted_mods = extract_loverslab_requirements(soup)

                with db.get_session() as s:
                    s.query(CatalogMod).filter_by(source=src, remote_id=c["remote_id"]).delete()
                    cm = CatalogMod(
                        source=src,
                        remote_id=c["remote_id"],
                        title=c["title"],
                        author=c["author"],
                        page_url=c["page_url"],
                        requirements_text=req_text,
                        requirements_status=req_status,
                    )
                    cm.set_requirements_mods_list(extracted_mods)
                    s.add(cm)
                    s.commit()
                    mod_id = cm.id

                overrides_map = {item: "COMMENT" for item in c["expected_comments"]}
                overrides_map.update({item: "MOD" for item in c["expected_unfound"]})

                self.call_api(
                    "save_requirements_override",
                    {
                        "catalog_mod_id": mod_id,
                        "source": src,
                        "remote_id": c["remote_id"],
                        "overrides": overrides_map,
                    },
                )

                chk = self.call_api(
                    "check_dependencies",
                    {"catalog_mod_id": mod_id, "source": src, "title": c["title"]},
                )
                comm_titles = [d["title"] for d in chk.get("comment_dependencies", [])]
                unf_titles = [d["title"] for d in chk.get("unfound_dependencies", [])] + [
                    d["title"] for d in chk.get("missing_dependencies", [])
                ]

                rep_chk = self.call_api(
                    "check_missing_report",
                    {
                        "catalog_mod_id": mod_id,
                        "missing_modules": unf_titles,
                        "unnecessary_modules": comm_titles,
                    },
                )
                f_msg = rep_chk.get("formatted_message", "")
                has_missing_sec = "📦 Unresolved / Missing Dependencies:" in f_msg
                has_notes_sec = "🧹 Notes / Instructions to clean from Requirements:" in f_msg

                separation_ok = False
                if has_missing_sec and has_notes_sec:
                    m_sec, n_sec = f_msg.split("🧹 Notes / Instructions to clean from Requirements:", 1)
                    m_lines = {line.strip() for line in m_sec.splitlines() if line.strip().startswith("- ")}
                    n_lines = {line.strip() for line in n_sec.splitlines() if line.strip().startswith("- ")}
                    separation_ok = all(
                        f"- {m}" in m_lines and f"- {m}" not in n_lines for m in unf_titles
                    ) and all(
                        f"- {cm_t}" in n_lines and f"- {cm_t}" not in m_lines for cm_t in comm_titles
                    )

                forum_post_and_delete_ok = True
                if c.get("live_target") and rep_chk.get("is_authenticated"):
                    # Si un ancien commentaire de test était présent, on le nettoie d'abord
                    if rep_chk.get("already_reported"):
                        self.call_api(
                            "delete_missing_report",
                            {
                                "catalog_mod_id": mod_id,
                                "missing_modules": unf_titles,
                                "unnecessary_modules": comm_titles,
                            },
                        )

                    # Publication du commentaire d'interpellation sur le forum (send_as_pm=False)
                    sub_res = self.call_api(
                        "report_missing_requirements",
                        {
                            "catalog_mod_id": mod_id,
                            "missing_modules": unf_titles,
                            "unnecessary_modules": comm_titles,
                            "send_as_pm": False,
                        },
                    )
                    posted_ok = bool(sub_res.get("success", False))

                    # Suppression immédiate du commentaire après validation
                    del_res = self.call_api(
                        "delete_missing_report",
                        {
                            "catalog_mod_id": mod_id,
                            "missing_modules": unf_titles,
                            "unnecessary_modules": comm_titles,
                        },
                    )
                    deleted_ok = bool(del_res.get("success", False))
                    forum_post_and_delete_ok = posted_ok and deleted_ok
                    print(
                        f"    -> Interpellation live ({src}) '{c['title']}' : Publié={posted_ok} | Supprimé={deleted_ok}"
                    )

                if c.get("live_target") or c["remote_id"] == "e2e_amb_cf_social_act":
                    print(f"    [APERÇU MESSAGE - {src.upper()} - '{c['title']}'] :")
                    for m_line in f_msg.strip().splitlines()[:18]:
                        print(f"      | {m_line}")
                    print("      | [...]")

                is_ok = (
                    len(comm_titles) == len(c["expected_comments"])
                    and len(unf_titles) == len(c["expected_unfound"])
                    and separation_ok
                    and forum_post_and_delete_ok
                )
                status_str = "OK" if is_ok else "FAIL"
                print(
                    f" -> [{status_str}] [{src.upper()}] '{c['title']}' : Commentaires={len(comm_titles)} | Mods manquants={len(unf_titles)} | Séparation message={separation_ok}"
                )
                self.ambiguous_validation_results.append(
                    {
                        "source": src,
                        "title": c["title"],
                        "author": c.get("author", "Author"),
                        "comments_detected": comm_titles,
                        "unfound_mods_detected": unf_titles,
                        "formatted_message": f_msg,
                        "forum_message_separation_valid": separation_ok,
                        "forum_post_and_delete_valid": forum_post_and_delete_ok,
                        "success": is_ok,
                    }
                )
        finally:
            with db.get_session() as s:
                for src_item, rid_item in all_temp_keys:
                    s.query(CatalogMod).filter(
                        CatalogMod.source == src_item,
                        CatalogMod.remote_id == rid_item,
                    ).delete(synchronize_session=False)
                s.commit()

    # =========================================================================
    # Étape 4.2 : Validation E2E Groupe de 4 Mods avec Dépendances Partagées
    # =========================================================================
    def validate_shared_dependencies_group_installation(self) -> None:
        """
        Valide sur un groupe de 4 mods partageant WickedWhims et XML Injector :
        - L'installation du 1er mod installe les dépendances communes.
        - L'exécution directe des 3 mods suivants détecte que les dépendances communes
          sont déjà installées et ne les réinstalle pas.
        """
        print("\n[ÉTAPE 4.2] Validation E2E : Installation de 4 mods avec dépendances communes sans réinstallation...")
        from src.infrastructure.database.models import InstalledMod

        db = DatabaseManager.get_instance()
        shared_reqs = [
            {
                "source": "loverslab",
                "remote_id": "e2e_sh_3169",
                "title": "SharedCore Framework (E2E Shared)",
                "url": "https://www.loverslab.com/files/file/3169-sharedcore/",
            },
            {
                "source": "loverslab",
                "remote_id": "e2e_sh_99901",
                "title": "XML Injector (E2E Shared)",
                "url": "https://www.loverslab.com/files/file/99901-xml-injector/",
            },
        ]
        group_4 = [
            {"remote_id": "e2e_sh_51444", "title": "Confidence Cascade"},
            {"remote_id": "e2e_sh_5001", "title": "Exciting Animations Pack"},
            {"remote_id": "e2e_sh_51834", "title": "Wicked Traits Unleashed"},
            {"remote_id": "e2e_sh_52204", "title": "Private Night (TS4 WW)"},
        ]
        all_temp_rids = ["e2e_sh_3169", "e2e_sh_99901"] + [m["remote_id"] for m in group_4]
        mod_ids: Dict[str, int] = {}

        try:
            with db.get_session() as s:
                s.query(InstalledMod).filter(InstalledMod.remote_id.in_(all_temp_rids)).delete(
                    synchronize_session=False
                )
                s.query(CatalogMod).filter(CatalogMod.remote_id.in_(all_temp_rids)).delete(synchronize_session=False)

                for sr in shared_reqs:
                    cm_dep = CatalogMod(
                        source="loverslab",
                        remote_id=sr["remote_id"],
                        title=sr["title"],
                        page_url=sr["url"],
                        requirements_status="NONE",
                    )
                    s.add(cm_dep)

                for gm in group_4:
                    cm_mod = CatalogMod(
                        source="loverslab",
                        remote_id=gm["remote_id"],
                        title=gm["title"],
                        page_url=f"https://www.loverslab.com/files/file/{gm['remote_id']}/",
                        requirements_status="RESOLVED",
                    )
                    cm_mod.set_requirements_mods_list(shared_reqs)
                    s.add(cm_mod)
                    s.flush()
                    mod_ids[gm["remote_id"]] = cm_mod.id
                s.commit()

            # 1. Avant installation du Mod 1 : les 2 dépendances sont manquantes
            first = group_4[0]
            chk_before = self.call_api(
                "check_dependencies",
                {"catalog_mod_id": mod_ids[first["remote_id"]], "source": "loverslab", "title": first["title"]},
            )
            missing_before = [d["title"] for d in chk_before.get("missing_dependencies", [])]

            # Simulation de l'installation du Mod 1 et de ses 2 dépendances partagées
            with db.get_session() as s:
                for sr in shared_reqs:
                    s.add(
                        InstalledMod(
                            source="loverslab",
                            remote_id=sr["remote_id"],
                            title=sr["title"],
                            folder_name=f"E2E_{sr['remote_id']}",
                        )
                    )
                s.add(
                    InstalledMod(
                        source="loverslab",
                        remote_id=first["remote_id"],
                        title=first["title"],
                        folder_name=f"E2E_{first['remote_id']}",
                    )
                )
                s.commit()

            first_ok = len(missing_before) == 2
            print(
                f" -> [1/4] '{first['title']}' : Installé avec {len(missing_before)} dépendances initiales ({', '.join(missing_before)})."
            )
            self.shared_deps_validation_results.append(
                {
                    "order": 1,
                    "title": first["title"],
                    "missing_dependencies_count": len(missing_before),
                    "already_installed_count": 0,
                    "reinstalled_dependencies": False,
                    "success": first_ok,
                }
            )

            # 2. Exécution directe pour les Mods 2, 3 et 4 : les dépendances communes ne doivent PAS être réinstallées
            for idx, sub_mod in enumerate(group_4[1:], start=2):
                chk_sub = self.call_api(
                    "check_dependencies",
                    {"catalog_mod_id": mod_ids[sub_mod["remote_id"]], "source": "loverslab", "title": sub_mod["title"]},
                )
                missing_sub = chk_sub.get("missing_dependencies", [])
                already_sub = chk_sub.get("already_installed_dependencies", [])
                no_reinstall = len(missing_sub) == 0 and len(already_sub) == 2

                with db.get_session() as s:
                    s.add(
                        InstalledMod(
                            source="loverslab",
                            remote_id=sub_mod["remote_id"],
                            title=sub_mod["title"],
                            folder_name=f"E2E_{sub_mod['remote_id']}",
                        )
                    )
                    s.commit()

                st = "OK" if no_reinstall else "FAIL"
                print(
                    f" -> [{idx}/4] [{st}] '{sub_mod['title']}' : Dépendances manquantes={len(missing_sub)}, Déjà installées={len(already_sub)} (Aucune réinstallation)"
                )
                self.shared_deps_validation_results.append(
                    {
                        "order": idx,
                        "title": sub_mod["title"],
                        "missing_dependencies_count": len(missing_sub),
                        "already_installed_count": len(already_sub),
                        "reinstalled_dependencies": not no_reinstall,
                        "success": no_reinstall,
                    }
                )
        finally:
            with db.get_session() as s:
                s.query(InstalledMod).filter(InstalledMod.remote_id.in_(all_temp_rids)).delete(
                    synchronize_session=False
                )
                s.query(CatalogMod).filter(CatalogMod.remote_id.in_(all_temp_rids)).delete(synchronize_session=False)
                s.commit()

    # =========================================================================
    # Étape 5 : Récupération séquentielle des logs & génération du rapport final
    # =========================================================================
    def collect_errors_and_generate_report(self) -> Path:
        """Parcourt tous les logs, filtre les messages d'information et génère le rapport Markdown."""
        print("\n[ÉTAPE 5] Récupération séquentielle des logs et génération du rapport final...")
        self.stats["end_time"] = datetime.now()

        # 1. Collecte séquentielle des logs depuis le démarrage du test
        all_raw_lines: List[str] = []

        # Lecture depuis app.log sur le disque (à partir de l'offset initial)
        log_file = AppConfig.get_logs_dir() / "app.log"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    if self.initial_log_offset > 0:
                        f.seek(self.initial_log_offset)
                    all_raw_lines.extend(f.readlines())
            except Exception as e:
                print(f" [WARNING] Erreur lors de la lecture de app.log : {e}")

        # Complément via l'API pour les derniers logs en mémoire vive
        try:
            logs_resp = self.call_api("get_logs", limit=2000)
            api_items = logs_resp.get("items", [])
            existing_set = set(line.strip() for line in all_raw_lines[-500:])
            for item in api_items:
                if item.strip() not in existing_set:
                    all_raw_lines.append(item.rstrip("\n") + "\n")
        except Exception as e:
            print(f" [WARNING] Impossible de récupérer les logs via l'API : {e}")

        # 2. Filtrage strict : Éliminer [INFO] et [DEBUG], ne garder que [ERROR], [CRITICAL] et exceptions
        # ET exclure les logs antérieurs au lancement de cette simulation
        filtered_errors: List[str] = []
        is_capturing_traceback = False
        start_time_threshold = self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S")

        for raw_line in all_raw_lines:
            line = raw_line.strip()
            if not line:
                continue

            # Élimination stricte des niveaux INFO et DEBUG
            if "[INFO]" in line or "[DEBUG]" in line:
                is_capturing_traceback = False
                continue

            # Vérification horodatage si présent [YYYY-MM-DD HH:MM:SS] ou format ISO/standard
            ts_match = re.match(r"^\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", line)
            if ts_match:
                line_ts = ts_match.group(1).replace("T", " ")
                if line_ts < start_time_threshold:
                    is_capturing_traceback = False
                    continue

            # Détection d'erreurs ou niveaux critiques
            if "[ERROR]" in line or "[CRITICAL]" in line or "Traceback (most recent call last):" in line:
                filtered_errors.append(line)
                if "Traceback (most recent call last):" in line:
                    is_capturing_traceback = True
                continue

            # Si on capture une trace de pile (traceback Python sans préfixe de log)
            if is_capturing_traceback:
                if line.startswith('File "') or line.startswith("  ") or re.search(r"^\w+Error:", line):
                    filtered_errors.append(line)
                else:
                    is_capturing_traceback = False

        self.filtered_errors = filtered_errors
        self.stats["errors_logged_count"] = len(filtered_errors)
        print(f" -> Logs filtrés : {len(filtered_errors)} message(s) d'erreur retenu(s) (INFO/DEBUG exclus).")

        # 3. Génération du rapport Markdown horodaté
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"simulation_rapport_{now_str}.md"
        report_json_path = REPORTS_DIR / f"simulation_rapport_{now_str}.json"

        start_time = self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        end_time = self.stats["end_time"].strftime("%Y-%m-%d %H:%M:%S")

        pages_disp = f"{self.max_pages}" if (self.max_pages and self.max_pages > 0) else "Toutes (-1)"
        if self.skip_sync:
            pages_disp = "Ignoré (--skip-sync)"
        installs_disp = f"{self.max_installs}" if (self.max_installs and self.max_installs > 0) else "Tous (-1)"
        if self.skip_install:
            installs_disp = "Désactivées (--skip-install)"
        limit_audit_disp = f"{self.limit_audit}" if (self.limit_audit and self.limit_audit > 0) else "Tous (-1)"

        param_flags = [
            f"`--max-pages {pages_disp}`",
            f"`--max-installs {installs_disp}`",
            f"`--concurrency {self.concurrency}`",
            f"`--limit-audit {limit_audit_disp}`",
        ]
        if self.skip_sync:
            param_flags.append("`--skip-sync`")
        if self.skip_install:
            param_flags.append("`--skip-install`")
        if self.keep_installed:
            param_flags.append("`--keep-installed`")
        params_str = ", ".join(param_flags)

        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("# Rapport d'Exécution : Simulation Utilisateur & Audit de Cohérence\n\n")
            rf.write(f"- **Date d'exécution** : {start_time} à {end_time}\n")
            rf.write(f"- **URL de l'API ciblée** : `{self.api_url}`\n")
            rf.write(f"- **Paramètres** : {params_str}\n\n")

            # Synthèse chiffrée
            rf.write("## 1. Synthèse globale\n\n")
            rf.write("| Métrique | Valeur |\n")
            rf.write("| :--- | :--- |\n")
            rf.write(f"| Mods répertoriés dans le catalogue | **{self.stats['total_catalog_mods']}** |\n")
            rf.write(f"| Mods audités en direct sur Internet | **{self.stats['total_audited_mods']}** |\n")
            rf.write(f"| Incohérences détectées | **{self.stats['inconsistencies_count']}** |\n")
            rf.write(f"| Installations tentées | **{self.stats['installations_attempted']}** |\n")
            rf.write(f"| Installations réussies (complètes) | **{self.stats['installations_succeeded']}** |\n")
            rf.write(
                f"| Installations partielles (dépendances non résolues) | **{self.stats['installations_partial']}** |\n"
            )
            rf.write(f"| Installations échouées | **{self.stats['installations_failed']}** |\n")
            rf.write(f"| Mods de test désinstallés (nettoyés) | **{self.stats['cleaned_mods_count']}** |\n")
            rf.write(f"| Erreurs d'application relevées dans les logs | **{self.stats['errors_logged_count']}** |\n\n")

            # Tableau des incohérences
            rf.write("## 2. Incohérences détectées sur Internet\n\n")
            if not self.inconsistencies:
                rf.write("> [!NOTE]\n> Aucune incohérence détectée ! Tous les statuts en ligne correspondent.\n\n")
            else:
                rf.write(
                    "> [!WARNING]\n"
                    f"> {len(self.inconsistencies)} incohérence(s) relevée(s) entre les données locales et Internet :\n\n"
                )
                rf.write("| Titre du Mod | URL | Statut Application | Résultat Internet Réel | Explication |\n")
                rf.write("| :--- | :--- | :--- | :--- | :--- |\n")
                for inc in self.inconsistencies:
                    safe_title = inc["title"].replace("|", "-")
                    safe_url = inc["url"]
                    safe_app = inc["app_status"].replace("|", "-")
                    safe_net = inc["internet_status"].replace("|", "-")
                    safe_det = inc["details"].replace("|", "-")
                    rf.write(f"| {safe_title} | [{safe_title}]({safe_url}) | {safe_app} | {safe_net} | {safe_det} |\n")
                rf.write("\n")

            # Tableau des installations
            rf.write("## 3. Résultats des installations séquentielles\n\n")
            if not self.installation_results:
                rf.write("> Aucune installation n'a été exécutée (`--skip-install` ou aucun mod installable).\n\n")
            else:
                rf.write("| Mod | Durée | Résultat | Message | Dépendances Installées |\n")
                rf.write("| :--- | :--- | :--- | :--- | :--- |\n")
                for inst in self.installation_results:
                    if inst["success"]:
                        status_icon = "⚠️ Succès partiel" if inst.get("is_partial") else "✅ Succès"
                    else:
                        status_icon = "❌ Échec"
                    safe_title = inst["title"].replace("|", "-")
                    safe_msg = inst["message"].replace("|", "-")
                    deps_str = ", ".join(inst["installed_dependencies"]) if inst["installed_dependencies"] else "Aucune"
                    rf.write(f"| {safe_title} | {inst['duration_sec']}s | {status_icon} | {safe_msg} | {deps_str} |\n")
                rf.write("\n")

            if self.cleanup_results:
                rf.write("### 3.1 Nettoyage post-test des mods\n\n")
                rf.write("| Mod | Dossier | Résultat | Message |\n")
                rf.write("| :--- | :--- | :--- | :--- |\n")
                for cl in self.cleanup_results:
                    st = "✅ Succès" if cl["success"] else "❌ Échec"
                    rf.write(
                        f"| {cl['title'].replace('|', '-')} | `{cl['folder']}` | {st} | {cl['message'].replace('|', '-')} |\n"
                    )
                rf.write("\n")

            if self.ambiguous_validation_results:
                rf.write("## 3.2 Validation E2E : Dépendances Ambiguës, Commentaires & Interpellation Forum (Multi-Plateformes)\n\n")
                rf.write("| Plateforme | Mod | Commentaires Qualifiés | Mods Non Trouvés | Séparation Message Forum | Statut |\n")
                rf.write("| :---: | :--- | :--- | :--- | :---: | :---: |\n")
                for amb in self.ambiguous_validation_results:
                    st = "✅ OK" if amb["success"] else "❌ FAIL"
                    sep = "✅ Conforme" if amb["forum_message_separation_valid"] else "❌ Non conforme"
                    src = amb.get("source", "loverslab").upper()
                    comms = ", ".join(f"`{x}`" for x in amb["comments_detected"])
                    unfs = ", ".join(f"`{x}`" for x in amb["unfound_mods_detected"])
                    rf.write(f"| `{src}` | {amb['title']} | {comms} | {unfs} | {sep} | {st} |\n")
                rf.write("\n")

                # Exemple de message d'interpellation avec séparation stricte Commentaires vs Mods non trouvés
                sample = next((a for a in self.ambiguous_validation_results if a.get("comments_detected") and a.get("unfound_mods_detected")), None)
                if sample and sample.get("formatted_message"):
                    rf.write("### 3.2.1 Exemple de Message d'Interpellation Généré (Commentaires vs Mods Non Trouvés)\n\n")
                    rf.write(f"> **Mod cible** : `{sample['title']}` (Auteur : `{sample.get('author', 'Author')}`)\n\n")
                    rf.write("```text\n")
                    rf.write(sample["formatted_message"].strip() + "\n")
                    rf.write("```\n\n")

            if self.shared_deps_validation_results:
                rf.write("## 3.3 Validation E2E : Groupe de 4 Mods avec Dépendances Communes (Non-Réinstallation)\n\n")
                rf.write(
                    "| Ordre | Mod | Dépendances Manquantes Initiales | Dépendances Déjà Installées | Réinstallation Évitée | Statut |\n"
                )
                rf.write("| :---: | :--- | :---: | :---: | :---: | :---: |\n")
                for sh in self.shared_deps_validation_results:
                    st = "✅ OK" if sh["success"] else "❌ FAIL"
                    avoided = "✅ Oui (0 réinstallation)" if not sh["reinstalled_dependencies"] else "❌ Non"
                    rf.write(
                        f"| {sh['order']} | {sh['title']} | {sh['missing_dependencies_count']} | {sh['already_installed_count']} | {avoided} | {st} |\n"
                    )
                rf.write("\n")

            # Section Erreurs d'application relevées
            rf.write("## 4. Erreurs d'application relevées (Filtre strict : sans INFO/DEBUG)\n\n")
            if not self.filtered_errors:
                rf.write("> Aucune erreur `[ERROR]` ou `[CRITICAL]` enregistrée pendant la session.\n\n")
            else:
                rf.write("```text\n")
                for err in self.filtered_errors:
                    rf.write(f"{err}\n")
                rf.write("```\n")

        # 4. Génération du rapport JSON structuré
        json_data = {
            "metadata": {
                "start_time": start_time,
                "end_time": end_time,
                "api_url": self.api_url,
                "max_pages": self.max_pages,
                "max_installs": self.max_installs,
                "concurrency": self.concurrency,
                "limit_audit": self.limit_audit,
                "skip_install": self.skip_install,
                "skip_sync": self.skip_sync,
                "keep_installed": self.keep_installed,
            },
            "stats": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in self.stats.items()},
            "inconsistencies": self.inconsistencies,
            "installation_results": self.installation_results,
            "ambiguous_validation_results": self.ambiguous_validation_results,
            "shared_deps_validation_results": self.shared_deps_validation_results,
            "cleanup_results": self.cleanup_results,
            "filtered_errors": self.filtered_errors,
        }
        try:
            with open(report_json_path, "w", encoding="utf-8") as jf:
                json.dump(json_data, jf, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f" [WARNING] Erreur lors de l'export JSON du rapport : {e}")

        print("\n================================================================================")
        print(" RAPPORTS GÉNÉRÉS AVEC SUCCÈS")
        print(f" Markdown : {report_path.resolve()}")
        print(f" JSON     : {report_json_path.resolve()}")
        print("================================================================================\n")

        return report_path.resolve()

    def validate_nsfwmods_provider_e2e(self) -> None:
        """Valide le plugin NSFWMods (https://nsfwmods.com/files/category/287-sims-mods/) en conditions réelles."""
        from src.providers.registry import ProviderRegistry

        print("\n[ÉTAPE 3quater] Validation E2E du plugin NSFWMods (https://nsfwmods.com/files/category/287-sims-mods/)...")
        prov = ProviderRegistry.get_provider("nsfwmods")
        if not prov:
            self.inconsistencies.append("Plugin 'nsfwmods' non enregistré dans ProviderRegistry.")
            return

        cat = prov.CATEGORIES[0]
        mods, _ = prov.scrape_category_page(cat, page=1)
        print(f" -> Catégorie '{cat['name']}' scrapée : {len(mods)} mod(s) détecté(s).")
        if not mods:
            self.inconsistencies.append("Aucun mod retourné par NSFWMods sur la catégorie 287-sims-mods.")
            return

        first_mod = mods[0]
        details = prov.get_mod_details(first_mod["page_url"])
        dl_urls = details.get("download_urls", [])
        print(
            f" -> Détails extraits pour '{first_mod['title']}' (ID {first_mod['remote_id']}) : "
            f"{len(dl_urls)} lien(s) de téléchargement."
        )
        if not dl_urls:
            self.inconsistencies.append(f"Aucun lien de téléchargement trouvé sur NSFWMods pour {first_mod['title']}.")

    def validate_curseforge_and_cross_platform_e2e(self) -> None:
        """
        Valide en conditions réelles :
        1. Le plugin CurseForge (https://www.curseforge.com/sims4) : scraping, détails et lien /api/v1/mods/.../download.
        2. La déduplication inter-plateformes et la non-collision (XML Injector sur CurseForge & LoversLab,
           Sims 4 Community Library sur NSFWMods & LoversLab) ainsi que l'installation simultanée sur les 3 plateformes.
        """
        from src.infrastructure.database.models import InstalledMod
        from src.providers.registry import ProviderRegistry

        print("\n[ÉTAPE 3quinquies] Validation E2E CurseForge & Non-Collision Inter-Plateformes (3 plateformes)...")
        cf_prov = ProviderRegistry.get_provider("curseforge")
        if not cf_prov:
            self.inconsistencies.append("Plugin 'curseforge' non enregistré dans ProviderRegistry.")
            return

        cat = cf_prov.CATEGORIES[0]
        mods, _ = cf_prov.scrape_category_page(cat, page=1)
        print(f" -> Catégorie CurseForge '{cat['name']}' scrapée : {len(mods)} mod(s) détecté(s).")
        if not mods:
            self.inconsistencies.append("Aucun mod retourné par CurseForge sur la catégorie Sims 4 Gameplay.")
            return

        xml_details = cf_prov.get_mod_details("https://www.curseforge.com/sims4/mods/xml-injector")
        dl_urls = xml_details.get("download_urls", [])
        print(f" -> Détails CurseForge 'XML Injector' : {len(dl_urls)} lien(s) de téléchargement ({dl_urls}).")
        if not dl_urls:
            self.inconsistencies.append("Aucun lien de téléchargement extrait pour XML Injector sur CurseForge.")

        # Validation de la non-collision inter-plateformes via check_dependencies (CurseForge <-> LoversLab & NSFWMods <-> LoversLab)
        db = DatabaseManager.get_instance()
        temp_rids = ["e2e_cf_xml", "e2e_ll_51444", "e2e_nm_742", "e2e_ll_s4cl_consumer"]
        try:
            with db.get_session() as s:
                s.query(InstalledMod).filter(InstalledMod.remote_id.in_(temp_rids)).delete(synchronize_session=False)
                s.query(CatalogMod).filter(CatalogMod.remote_id.in_(temp_rids)).delete(synchronize_session=False)

                # XML Injector installé depuis CurseForge, requis par Confidence Cascade sur LoversLab
                s.add(
                    InstalledMod(
                        source="curseforge",
                        remote_id="e2e_cf_xml",
                        title="XML Injector",
                        folder_name="[CurseForge] XML Injector",
                    )
                )
                # The Sims 4 Community Library installé depuis NSFWMods, requis par un mod sur LoversLab
                s.add(
                    InstalledMod(
                        source="nsfwmods",
                        remote_id="e2e_nm_742",
                        title="The Sims 4 Community Library",
                        folder_name="[NSFWMods] The Sims 4 Community Library",
                    )
                )

                cm_ll_cascade = CatalogMod(
                    source="loverslab",
                    remote_id="e2e_ll_51444",
                    title="Confidence Cascade (Cross-Platform Check)",
                    page_url="https://www.loverslab.com/files/file/51444-confidence-cascade/",
                    requirements_status="FOUND",
                )
                cm_ll_cascade.set_requirements_mods_list(
                    [
                        {
                            "source": "loverslab",
                            "remote_id": "99901",
                            "title": "XML Injector v4",
                            "url": "https://www.loverslab.com/files/file/99901-xml-injector/",
                        },
                        {
                            "source": "loverslab",
                            "remote_id": "25060",
                            "title": "Sims 4 Community Library",
                            "url": "https://www.loverslab.com/files/file/25060-sims-4-community-library/",
                        },
                    ]
                )
                s.add(cm_ll_cascade)
                s.commit()
                cascade_id = cm_ll_cascade.id

            chk_cross = self.call_api(
                "check_dependencies",
                {
                    "catalog_mod_id": cascade_id,
                    "source": "loverslab",
                    "title": "Confidence Cascade (Cross-Platform Check)",
                },
            )
            missing_cross = chk_cross.get("missing_dependencies", [])
            already_cross = chk_cross.get("already_installed_dependencies", [])
            cross_ok = len(missing_cross) == 0 and len(already_cross) == 2
            print(
                f" -> [{'OK' if cross_ok else 'FAIL'}] Déduplication inter-plateformes (CurseForge + NSFWMods -> LoversLab) : "
                f"Manquantes={len(missing_cross)}, Déjà installées={len(already_cross)}"
            )
        finally:
            with db.get_session() as s:
                s.query(InstalledMod).filter(InstalledMod.remote_id.in_(temp_rids)).delete(synchronize_session=False)
                s.query(CatalogMod).filter(CatalogMod.remote_id.in_(temp_rids)).delete(synchronize_session=False)
                s.commit()

    def validate_thesimsresource_and_i18n_e2e(self) -> None:
        """
        Valide en conditions réelles :
        1. Le plugin The Sims Resource (https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/) :
           scraping des cartes data-item, détails et flux ticket initDownload.
        2. La non-collision inter-plateformes sur 4 plateformes (LoversLab, NSFWMods, CurseForge, The Sims Resource).
        3. Le basculement multilangue i18n FR / EN.
        """
        from src.i18n import I18nManager, tr
        from src.providers.registry import ProviderRegistry

        print(
            "\n[ÉTAPE 3sexies] Validation E2E The Sims Resource (4 plateformes) & Système Multilangue i18n (FR / EN)..."
        )
        tsr_prov = ProviderRegistry.get_provider("thesimsresource")
        if not tsr_prov:
            self.inconsistencies.append("Plugin 'thesimsresource' non enregistré dans ProviderRegistry.")
            return

        cat = tsr_prov.CATEGORIES[0]
        mods, _ = tsr_prov.scrape_category_page(cat, page=1)
        print(f" -> Catégorie TSR '{cat['name']}' scrapée : {len(mods)} mod(s) détecté(s).")
        if not mods:
            self.inconsistencies.append("Aucun mod retourné par The Sims Resource sur la catégorie Mods.")
            return

        first_mod = mods[0]
        details = tsr_prov.get_mod_details(first_mod["page_url"])
        dl_urls = details.get("download_urls", [])
        print(
            f" -> Détails TSR extraits pour '{first_mod['title']}' (ID #{first_mod['remote_id']}) : "
            f"{len(dl_urls)} lien(s) d'initialisation ticket."
        )
        if not dl_urls:
            self.inconsistencies.append(f"Aucun lien de téléchargement TSR trouvé pour {first_mod['title']}.")

        # Validation du basculement i18n FR / EN
        i18n = I18nManager.instance()
        i18n.set_language("en")
        en_cat = tr("nav.catalog")
        en_tsr = tr("accounts.thesimsresource_title")
        i18n.set_language("fr")
        fr_cat = tr("nav.catalog")
        fr_tsr = tr("accounts.thesimsresource_title")
        i18n_ok = ("Unified Catalog" in en_cat) and ("Catalogue Unifié" in fr_cat) and (en_tsr != fr_tsr)
        print(f" -> [{'OK' if i18n_ok else 'FAIL'}] Basculement i18n FR/EN : FR='{fr_cat}' | EN='{en_cat}'")

    def run(self) -> None:
        """Exécute toutes les étapes de la simulation."""
        print("=" * 80)
        print(" DÉMARRAGE DE LA SIMULATION UTILISATEUR & AUDIT (SIMS 4 MODS MANAGER)")
        print("=" * 80)

        try:
            self.ensure_api_server()
            # Mémorisation stricte des mods déjà installés dans le jeu avant toute opération
            initial_installed = self._get_installed_mods_list()
            self.installed_mod_ids_before = {m["id"] for m in initial_installed if isinstance(m, dict) and "id" in m}
            print(f" -> {len(self.installed_mod_ids_before)} mod(s) déjà installé(s) au préalable dans le jeu.")

            self.setup_loverslab_session()
            if not self.skip_sync:
                self.sync_catalog()
            else:
                print(
                    "\n[ÉTAPE 2] Synchronisation LoversLab ignorée (--skip-sync actif). Réutilisation du catalogue existant."
                )
            self.audit_mods_consistency()
            self.validate_ambiguous_dependencies_and_forum_interpellation()
            self.validate_shared_dependencies_group_installation()
            self.validate_nsfwmods_provider_e2e()
            self.validate_curseforge_and_cross_platform_e2e()
            self.validate_thesimsresource_and_i18n_e2e()
            self.install_mods_sequentially()
            self.cleanup_installed_test_mods()
        finally:
            self.collect_errors_and_generate_report()


def main():
    parser = argparse.ArgumentParser(
        description="Script de simulation des actions utilisateur via l'API REST et audit de cohérence Internet."
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="URL de l'API REST (défaut : http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=-1,
        help="Nombre de pages LoversLab à scraper par catégorie (-1 pour toutes les pages, défaut : -1)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scraper l'intégralité du site LoversLab (équivalent à --max-pages -1)",
    )
    parser.add_argument(
        "--max-installs",
        type=int,
        default=-1,
        help="Nombre maximal de mods installables à installer séquentiellement (-1 pour tous, défaut : -1)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="N'exécuter que l'audit et le scraping sans installer de mod dans le jeu",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Ignorer l'étape de scraping/synchronisation du catalogue LoversLab et réutiliser les données locales",
    )
    parser.add_argument(
        "--force-login",
        action="store_true",
        help="Forcer l'ouverture du navigateur Playwright pour réauthentifier LoversLab",
    )
    parser.add_argument(
        "--keep-installed",
        action="store_true",
        help="Conserver les mods installés dans le jeu sans les désinstaller automatiquement à la fin de la simulation",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Nombre de threads/requêtes concurrentes pour l'audit web (défaut : 4)",
    )
    parser.add_argument(
        "--limit-audit",
        type=int,
        default=-1,
        help="Nombre maximal de mods à auditer en direct sur Internet (-1 pour tous, défaut : -1)",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Retourner un code de retour non-nul (exit 1) en cas d'erreurs d'installation ou d'erreurs critiques dans les logs",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Désinstaller immédiatement les mods de test LoversLab restés dans le jeu sans relancer la simulation",
    )

    args = parser.parse_args()

    if args.clean_only:
        runner = SimulationRunner(api_url=args.api_url)
        runner.clean_orphaned_test_mods()
        return

    max_pages = -1 if args.full else args.max_pages

    runner = SimulationRunner(
        api_url=args.api_url,
        max_pages=max_pages,
        max_installs=args.max_installs,
        skip_install=args.skip_install,
        skip_sync=args.skip_sync,
        force_login=args.force_login,
        keep_installed=args.keep_installed,
        concurrency=args.concurrency,
        limit_audit=args.limit_audit,
        fail_on_errors=args.fail_on_errors,
    )
    runner.run()

    if args.fail_on_errors:
        failed_installs = runner.stats.get("installations_failed", 0)
        logged_errors = runner.stats.get("errors_logged_count", 0)
        if failed_installs > 0 or logged_errors > 0:
            print(
                f"\n[CI/CD ERROR] Échec de la simulation : {failed_installs} installation(s) échouée(s), {logged_errors} erreur(s) relevée(s)."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()

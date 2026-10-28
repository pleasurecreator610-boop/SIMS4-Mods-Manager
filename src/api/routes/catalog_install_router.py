"""Endpoints pour l'installation des mods du catalogue, streaming de progression et vignettes."""

from __future__ import annotations

import ipaddress
import json
import queue
import re
import socket
import urllib.parse
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse

from src.api.deps import get_catalog_repo
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.api.schemas.catalog import (
    CatalogInstallRequest,
    CatalogInstallResponse,
    DependenciesCheckResponse,
)
from src.core.concurrency.thread_pool_manager import ThreadPoolManager
from src.core.config import AppConfig
from src.core.session_manager import SessionManager
from src.infrastructure.database.manager import DatabaseManager
from src.application.catalog.catalog_sync_service import check_catalog_dependencies
from src.application.mods.mod_installer_service import perform_mod_install
from src.utils.logger import logger

install_router = APIRouter(tags=["Catalog Installation"])

MAX_THUMBNAIL_BYTES: int = 10 * 1024 * 1024  # 10 Mio max


def _is_forbidden_ip(ip_str: str) -> bool:
    """Vérifie si une adresse IP est privée, loopback, link-local, multicast ou réservée."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return bool(
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        )
    except ValueError:
        return False


def _validate_safe_thumbnail_url(url: str) -> None:
    """Valide une URL de vignette contre les attaques SSRF (CWE-918)."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Schéma d'URL non autorisé pour la vignette.")

    hostname = (parsed.hostname or "").strip().lower()
    if (
        not hostname
        or hostname in {"localhost", "localhost.localdomain", "ip6-localhost"}
        or hostname.endswith((".local", ".internal"))
    ):
        raise HTTPException(status_code=400, detail="Hôte local ou interne interdit (protection SSRF).")

    if _is_forbidden_ip(hostname):
        raise HTTPException(status_code=400, detail="Adresse IP privée ou loopback interdite (protection SSRF).")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
        for info in addr_infos:
            resolved_ip = str(info[4][0])
            if _is_forbidden_ip(resolved_ip):
                raise HTTPException(
                    status_code=400,
                    detail="Résolution DNS vers une adresse IP interne interdite (protection SSRF).",
                )
    except HTTPException:
        raise
    except OSError:
        # En mode hors-ligne / tests unitaires mockés, la résolution DNS peut échouer sans être une IP interne
        pass


@install_router.get("/thumbnail")
def get_thumbnail(source: str, remote_id: str, url: str):
    """Récupère et met en cache l'image vignette d'un mod de manière sécurisée (anti-SSRF & anti-Path Traversal)."""
    if ".." in source or ".." in remote_id or "/" in source or "\\" in source or "/" in remote_id or "\\" in remote_id:
        raise HTTPException(status_code=400, detail="Paramètres source ou remote_id invalides.")

    safe_source = re.sub(r"[^a-zA-Z0-9_-]", "", source)
    safe_remote_id = re.sub(r"[^a-zA-Z0-9_-]", "", remote_id)
    if not safe_source or not safe_remote_id:
        raise HTTPException(status_code=400, detail="Paramètres source ou remote_id vides après nettoyage.")

    _validate_safe_thumbnail_url(url)

    cache_dir = AppConfig.get_thumbnails_cache_dir().resolve()
    dest_path = (cache_dir / f"thumb_{safe_source}_{safe_remote_id}.jpg").resolve()
    if cache_dir not in dest_path.parents:
        raise HTTPException(status_code=400, detail="Chemin de destination hors du cache autorisé.")

    if not dest_path.exists() or dest_path.stat().st_size < 100:
        session = SessionManager.get_http_session(safe_source)
        try:
            resp = session.get(url, timeout=15)
            content = resp.content or b""
            if len(content) > MAX_THUMBNAIL_BYTES:
                raise HTTPException(status_code=413, detail="Image vignette trop volumineuse (> 10 Mio).")
            if resp.status_code == 200 and len(content) > 100:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(content)
            else:
                raise HTTPException(status_code=404, detail="Image introuvable.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Erreur téléchargement image: {e}") from e

    media_type = "image/jpeg"
    try:
        with open(dest_path, "rb") as f:
            header = f.read(12)
        if header.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif header.startswith(b"RIFF") and b"WEBP" in header:
            media_type = "image/webp"
        elif header.startswith(b"GIF8"):
            media_type = "image/gif"
    except (OSError, IOError) as e:
        logger.debug(f"Could not read image header for {dest_path}: {e}")

    return FileResponse(dest_path, media_type=media_type)


@install_router.post("/purge")
def purge_catalog_endpoint():
    """Purge l'intégralité du catalogue pour repartir d'une base saine."""
    db = DatabaseManager.get_instance()
    deleted = db.purge_catalog()
    return {"success": True, "deleted": deleted, "message": f"{deleted} mod(s) supprimé(s) du catalogue."}


@install_router.post("/check-dependencies", response_model=DependenciesCheckResponse)
def check_dependencies(
    payload: CatalogInstallRequest,
    catalog_repo: ICatalogRepository = Depends(get_catalog_repo),
):
    """Analyse l'arbre de dépendances d'un mod avant son installation."""
    cat_mod = None
    if payload.catalog_mod_id:
        cat_mod = catalog_repo.get_by_id(payload.catalog_mod_id)
    elif payload.source and payload.remote_id:
        cat_mod = catalog_repo.get_by_source_and_remote_id(payload.source, payload.remote_id)

    page_url = cat_mod.page_url if cat_mod else payload.page_url
    source = str((cat_mod.source if cat_mod else payload.source) or "loverslab")
    mod_title = str((cat_mod.title if cat_mod else payload.title) or "Mod")

    return check_catalog_dependencies(
        mod_title=mod_title,
        page_url=page_url,
        source=source,
        cat_mod=cat_mod,
    )


@install_router.post("/install", response_model=CatalogInstallResponse)
def install_mod(payload: CatalogInstallRequest):
    """Télécharge et installe un mod via l'orchestrateur."""
    from src.api.routes import catalog_router

    perform_fn = getattr(catalog_router, "_perform_install", perform_mod_install)
    res = perform_fn(payload)
    if not res.success and "introuvable" in res.message:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@install_router.post("/install-stream")
def install_mod_stream(payload: CatalogInstallRequest):
    """Installe un mod en diffusant les événements de progression en flux NDJSON via le ThreadPoolManager."""
    from src.api.routes import catalog_router

    perform_fn = getattr(catalog_router, "_perform_install", perform_mod_install)
    q: queue.Queue = queue.Queue()

    def progress_cb(pct: int, status: str, details: str = ""):
        """Exécute l'opération progress cb.

        Args:
            pct: Paramètre pct.
            status: Paramètre status.
            details: Paramètre details.
        """
        q.put({"type": "progress", "percent": pct, "status": status, "details": details})

    def run_worker():
        """Exécute l'opération run worker."""
        try:
            res = perform_fn(payload, progress_callback=progress_cb)
            q.put({"type": "finished", "success": res.success, "message": res.message})
        except Exception as e:
            q.put({"type": "finished", "success": False, "message": str(e)})
        finally:
            q.put(None)

    # Exécution via le ThreadPoolManager centralisé au lieu d'un thread sauvage
    ThreadPoolManager.get_instance().submit_io(run_worker)

    def event_generator():
        """Exécute l'opération event generator."""
        while True:
            item = q.get()
            if item is None:
                break
            yield json.dumps(item) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

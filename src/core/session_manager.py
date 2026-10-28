import asyncio
import shutil
import threading
from datetime import datetime
from typing import Optional, Dict, Tuple
from curl_cffi import requests as cffi_requests

from src.core.config import AppConfig
from src.core.shutdown_manager import ShutdownManager
from src.database import DatabaseManager, AccountSession
from src.utils.logger import logger


def _close_async_session(async_sess: cffi_requests.AsyncSession) -> None:
    """Closes an AsyncSession cleanly without leaving orphaned coroutines."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(async_sess.close())
        else:
            asyncio.run(async_sess.close())
    except Exception:
        pass


class SessionManager:
    """
    Manages Playwright persistent browser profiles, interactive logins for Cloudflare/Auth/NSFW,
    session verification, cookie persistence, and impersonated curl_cffi HTTP sessions.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    _http_sessions: Dict[str, cffi_requests.Session] = {}
    _async_http_sessions: Dict[str, cffi_requests.AsyncSession] = {}
    _http_sessions_lock: threading.Lock = threading.Lock()

    @classmethod
    def invalidate_http_session(cls, provider_name: str) -> None:
        """Closes and removes the pooled HTTP sessions (sync and async) for a provider."""
        with cls._http_sessions_lock:
            key = provider_name.lower()
            old_sess = cls._http_sessions.pop(key, None)
            if old_sess:
                try:
                    old_sess.close()
                except Exception:
                    pass
            old_async_sess = cls._async_http_sessions.pop(key, None)
            if old_async_sess:
                _close_async_session(old_async_sess)

    @classmethod
    def close_all_http_sessions(cls) -> None:
        """Closes all pooled curl_cffi sync and async sessions."""
        with cls._http_sessions_lock:
            for s in cls._http_sessions.values():
                try:
                    s.close()
                except Exception:
                    pass
            cls._http_sessions.clear()

            for async_s in cls._async_http_sessions.values():
                _close_async_session(async_s)
            cls._async_http_sessions.clear()

    @classmethod
    def get_saved_session(cls, provider_name: str) -> Optional[AccountSession]:
        """Retrieves stored session info from SQLite."""
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            return session.query(AccountSession).filter_by(provider_name=provider_name).first()

    @classmethod
    def is_member_authenticated(cls, provider_name: str) -> bool:
        """
        Checks if the user is authenticated with an actual registered member account.
        (Distinct from a guest session with anti-bot cookies only).
        """
        acc = cls.get_saved_session(provider_name)
        if not acc:
            return False
        cookies = acc.get_cookies_dict()
        if not cookies:
            return False

        if provider_name.lower() in ("loverslab", "nsfwmods"):
            member_id = cookies.get("ips4_member_id")
            return bool(member_id and member_id != "0")

        if provider_name.lower() == "patreon":
            return bool(cookies.get("session_id") or cookies.get("patreon_session_id") or cookies.get("api_session_id"))

        return bool(acc.is_authenticated)

    @classmethod
    def is_session_ready(cls, provider_name: str) -> bool:
        """
        Checks if the provider session has valid cookies/tokens to navigate and download.
        For LoversLab: accepts cf_clearance, ips4_hasAcceptedAge, or member login.
        For Patreon: accepts session cookies.
        """
        acc = cls.get_saved_session(provider_name)
        if not acc:
            return False

        cookies = acc.get_cookies_dict()
        if not cookies:
            return False

        if provider_name.lower() in ("loverslab", "nsfwmods"):
            # Ready if we have Cloudflare clearance, adult age consent, or member login
            has_cf = bool(cookies.get("cf_clearance"))
            has_age = bool(cookies.get("ips4_hasAcceptedAge"))
            has_member = bool(cookies.get("ips4_member_id") and cookies.get("ips4_member_id") != "0")
            has_session = bool(cookies.get("ips4_IPSSessionFront"))
            return has_cf or has_age or has_member or has_session

        if provider_name.lower() == "patreon":
            return bool(
                cookies.get("session_id")
                or cookies.get("patreon_session_id")
                or cookies.get("api_session_id")
                or len(cookies) >= 2
            )

        return len(cookies) > 0

    @classmethod
    def save_session(
        cls,
        provider_name: str,
        cookies: Dict[str, str],
        user_display_name: str = "",
        is_authenticated: bool = True,
        user_agent: Optional[str] = None,
    ) -> None:
        """Stores or updates session data in SQLite with detailed token analysis."""
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()

            # Check for member ID or display name in cookies
            member_id = cookies.get("ips4_member_id")
            if member_id and member_id != "0" and not user_display_name:
                user_display_name = f"Membre #{member_id}"

            if not acc:
                acc = AccountSession(
                    provider_name=provider_name,
                    is_authenticated=is_authenticated,
                    user_display_name=user_display_name,
                    user_agent=user_agent or cls.DEFAULT_USER_AGENT,
                    last_verified=datetime.now(),
                )
                acc.set_cookies_dict(cookies)
                session.add(acc)
            else:
                acc.is_authenticated = is_authenticated
                if user_display_name:
                    acc.user_display_name = user_display_name
                if user_agent:
                    acc.user_agent = user_agent
                acc.set_cookies_dict(cookies)
                acc.last_verified = datetime.now()
            session.commit()

            tokens_found = [
                k for k in ["cf_clearance", "ips4_hasAcceptedAge", "ips4_member_id", "session_id"] if k in cookies
            ]
            cls.invalidate_http_session(provider_name)
            logger.info(
                f"Session enregistrée pour '{provider_name}': {len(cookies)} cookie(s) sauvegardé(s). "
                f"Tokens identifiés: {tokens_found}. Utilisateur: '{user_display_name or 'Anonyme/Anti-bot validé'}'."
            )

    @classmethod
    def clear_session(cls, provider_name: str) -> bool:
        """Clears stored session from SQLite and removes persistent browser profile directory."""
        try:
            cls.invalidate_http_session(provider_name)
            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()
                if acc:
                    session.delete(acc)
                    session.commit()

            # Clean browser profile folder
            profile_dir = AppConfig.get_browser_profile_dir() / provider_name
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)

            logger.info(f"Session et profil navigateur réinitialisés pour '{provider_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation de session pour '{provider_name}': {e}")
            return False

    @classmethod
    def verify_session(cls, provider_name: str) -> Tuple[bool, str]:
        """Performs a live HTTP check using saved cookies and updates status."""
        session = cls.get_http_session(provider_name)
        try:
            if provider_name.lower() == "loverslab":
                url = "https://www.loverslab.com/"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session LoversLab ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    html = resp.text
                    if "elUserNav" in html or "Sign Out" in html or "Déconnexion" in html:
                        return True, "Session membre connectée et active."
                    if "cf_clearance" in str(session.cookies) or "ips4_hasAcceptedAge" in str(session.cookies):
                        return True, "Session active (Anti-Bot Cloudflare & +18 ans validés)."
                    return True, "Accès au site vérifié avec succès."
                if resp.status_code in [403, 503]:
                    return (
                        False,
                        f"Protection Cloudflare active (Code {resp.status_code}). Veuillez rouvrir le navigateur.",
                    )

            elif provider_name.lower() == "nsfwmods":
                url = "https://nsfwmods.com/files/category/287-sims-mods/"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session NSFWMods ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    html = resp.text
                    if "elUserNav" in html or "Sign Out" in html or "Déconnexion" in html:
                        return True, "Session membre NSFWMods connectée et active."
                    return True, "Accès à NSFWMods vérifié avec succès."
                if resp.status_code in [403, 503]:
                    return (
                        False,
                        f"Protection anti-bot active sur NSFWMods (Code {resp.status_code}). Veuillez ouvrir le navigateur.",
                    )

            elif provider_name.lower() == "curseforge":
                url = "https://www.curseforge.com/sims4"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session CurseForge ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    return True, "Accès à CurseForge Sims 4 vérifié avec succès."
                if resp.status_code in [403, 503]:
                    return (
                        False,
                        f"Protection Cloudflare active sur CurseForge (Code {resp.status_code}). Veuillez ouvrir le navigateur.",
                    )

            elif provider_name.lower() == "thesimsresource":
                url = "https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session The Sims Resource ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    return True, "Accès à The Sims Resource Sims 4 vérifié avec succès."
                if resp.status_code in [403, 503]:
                    return (
                        False,
                        f"Protection anti-bot active sur The Sims Resource (Code {resp.status_code}). Veuillez ouvrir le navigateur.",
                    )

            elif provider_name.lower() == "patreon":
                url = "https://www.patreon.com/api/current_user"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session Patreon ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get("attributes", {})
                    name = data.get("full_name") or data.get("email") or "Connecté"
                    return True, f"Connecté à Patreon ({name})."
                if resp.status_code in [401, 403]:
                    return False, "Non connecté à Patreon ou session expirée."

            return False, f"Réponse inattendue (Code {resp.status_code})"
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de session pour {provider_name}: {e}")
            return False, f"Erreur de connexion: {e}"

    @classmethod
    def get_http_session(cls, provider_name: str, force_new: bool = False) -> cffi_requests.Session:
        """
        Returns a configured curl_cffi Session loaded with provider cookies and browser impersonation.
        Reuses pooled session per provider for connection reuse and performance.
        """
        key = provider_name.lower()
        if not force_new:
            with cls._http_sessions_lock:
                if key in cls._http_sessions:
                    return cls._http_sessions[key]

        http_session: cffi_requests.Session = cffi_requests.Session(impersonate="chrome120")
        http_session.headers.update(
            {
                "User-Agent": cls.DEFAULT_USER_AGENT,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        # Load cookies from DB
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()
            if acc:
                cookies = acc.get_cookies_dict()
                for name, value in cookies.items():
                    http_session.cookies.set(name, value)
                if acc.user_agent:
                    http_session.headers["User-Agent"] = acc.user_agent

        # For LoversLab & NSFWMods: automatically ensure adult age consent cookie
        if key == "loverslab":
            http_session.cookies.set("ips4_hasAcceptedAge", "1", domain=".loverslab.com")
            http_session.cookies.set("ips4_IPSSessionFront", "1", domain=".loverslab.com")
        elif key == "nsfwmods":
            http_session.cookies.set("ips4_hasAcceptedAge", "1", domain=".nsfwmods.com")
            http_session.cookies.set("ips4_IPSSessionFront", "1", domain=".nsfwmods.com")

        if not force_new:
            with cls._http_sessions_lock:
                cls._http_sessions[key] = http_session

        return http_session

    @classmethod
    def get_async_http_session(cls, provider_name: str, force_new: bool = False) -> cffi_requests.AsyncSession:
        """
        Returns a configured curl_cffi AsyncSession loaded with provider cookies and browser impersonation.
        Reuses pooled async session per provider for high-performance concurrent I/O.
        """
        key = provider_name.lower()
        if not force_new:
            with cls._http_sessions_lock:
                if key in cls._async_http_sessions:
                    return cls._async_http_sessions[key]

        async_session: cffi_requests.AsyncSession = cffi_requests.AsyncSession(impersonate="chrome120")
        async_session.headers.update(
            {
                "User-Agent": cls.DEFAULT_USER_AGENT,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()
            if acc:
                cookies = acc.get_cookies_dict()
                for name, value in cookies.items():
                    async_session.cookies.set(name, value)
                if acc.user_agent:
                    async_session.headers["User-Agent"] = acc.user_agent

        if key == "loverslab":
            async_session.cookies.set("ips4_hasAcceptedAge", "1", domain=".loverslab.com")
            async_session.cookies.set("ips4_IPSSessionFront", "1", domain=".loverslab.com")
        elif key == "nsfwmods":
            async_session.cookies.set("ips4_hasAcceptedAge", "1", domain=".nsfwmods.com")
            async_session.cookies.set("ips4_IPSSessionFront", "1", domain=".nsfwmods.com")

        if not force_new:
            with cls._http_sessions_lock:
                cls._async_http_sessions[key] = async_session

        return async_session

    @classmethod
    def is_browser_available(cls) -> bool:
        """Checks if a browser engine is available for Playwright via BrowserLoginHelper."""
        from src.core.browser_login import BrowserLoginHelper

        return BrowserLoginHelper.is_browser_available()

    @classmethod
    def launch_interactive_login(
        cls,
        provider_name: str,
        target_url: str,
        success_indicator_selector: Optional[str] = None,
        timeout_seconds: int = 180,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """Launches a visible browser window via Playwright to log in and capture cookies."""
        from src.core.browser_login import BrowserLoginHelper

        return BrowserLoginHelper.launch_interactive_login(
            provider_name=provider_name,
            target_url=target_url,
            save_session_callback=cls.save_session,
            user_agent=cls.DEFAULT_USER_AGENT,
            timeout_seconds=timeout_seconds,
        )


ShutdownManager.register_callback(SessionManager.close_all_http_sessions)

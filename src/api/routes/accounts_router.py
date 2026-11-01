"""Routes API REST pour les comptes et sessions anti-bot (Front -> Back)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas.accounts import (
    AccountActionResponse,
    AccountListResponse,
    AccountLoginRequest,
    AccountLoginResponse,
    AccountStatusItem,
)
from src.core.config import ACCOUNT_SUPPORTED_PROVIDERS, PUBLIC_NO_ACCOUNT_PROVIDERS
from src.core.session_manager import SessionManager
from src.infrastructure.database.repositories.sqlalchemy_account_repository import (
    SqlAlchemyAccountRepository,
)

from src.providers import ProviderRegistry

router = APIRouter(prefix="/accounts", tags=["Accounts & Anti-Bot"])
_account_repo = SqlAlchemyAccountRepository()

PROVIDERS_LOGIN_URLS = {
    "loverslab": "https://www.loverslab.com/login/",
    "nsfwmods": "https://nsfwmods.com/login/",
    "curseforge": "https://www.curseforge.com/login",
    "thesimsresource": "https://www.thesimsresource.com/account/login",
    "patreon": "https://www.patreon.com/login",
    "modthesims": "https://modthesims.info/member.php?action=login",
    "simsfinds": "https://www.simsfinds.com/en/downloads/sims4",
    "nexusmods": "https://users.nexusmods.com/auth/sign_in?redirect_url=https%3A%2F%2Fwww.nexusmods.com%2Fthesims4",
    "simfileshare": "https://simfileshare.net/",
    "mmccworld": "https://www.tumblr.com/login?redirect_to=https%3A%2F%2Fmaxismatchccworld.tumblr.com%2F",
    "maxismatchccworld": "https://www.tumblr.com/login?redirect_to=https%3A%2F%2Fmaxismatchccworld.tumblr.com%2F",
    "sims4studio": "https://sims4studio.com/login",
    "f95zone": "https://f95zone.to/login/",
    "itchio": "https://itch.io/login",
    "gamebanana": "https://gamebanana.com/members/account/login",
    "synthira": "https://synthira.ru/index/1",
}


def _get_registered_provider_names() -> list[str]:
    names = list(ACCOUNT_SUPPORTED_PROVIDERS)
    for prov in ProviderRegistry.list_providers():
        pname = prov.provider_name.lower()
        if pname in PUBLIC_NO_ACCOUNT_PROVIDERS:
            continue
        if pname not in names:
            names.append(pname)
    return names


def _get_login_url(provider_name: str) -> str | None:
    p_lower = provider_name.lower()
    if p_lower in PROVIDERS_LOGIN_URLS:
        return PROVIDERS_LOGIN_URLS[p_lower]
    prov = ProviderRegistry.get_provider(p_lower)
    if prov:
        login_url = getattr(prov, "login_url", None)
        if login_url:
            return str(login_url)
        base_url = getattr(prov, "base_url", None)
        if base_url:
            return f"{str(base_url).rstrip('/')}/login"
    return None


@router.get("", response_model=AccountListResponse)
def get_accounts() -> AccountListResponse:
    """Liste le statut d'authentification et anti-bot de tous les providers supportés."""
    accounts_list: list[AccountStatusItem] = []

    for p_name in _get_registered_provider_names():
        acc = _account_repo.get_by_provider(p_name)
        is_ready = SessionManager.is_session_ready(p_name)
        is_member = SessionManager.is_member_authenticated(p_name)
        cookies_dict = acc.cookies_data if acc else {}

        user_display_name = ""
        if acc and acc.user_display_name:
            user_display_name = acc.user_display_name
        elif is_member:
            user_display_name = "Connecté"
        elif is_ready:
            user_display_name = "Anti-bot validé"

        accounts_list.append(
            AccountStatusItem(
                provider_name=p_name,
                is_configured=acc is not None and len(cookies_dict) > 0,
                is_ready=is_ready,
                is_member=is_member,
                user_display_name=user_display_name,
                cookies_count=len(cookies_dict),
                last_verified=acc.last_verified if acc else None,
            )
        )

    return AccountListResponse(accounts=accounts_list)


@router.post("/{provider_name}/test", response_model=AccountActionResponse)
def test_account(provider_name: str) -> AccountActionResponse:
    """Effectue un test HTTP en direct des cookies de session pour le provider spécifié."""
    p_lower = provider_name.lower()
    if p_lower not in _get_registered_provider_names():
        raise HTTPException(status_code=400, detail=f"Fournisseur non reconnu: {provider_name}")

    ok, msg = SessionManager.verify_session(p_lower)
    return AccountActionResponse(success=ok, message=msg)


@router.delete("/{provider_name}", response_model=AccountActionResponse)
def clear_account(provider_name: str) -> AccountActionResponse:
    """Efface les cookies de session stockés et supprime le profil de navigateur persistant."""
    p_lower = provider_name.lower()
    if p_lower not in _get_registered_provider_names():
        raise HTTPException(status_code=400, detail=f"Fournisseur non reconnu: {provider_name}")

    ok = SessionManager.clear_session(p_lower)
    if ok:
        return AccountActionResponse(success=True, message=f"Session pour '{provider_name}' réinitialisée avec succès.")
    return AccountActionResponse(
        success=False, message=f"Erreur lors de la réinitialisation de la session pour '{provider_name}'."
    )


@router.post("/{provider_name}/login", response_model=AccountLoginResponse)
def login_account(provider_name: str, payload: AccountLoginRequest = AccountLoginRequest()) -> AccountLoginResponse:
    """Lance une fenêtre Playwright interactive pour résoudre Cloudflare ou se connecter."""
    p_lower = provider_name.lower()
    login_url = _get_login_url(p_lower)
    if not login_url:
        raise HTTPException(
            status_code=400, detail=f"Fournisseur non reconnu ou sans URL de connexion: {provider_name}"
        )

    ok, msg, cookies = SessionManager.launch_interactive_login(
        provider_name=p_lower,
        target_url=login_url,
        timeout_seconds=payload.timeout_seconds,
    )

    return AccountLoginResponse(
        success=ok,
        message=msg,
        cookies_count=len(cookies),
    )


@router.post("/nexusmods/api-key", response_model=AccountActionResponse)
def set_nexusmods_api_key(payload: dict[str, str]) -> AccountActionResponse:
    """Enregistre et valide une clé API personnelle Nexus Mods directement via l'API officielle."""
    key = payload.get("api_key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Clé API manquante.")

    import httpx

    try:
        resp = httpx.get(
            "https://api.nexusmods.com/v1/users/validate.json",
            headers={"apikey": key},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            username = data.get("name", "Nexus User")
            cookies = {"nexusmods_api_key": key}
            SessionManager.save_session(
                provider_name="nexusmods",
                cookies_dict=cookies,
                user_display_name=username,
                is_authenticated=True,
            )
            return AccountActionResponse(
                success=True,
                message=f"Clé API validée avec succès pour le compte '{username}'.",
            )
        else:
            return AccountActionResponse(
                success=False,
                message=f"Clé API rejetée par Nexus Mods (Code HTTP {resp.status_code}).",
            )
    except Exception as e:
        return AccountActionResponse(
            success=False,
            message=f"Erreur lors de la validation de la clé API Nexus Mods: {e}",
        )

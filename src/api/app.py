import asyncio
import time
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.routes import (
    accounts_router,
    catalog_router,
    installed_mods_router,
    mod_updates_router,
    settings_router,
    logs_router,
    system_router,
)
from src.infrastructure.database import DatabaseManager
from src.providers import ProviderRegistry
from src.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Démarrage de l'API REST SIMS 4 Mods Manager...")
    DatabaseManager.get_instance()
    ProviderRegistry.initialize()

    async def _async_warmup():
        try:
            await asyncio.sleep(0.05)
            from sqlalchemy import text

            db = DatabaseManager.get_instance()
            with db.get_session() as s:
                s.execute(text("SELECT 1")).fetchall()
            logger.debug("[Warmup] Préchauffage mémoire du catalogue et de la base terminé.")
        except Exception:
            pass

    asyncio.create_task(_async_warmup())
    yield
    # Shutdown
    logger.info("Arrêt de l'API REST SIMS 4 Mods Manager.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="SIMS 4 Mods Manager API",
        description=(
            "API REST unifiée pour piloter l'ensemble des fonctionnalités du gestionnaire de mods Sims 4 : "
            "Catalogue multi-sources, téléchargement, installation, détection, activation/désactivation, "
            "mises à jour en 1 clic, contournement anti-bot et journalisation en temps réel."
        ),
        version="0.5.0",
        lifespan=lifespan,
    )

    # Configuration CORS sécurisée (restreinte aux origines locales et loopback)
    allowed_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "app://sims4-mods-manager",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from src.core.security import verify_internal_token
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def security_token_middleware(request, call_next):
        """Vérifie l'origine loopback, l'hôte (anti-DNS Rebinding), le jeton X-Internal-Token et applique les en-têtes HTTP de sécurité."""
        path = request.url.path
        public_paths = ("/api/system/ping", "/docs", "/redoc", "/openapi.json")
        if not (path.startswith(public_paths) or path == "/"):
            client_host = request.client.host if request.client else ""
            if client_host and client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Accès restreint à l'environnement local (loopback)."},
                )

            # Protection contre les attaques par DNS Rebinding
            req_host = (request.headers.get("host") or "").split(":")[0].lower()
            if req_host and req_host not in ("127.0.0.1", "localhost", "testserver", "::1"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "En-tête Host non autorisé (anti-DNS Rebinding)."},
                )

            token = request.headers.get("X-Internal-Token")
            if not verify_internal_token(token):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Jeton d'autorisation interne (X-Internal-Token) manquant ou invalide."},
                )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    # Rate Limiter local en mémoire pour endpoints d'actions critiques
    _rate_limits: dict[str, list[float]] = {}
    _rate_lock = threading.Lock()
    RATE_LIMIT_RULES = {
        "/api/catalog/sync": (10, 60.0),  # max 10 syncs / minute
        "/api/catalog/install": (30, 60.0),  # max 30 installations / minute
        "/api/catalog/install-stream": (30, 60.0),  # max 30 installations stream / minute
        "/api/catalog/report-missing-requirements": (10, 60.0),  # max 10 signalements forum / minute
        "/api/catalog/delete-missing-report": (15, 60.0),  # max 15 suppressions forum / minute
        "/api/updates/batch": (10, 60.0),  # max 10 mises à jour par lot / minute
        "/api/mods/toggle": (60, 60.0),  # max 60 toggles / minute
    }

    @app.middleware("http")
    async def rate_limiting_middleware(request, call_next):
        """Protection contre les surcharges de requêtes en rafale (Rate Limiter) avec purge mémoire."""
        from src.core.security import is_auth_disabled

        if is_auth_disabled():
            return await call_next(request)

        client_host = request.client.host if request.client else ""
        if client_host == "testclient":
            return await call_next(request)

        path = request.url.path
        if path in RATE_LIMIT_RULES:
            max_calls, window = RATE_LIMIT_RULES[path]
            now = time.time()
            key = f"{client_host}:{path}"
            with _rate_lock:
                if len(_rate_limits) > 256:
                    stale_keys = [
                        k for k, ts_list in _rate_limits.items() if not ts_list or (now - ts_list[-1]) >= window
                    ]
                    for sk in stale_keys:
                        _rate_limits.pop(sk, None)

                timestamps = [t for t in _rate_limits.get(key, []) if now - t < window]
                if len(timestamps) >= max_calls:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Trop de requêtes. Veuillez patienter avant de relancer cette opération."},
                    )
                timestamps.append(now)
                _rate_limits[key] = timestamps

        return await call_next(request)

    # Mount API routers
    app.include_router(accounts_router.router, prefix="/api")
    app.include_router(catalog_router.router, prefix="/api")
    app.include_router(installed_mods_router.router, prefix="/api")
    app.include_router(mod_updates_router.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(logs_router.router, prefix="/api")
    app.include_router(system_router.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root():
        """Exécute l'opération root.

        Returns:
            Résultat de l'opération root.
        """
        return RedirectResponse(url="/docs")

    return app


app = create_app()

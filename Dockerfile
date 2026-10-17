# ==============================================================================
# Dockerfile Multi-Stage : SIMS 4 Mods Manager (Mode Serveur Headless REST API)
# ==============================================================================
FROM python:3.12-slim-bookworm AS base

# Empêcher la mise en cache Python bytecode et forcer le flush stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Installer les dépendances système minimales requises (SQLite, curl, certificats)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libsqlite3-0 \
    p7zip-full \
    unrar-free \
    && rm -rf /var/lib/apt/lists/*

# Installer uv pour des installations de dépendances ultra-rapides
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copier les définitions de dépendances
COPY pyproject.toml uv.lock ./

# Installer l'environnement virtuel et les dépendances projet (sans dev)
RUN uv sync --frozen --no-dev --no-install-project

# Installer le runtime Chromium pour Playwright (anti-bot Cloudflare headless)
RUN uv run playwright install --with-deps chromium

# Copier le code source de l'application
COPY src/ ./src/
COPY plugins/ ./plugins/
COPY run.py ./

# Exposer le port de l'API REST FastAPI
EXPOSE 8000

# Volumes pour la persistance de la BDD et le dossier des Mods Sims 4
VOLUME ["/root/.sims4_mod_manager", "/sims4_mods"]

# Point d'entrée : Serveur FastAPI autonome
ENTRYPOINT ["uv", "run", "python", "run.py", "--server", "--port", "8000"]

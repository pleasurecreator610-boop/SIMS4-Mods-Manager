# SIMS 4 Mods Manager 💎

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-286%20passed%20(100%25)-success.svg)](./tests)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Architecture: 3--Tier POO](https://img.shields.io/badge/architecture-3--Tier%20POO-purple.svg)](./documentation/architecture.md)
[![Plugins: Modulaires](https://img.shields.io/badge/plugins-extensibles-orange.svg)](./plugins)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](./LICENSE)

Gestionnaire de mods automatisé, moderne et ultra-performant pour **Les Sims 4** (Windows & Serveurs).  
Conçu avec une architecture **100% découplée via API REST (FastAPI)**, un domaine métier en **POO 3-Tiers** (Orchestrators $\to$ Coordinators $\to$ Actions), un système de plugins extensible et une interface de bureau réactive **PySide6**.

---

## ⚡ En Bref : Ce Que Fait le Projet

- **🔍 Recherche & Indexation Automatisée** : Scrape et indexe le contenu (LoversLab, Patreon) avec contournement transparent des protections anti-bot (Cloudflare Turnstile) via Playwright.
- **🔌 Architecture de Plugins Modulaire** : Ajout de nouvelles sources de téléchargement par simple dépôt de fichier Python dans `plugins/` via `@register_provider`.
- **⚔️ Détecteur de Conflits DBPF** : Analyse binaire des conteneurs `.package` pour détecter à l'avance les collisions de tuning (TGI) entre mods installés.
- **🧩 Résolution de Dépendances en Cascade** : Détecte les prérequis obligatoires (WickedWhims, etc.) et les installe automatiquement en chaîne.
- **📦 Respect Strict de la Règle `.ts4script`** : Remonte automatiquement les scripts au niveau 1 de profondeur (`Mods/<NomDuMod>/script.ts4script`) pour garantir leur chargement par le moteur des Sims 4.
- **🎛️ Activation / Désactivation Propre** : Désactive instantanément un mod via extension `.disabled` réversible sans supprimer vos fichiers.
- **⚡ Mises à Jour Sécurisées avec Rollback** : Compare les versions en un clic et crée une sauvegarde d'archive automatique avant tout remplacement.


---

## 🚀 Démarrage Express (3 Commandes)

### 1. Prérequis
Installez [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets ultra-rapide) :
```powershell
scoop install uv
```

### 2. Installation
```powershell
# Cloner et installer l'environnement complet
uv sync

# Installer Chromium headless pour le contournement anti-bot
uv run playwright install chromium
```

### 3. Lancer l'Application
```powershell
# Mode Interface Graphique (PySide6)
uv run python run.py

# Ou Mode Serveur API Autonome (sans GUI)
uv run python run.py --server --port 8000
```
> 📖 *Documentation interactive Swagger disponible sur : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)*

---

## 🧪 Tests & Vérification Qualité

Le projet dispose d'une suite de **229 tests automatisés** garantissant 100% de stabilité :

```powershell
# Lancer l'ensemble des tests (tests unitaires & intégration)
uv run pytest -q

# Lancer les tests unitaires seuls
uv run pytest tests/unit/ -q

# Lancer le flux end-to-end simulé
uv run pytest tests/e2e/test_mocked_flow_e2e.py -v

# Vérification du code avec Ruff
uv run ruff check src/ tests/
```

---

## 🏛️ Architecture 3-Tiers POO

La couche applicative (`src/application/`) est strictement découpée en 3 niveaux :
1. **Tier 1 - Orchestrateurs (`*_orchestrator.py`)** : Façades de haut niveau appelées par les routes REST.
2. **Tier 2 - Coordinateurs (`*_coordinator.py`)** : Gestion du séquençage, des boucles, des batchs et du suivi de progression (`SyncTracker`).
3. **Tier 3 - Actions (`*_actions.py`)** : Opérations atomiques pures (I/O, validation binaire DBPF, renommage, normalisation).

---

## 📚 Documentation Technique Détaillée

Pour les développeurs et contributeurs, une documentation complète est disponible dans le dossier [`documentation/`](./documentation/) :

| Document | Description |
| :--- | :--- |
| 📖 **[Portail d'Accueil](./documentation/index.md)** | Vue synthétique de la documentation |
| 🏛️ **[Architecture & Découpage](./documentation/architecture.md)** | Clean architecture, découpage 3-tiers et arborescence |
| 📊 **[Modules & Classes](./documentation/modules_and_classes.md)** | Schémas de données, diagrammes Mermaid de classes et séquences |
| ⚙️ **[Services Métier & Fournisseurs](./documentation/services_and_providers.md)** | Détails du scraping, règle `.ts4script`, connecteurs LoversLab & Patreon |
| 🌐 **[Spécification de l'API REST](./documentation/api_reference.md)** | Endpoints, paramètres, DTOs Pydantic et streaming NDJSON |
| 🚀 **[Optimisations & Roadmap](./documentation/proposals_and_roadmap.md)** | Analyse de performance, pool HTTP, détection conflits DBPF et packaging |
| 🧩 **[Classification des Dépendances](./documentation/dependency_classification_and_noise.md)** | Algorithme des 4 statuts et règles de filtrage du bruit |

---

## 📄 Licence

Ce projet est distribué sous licence GNU GPL v3. Voir le fichier [LICENSE](./LICENSE) pour plus d'informations.

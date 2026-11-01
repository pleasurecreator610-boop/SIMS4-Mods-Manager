# SIMS 4 Mods Manager 💎

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-100%25%20passed-success.svg)](./tests)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Architecture: Clean + 3--Tier POO](https://img.shields.io/badge/architecture-Clean%20%2B%203--Tier%20POO-purple.svg)](./documentation/architecture.md)
[![Providers: 22 Plateformes](https://img.shields.io/badge/providers-22%20plateformes-orange.svg)](./plugins)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](./LICENSE)

Gestionnaire de mods automatisé, moderne et haute performance pour **Les Sims 4** (Windows & Serveurs).  
Conçu selon une **Clean Architecture découplée via API REST (FastAPI)**, un domaine métier en **POO 3-Tiers** (`Orchestrators` $\rightarrow$ `Coordinators` $\rightarrow$ `Actions`), un système de **22 plugins fournisseurs auto-découverts** et une interface graphique réactive **PySide6**.

---

## ⚡ En Bref : Fonctionnalités Clés

- **🌐 Catalogue Unifié Multi-Plateformes (22 Sources)** : Indexe et synchronise en parallèle les portails officiels de frameworks, les grands catalogues communautaires SFW et les portails adultes (`+18`, masqués par défaut).
- **🛡️ Priorité Absolue aux Sites Officiels des Frameworks** : Toute dépendance vers **MC Command Center (Deaderpool)**, **XML Injector (Scumbumbo)**, **RPO / Mood Pack / Toolbox (Lumpinou)**, **WickedWhims / WonderfulWhims (Wicked.cc)**, **Basemental** ou **Andrew's Pose Player (Sims 4 Studio)** est automatiquement interceptée et téléchargée depuis son **site officiel** sans nécessiter de compte tiers.
- **🧩 Résolution de Dépendances & Déduplication Inter-Plateformes** : Détecte les prérequis en cascade, évite les téléchargements en doublon entre plateformes (`ModMatcher` + `ActiveInstallationRegistry`) et distingue automatiquement les vrais mods des notes d'auteurs (`COMMENT_NOISE`).
- **📢 Signalement & Commentaires aux Créateurs** : Permet d'interpeller proprement l'auteur d'un mod (commentaire forum ou message privé en anglais standardisé) lorsqu'un prérequis est introuvable, après vérification ou demande d'authentification.
- **⚔️ Détecteur de Conflits DBPF (`mmap` Zero-Copy)** : Inspecte les en-têtes binaires `.package` et les tables d'index TGI (Type-Group-Instance) avec cache SQLite incrémental pour détecter instantanément les collisions de tuning et de traductions (`STBL`).
- **📦 Règle `.ts4script` & Mises à Jour avec Rollback** : Remonte automatiquement les scripts `.ts4script` au niveau 1 (`Mods/<NomDuMod>/script.ts4script`), permet l'activation/désactivation réversible (`.disabled`) et crée une sauvegarde ZIP automatique avant chaque mise à jour.

---

## 🌍 Les 22 Plateformes de Mods Intégrées

### 1. Portails Officiels de Frameworks (Prioritaires • Sans Compte)
| Plateforme | Identifiant | Site Officiel | Contenu Principal |
| :--- | :--- | :--- | :--- |
| **Deaderpool (MCCC)** | `deaderpool` | `deaderpool-mccc.com` | *MC Command Center (MCCC)* & *MC WooHoo* |
| **Scumbumbo Memorial** | `scumbumbo` | `scumbumbomods.com` | *XML Injector*, *Teleport Any Sim*, *Keep Instruments* |
| **Lumpinou Mods** | `lumpinou` | `lumpinoumods.com` | *RPO (WooHoo Wellness)*, *Mood Pack Mod*, *Toolbox*, *LGBTQIA+* |
| **Wicked.cc (TURBODRIVER)** | `wickedcc` | `wicked.cc` / `wonderfulwhims.com` | *WickedWhims* (`+18`), *WonderfulWhims* & animations officielles |
| **Basemental CC** | `basemental` | `basementalcc.com` | *Basemental Drugs* (`+18`), *Basemental Gangs*, *Universal Venue List* |

### 2. Catalogues Communautaires & Portails Créateurs SFW
| Plateforme | Identifiant | Compte / Session | Commentaires / MP | Contenu Principal |
| :--- | :--- | :--- | :--- | :--- |
| **CurseForge** | `curseforge` | Optionnel (Anti-bot) | Oui | Catalogue officiel Sims 4 & téléchargements ForgeCDN |
| **The Sims Resource (TSR)** | `thesimsresource` | Optionnel | Oui | Créations CC, coiffures, vêtements, meubles & mods |
| **ModTheSims (MTS)** | `modthesims` | Optionnel | Oui | Mods de gameplay, scripts, traits, carrières & créations |
| **Nexus Mods** | `nexusmods` | Clé API / Session | Oui | Mods Sims 4 Gameplay, UI, reshades & utilitaires |
| **Patreon** | `patreon` | Optionnel (Abonnés) | Oui | Publications créateurs publiques et paliers abonnés |
| **SimsFinds** | `simsfinds` | Optionnel | Oui | Catalogue CC, meubles, vêtements & mods |
| **Maxis Match CC World** | `mmccworld` | Optionnel (Tumblr) | Oui | Répertoire Maxis Match CC & redirections SimFileShare |
| **SimFileShare (SFS)** | `simfileshare` | Sans compte | Non | Résolveur universel de fichiers & dossiers SimFileShare |
| **Sims 4 Studio** | `sims4studio` | Optionnel (Forum) | Oui | *Andrew's Pose Player*, *Teleport Any Sim* & *Creator Studios* |
| **GameBanana** | `gamebanana` | Optionnel | Oui | Catalogue Sims 4 via l'API publique Core v11 |
| **The Sims Catalog** | `thesimscatalog` | Sans compte | Non | Mods de gameplay, traits, carrières & CC |
| **itch.io** | `itchio` | Optionnel | Oui | Mods indépendants Sims 4 (`tag-sims-4`) |
| **LittleMsSam** | `littlemssam` | Sans compte | Non | Plus de 200 mods de gameplay, *RSM*, *Small Mods* |
| **SixamCC** | `sixamcc` | Sans compte | Non | Packs d'objets et CC façon Kits officiels |

### 3. Portails Adultes (`+18` — Masqués par défaut, activables en 1 clic)
| Plateforme | Identifiant | Compte / Session | Commentaires / MP | Contenu Principal |
| :--- | :--- | :--- | :--- | :--- |
| **LoversLab** | `loverslab` | Requis / Anti-bot | Oui (Forum IPS4 & MP) | Catalogue complet Sims 4 Adulte (14 sous-catégories) |
| **NSFWMods** | `nsfwmods` | Optionnel / Anti-bot | Oui (Forum IPS4 & MP) | Mods adultes, animations & accessoires Sims 4 |
| **Synthira.ru** | `synthira` | Optionnel | Oui | Portail Sims 4 (+18), animations WW & traductions |
| **F95zone** | `f95zone` | Requis (XenForo) | Oui | Fils dédiés mods Sims 4, packs d'animations & scripts |
| **SmutBase** | `smutbase` | Sans compte | Non | Modèles 3D, rigs, accessoires et ressources d'animation |

---

## 🚀 Démarrage Express (3 Commandes)

### 1. Prérequis
Installez [`uv`](https://docs.astral.sh/uv/) via Scoop :
```powershell
scoop install uv
```

### 2. Installation de l'Environnement
```powershell
uv sync
uv run playwright install chromium
```

### 3. Lancement de l'Application
```powershell
# Mode Interface Graphique Bureau (PySide6)
uv run python run.py

# Mode Serveur API REST Autonome (sans interface graphique)
uv run python run.py --server --port 8000
```

---

## 🧪 Tests & Conformité Qualité

```powershell
# Exécution des tests unitaires par module (mode verbeux)
uv run pytest tests/unit/core -v
uv run pytest tests/unit/utils -v
uv run pytest tests/unit/database -v
uv run pytest tests/unit/domain -v
uv run pytest tests/unit/infrastructure -v
uv run pytest tests/unit/security -v
uv run pytest tests/unit/providers -v
uv run pytest tests/unit/application -v
uv run pytest tests/unit/api -v
uv run pytest tests/unit/ui -v
uv run pytest tests/e2e -v

# Audit complet de conformité statique (Ruff, Bandit, Vulture, Deptry, Mypy)
python D:\Workspace\Gitlab\workspace\02_compliance_code\python\analyze.py --target . --skip-update
```

---

## 📚 Documentation Complète

| Document | Contenu |
| :--- | :--- |
| 📖 **[Portail Documentation](./documentation/index.md)** | Point d'entrée général, navigation et synthèse des fonctionnalités |
| 🏛️ **[Architecture Unifiée](./documentation/architecture.md)** | Clean Architecture, POO 3-Tiers, schémas Mermaid, concurrence et DBPF `mmap` |
| 📊 **[Modules & Classes](./documentation/modules_and_classes.md)** | Diagrammes de classes, entités SQLite WAL/FTS5 et séquences |
| ⚙️ **[Services & Fournisseurs](./documentation/services_and_providers.md)** | Détail des services applicatifs et vue d'ensemble des 22 providers |
| 🔌 **[Fiches Détaillées par Provider](./documentation/providers/)** | Documentation dédiée pour chacun des providers (`deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`, `loverslab`, `curseforge`, etc.) |
| 🧩 **[Résolution & Classification des Dépendances](./documentation/dependency_classification_and_noise.md)** | Priorité aux sites officiels, déduplication inter-plateformes, filtrage du bruit et signalement aux créateurs |
| 🌐 **[Référence API REST](./documentation/api_reference.md)** | Endpoints FastAPI, schémas Pydantic v2 et streaming NDJSON |
| 🤖 **[Guide Normalisé pour Agents LLM (`AGENTS.md`)](./AGENTS.md)** | Contrat d'implémentation d'un provider et les 7 familles de tests obligatoires |

---

## 📄 Licence

Distribué sous licence **GNU GPL v3**. Voir [LICENSE](./LICENSE).

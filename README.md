# 💎 SIMS 4 Mods Manager

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Site%20Vitrine%20%26%20Doc-00E676?logo=github)](https://pleasurecreator610-boop.github.io/SIMS4-Mods-Manager/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-477%20passed-success.svg)](./tests)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20%2B%203--Tier%20POO-purple.svg)](./documentation/architecture.md)
[![Providers](https://img.shields.io/badge/providers-22%20plateformes-orange.svg)](./documentation/providers/README.md)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](./LICENSE)

Gestionnaire de mods moderne, automatisé et haute performance pour **Les Sims 4** (Windows & Serveurs).  
Il fédère **22 plateformes de mods** dans un catalogue unifié, résout automatiquement les dépendances en cascade en privilégiant **les sites officiels des frameworks**, et inspecte les conflits binaires `.package` (`DBPF`).

👉 **[Découvrir le Site Vitrine & la Documentation Interactive (GitHub Pages)](https://pleasurecreator610-boop.github.io/SIMS4-Mods-Manager/)**

---

## ✨ Points Forts en un Coup d'Œil

| Fonctionnalité | Description | Documentation Dédiée |
| :--- | :--- | :--- |
| 🌐 **Catalogue Unifié (22 Plateformes)** | Recherche plein texte `SQLite FTS5` et filtres indexés (`mod_type`) sur 5 portails officiels, 12 catalogues SFW et 5 portails adultes (`+18` masqués par défaut). | [🔌 Index des 22 Plateformes](./documentation/providers/README.md) |
| 🛡️ **Priorité aux Sites Officiels** | Toute dépendance vers **MCCC (`deaderpool`)**, **XML Injector (`scumbumbo`)**, **RPO / Mood Pack (`lumpinou`)**, **WickedWhims (`wickedcc`)**, **Basemental** ou **Pose Player (`sims4studio`)** est téléchargée depuis son site officiel sans compte. | [🧩 Dépendances & Priorités](./documentation/dependency_classification_and_noise.md) |
| 🔄 **Déduplication & Filtrage du Bruit** | Empreinte canonique inter-plateformes (`title_fingerprint`), mutualisation des téléchargements concurrents et filtrage automatique `MOD` vs `COMMENT_NOISE`. | [✨ Guide des Fonctionnalités](./documentation/features.md) |
| 📢 **Signalement aux Créateurs** | Envoi de commentaire ou MP standardisé à l'auteur en cas de prérequis manquant, avec vérification anti-doublon et authentification guidée. | [✨ Guide des Fonctionnalités](./documentation/features.md#4-signalement--interpellation-des-createurs-commentaires--mp) |
| ⚔️ **Détecteur de Conflits DBPF (`mmap`)** | Analyse zero-copy des ressources `TGI` (`Tuning`, `SimData` vs traductions `STBL`) avec cache SQLite incrémental. | [🏛️ Architecture & DBPF](./documentation/architecture.md#4-analyse-binaire-dbpf-mmap-zero-copy--conflits) |
| 📦 **Règle `.ts4script` & Rollback ZIP** | Aplatissement automatique des scripts `.ts4script` (profondeur ≤ 1), activation `.disabled` en 1 clic et sauvegarde ZIP avant mise à jour. | [✨ Guide des Fonctionnalités](./documentation/features.md#5-installation-securisee-regle-ts4script--rollback-de-mise-a-jour) |

---

## 🚀 Démarrage Rapide (3 Commandes)

```powershell
# 1. Installer le gestionnaire de paquets Python uv (via Scoop)
scoop install uv

# 2. Synchroniser l'environnement et installer le navigateur headless Chromium
uv sync
uv run playwright install chromium

# 3. Lancer l'application de bureau (PySide6 + API FastAPI locale)
uv run python run.py
```

> **Mode Serveur API autonome** : `uv run python run.py --server --port 8000`

---

## 📚 Index de la Documentation

L'ensemble de la documentation est structuré par domaine pour une lecture directe et rapide :

### 1. Découverte & Utilisation

- 🌟 **[Site Vitrine & Portail Documentaire (`documentation/index.md`)](./documentation/index.md)** : Présentation visuelle aux couleurs des Sims 4 et navigation générale.
- ✨ **[Guide Complet des Fonctionnalités (`documentation/features.md`)](./documentation/features.md)** : Explication détaillée de chaque écran et mécanisme métier.
- 🌍 **[Internationalisation 5 Langues (`documentation/i18n.md`)](./documentation/i18n.md)** : Fonctionnement du moteur multilingue (`fr`, `en`, `es`, `zh`, `hi`).

### 2. Plateformes de Mods (`22 Providers`)

- 🔌 **[Catalogue & Comparatif des 22 Plateformes (`documentation/providers/README.md`)](./documentation/providers/README.md)**
  - **Frameworks Officiels (Sans Compte)** : [Deaderpool (MCCC)](./documentation/providers/deaderpool.md) • [Scumbumbo](./documentation/providers/scumbumbo.md) • [Lumpinou](./documentation/providers/lumpinou.md) • [Wicked.cc](./documentation/providers/wickedcc.md) • [Basemental](./documentation/providers/basemental.md)
  - **Catalogues & Créateurs SFW** : [CurseForge](./documentation/providers/curseforge.md) • [The Sims Resource](./documentation/providers/thesimsresource.md) • [ModTheSims](./documentation/providers/modthesims.md) • [Nexus Mods](./documentation/providers/nexusmods.md) • [Patreon](./documentation/providers/patreon.md) • [SimsFinds](./documentation/providers/simsfinds.md) • [Maxis Match CC World](./documentation/providers/mmccworld.md) • [SimFileShare](./documentation/providers/simfileshare.md) • [Sims 4 Studio](./documentation/providers/sims4studio.md) • [GameBanana](./documentation/providers/gamebanana.md) • [The Sims Catalog](./documentation/providers/thesimscatalog.md) • [itch.io](./documentation/providers/itchio.md) • [LittleMsSam](./documentation/providers/littlemssam.md) • [SixamCC](./documentation/providers/sixamcc.md)
  - **Portails Adultes (`+18`)** : [LoversLab](./documentation/providers/loverslab.md) • [NSFWMods](./documentation/providers/nsfwmods.md) • [Synthira.ru](./documentation/providers/synthira.md) • [F95zone](./documentation/providers/f95zone.md) • [SmutBase](./documentation/providers/smutbase.md)

### 3. Architecture Technique, Base de Données & API

- 🏛️ **[Architecture Logicielle & Optimisations BDD (`documentation/architecture.md`)](./documentation/architecture.md)** : Clean Architecture, POO 3-Tiers (`Orchestrator` → `Coordinator` → `Actions`), SQLite WAL/FTS5, `title_fingerprint`, `mod_type` et sécurité `AES-256-GCM`.
- 📊 **[Modules, Classes & Modèle de Données (`documentation/modules_and_classes.md`)](./documentation/modules_and_classes.md)** : Diagrammes de classes UML et séquences d'exécution.
- 📐 **[Architecture Decision Records (`documentation/adr/index.md`)](./documentation/adr/index.md)** : Historique des décisions d'architecture (ADR 0001 à 0005).
- 🌐 **[Référence API REST (`documentation/api_reference.md`)](./documentation/api_reference.md)** & **[Spécification FastAPI (`documentation/api/REST_API.md`)](./documentation/api/REST_API.md)**.

### 4. Qualité, Tests & Contribution IA

- 🤖 **[Guide Normalisé pour Agents LLM (`AGENTS.md`)](./AGENTS.md)** : Contrat d'intégration d'un provider, règles de priorité officielle et matrice des **7 familles de tests obligatoires**.

---

## 🧪 Commandes de Vérification Rapide

```powershell
# Exécuter une suite de tests unitaires ciblée
uv run pytest tests/unit/database -v
uv run pytest tests/unit/providers -v
uv run pytest tests/e2e -v

# Vérifier le typage statique (Mypy) et le linter (Ruff)
uv run mypy
ruff check src tests
```

---

## 📄 Licence

Distribué sous licence **GNU GPL v3**. Voir [LICENSE](./LICENSE).

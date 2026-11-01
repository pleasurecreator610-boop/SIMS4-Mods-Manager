# SIMS 4 Mods Manager - Documentation Technique

Bienvenue sur la documentation officielle de **SIMS 4 Mods Manager**.

Cette application de bureau moderne permet d'explorer, installer, mettre à jour, résoudre les dépendances en cascade et diagnostiquer les conflits binaires DBPF pour **Les Sims 4**, en fédérant **22 plateformes de mods** (portails officiels de frameworks, catalogues communautaires SFW et portails adultes `+18`).

---

## 🏛️ Principes Clés d'Architecture

1. **Clean Architecture & Modèle POO 3-Tiers** :
   - **Tier 1 (`*_orchestrator.py`)** : Façades par domaine appelées par les routeurs FastAPI.
   - **Tier 2 (`*_coordinator.py`)** : Séquençage, boucles, téléchargements parallèles et suivi `SyncTracker`.
   - **Tier 3 (`*_actions.py`)** : Actions atomiques sans état (I/O, règles `.ts4script`, parsing DBPF, requêtes SQL).
2. **Découplage Total UI $\leftrightarrow$ Backend** :
   - L'interface PySide6 communique exclusivement via `ApiClient` avec l'API REST FastAPI (aucun accès SQLite direct depuis l'UI).
3. **Priorité Absolue aux Sites Officiels des Frameworks (`SPECIAL_DEPENDENCY_CASES`)** :
   - Les dépendances vers **Deaderpool (MCCC)**, **Scumbumbo (XML Injector)**, **Lumpinou (RPO, Mood Pack, Toolbox)**, **Wicked.cc (WickedWhims / WonderfulWhims)**, **Basemental** et **Sims 4 Studio (Andrew's Pose Player)** sont systématiquement résolues et téléchargées depuis leurs sites officiels, sans compte requis.
4. **Déduplication Inter-Plateformes & Concurrence** :
   - `ModMatcher.canonical_fingerprint` identifie un même mod à travers plusieurs plateformes pour éviter toute réinstallation ou collision.
   - `ActiveInstallationRegistry` mutualise en temps réel les téléchargements de dépendances partagées lors d'installations multiples simultanées.

---

## 🧭 Sommaire de la Documentation

### 1. Architecture & Modélisation
- **[Architecture Logicielle Unifiée](architecture.md)** : Diagrammes Mermaid des couches, modèle 3-Tiers POO, concurrence (`ThreadPoolManager`, `QThreadPool`), parser binaire DBPF `mmap` et sécurité.
- **[APIs Internes & Contrats Back-to-Back](architecture/INTERNAL_APIS.md)** : Interfaces `Repository` et contrats inter-couches.
- **[Modules, Classes & Schéma de Données](modules_and_classes.md)** : Diagrammes de classes, tables SQLite WAL + FTS5 et séquences d'exécution.
- **[Architecture Decision Records (ADR)](adr/index.md)** : Décisions d'architecture structurantes (Clean Architecture, SQLite WAL, AES-256-GCM, Anti-Zip-Bomb & SSRF, Moteurs mutualisés IPS4 & Portails).

### 2. Services Métier & Résolution des Dépendances
- **[Services Applicatifs & Vue d'Ensemble des Providers](services_and_providers.md)**
- **[Résolution des Dépendances, Priorité Officielle & Filtrage du Bruit](dependency_classification_and_noise.md)**
- **[Internationalisation Dynamique (i18n)](i18n.md)**

### 3. Documentation Détaillée par Provider (22 Plateformes)
- **Frameworks Officiels (Sans Compte)** :
  - [Deaderpool — MCCC & MC WooHoo](providers/deaderpool.md)
  - [Scumbumbo — XML Injector & Utilitaires](providers/scumbumbo.md)
  - [Lumpinou — RPO, Mood Pack & Toolbox](providers/lumpinou.md)
  - [Wicked.cc — WickedWhims & WonderfulWhims](providers/wickedcc.md)
  - [Basemental — Drugs, Gangs & Universal Venue List](providers/basemental.md)
- **Catalogues Communautaires & Créateurs SFW** :
  - [CurseForge](providers/curseforge.md) • [The Sims Resource (TSR)](providers/thesimsresource.md) • [ModTheSims](providers/modthesims.md) • [Nexus Mods](providers/nexusmods.md) • [Patreon](providers/patreon.md) • [SimsFinds](providers/simsfinds.md) • [Maxis Match CC World](providers/mmccworld.md) • [SimFileShare](providers/simfileshare.md) • [Sims 4 Studio](providers/sims4studio.md) • [GameBanana](providers/gamebanana.md) • [The Sims Catalog](providers/thesimscatalog.md) • [itch.io](providers/itchio.md) • [LittleMsSam](providers/littlemssam.md) • [SixamCC](providers/sixamcc.md)
- **Portails Adultes (`+18`)** :
  - [LoversLab](providers/loverslab.md) • [NSFWMods](providers/nsfwmods.md) • [Synthira.ru](providers/synthira.md) • [F95zone](providers/f95zone.md) • [SmutBase](providers/smutbase.md)

### 4. API REST & Standards Agents LLM
- **[Spécification Complète REST API](api/REST_API.md)** & **[Référence des Endpoints](api_reference.md)**
- **[Guide Normalisé pour Agents LLM (`AGENTS.md`)](../AGENTS.md)** : Contrat d'ajout de provider et matrice des 7 familles de tests obligatoires.

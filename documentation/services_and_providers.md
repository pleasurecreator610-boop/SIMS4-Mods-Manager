# Services Applicatifs Métier & Fournisseurs Externes (22 Providers)

Ce document détaille le fonctionnement interne de la couche **Application (`src/application/`)** et du système de **Plugins Fournisseurs (`src/providers/` & `plugins/`)**.

---

## 🛠️ 1. Services Métier Applicatifs (`src/application/`)

La couche applicative encapsule tous les cas d'utilisation selon le modèle **POO 3-Tiers** (`Orchestrators` $\rightarrow$ `Coordinators` $\rightarrow$ `Actions`).

### 1.1 Domaine Catalogue & Synchronisation (`src/application/catalog/`)
- **`CatalogOrchestrator`** : Façade d'entrée pour la synchronisation multi-plateformes, la recherche plein texte `FTS5` et l'inspection de fiches de mods.
- **`CatalogSyncCoordinator`** :
  - Orchestre le scraping parallèle des **22 plateformes** enregistrées dans `ProviderRegistry`.
  - Maintient l'état temps réel par fournisseur dans `SyncTracker` (`status`, `current_page`, `total_pages`, `scraped_count`, `subcategories`).
  - Applique un backoff exponentiel en cas de ralentissement réseau et respecte `ShutdownManager.is_shutting_down()`.
- **`CatalogSyncActions`** : Persistance atomique `UPSERT` dans SQLite et normalisation des dates et tags.

### 1.2 Domaine Mods : Installation, Déduplication Concurrente & Règle `.ts4script` (`src/application/mods/`)
- **`ModOrchestrator`**, **`ModInstallCoordinator`** & **`ModInstallActions`** :
  - **Déduplication Concurrente (`ActiveInstallationRegistry`)** : Lorsque l'utilisateur lance l'installation simultanée de plusieurs mods partageant une dépendance commune (ex. *XML Injector* ou *WickedWhims*), un seul thread télécharge et installe la dépendance tandis que les autres attendent sa complétion.
  - **Règle d'or `.ts4script` (Profondeur $\le 1$)** : Les scripts Python compilés `.ts4script` sont automatiquement remontés dans `Mods/<NomDuMod>/script.ts4script` pour garantir leur prise en compte par le moteur C++ des Sims 4.
  - **Validation Binaire DBPF & Rejet HTML** : Vérifie la signature binaire des archives et des fichiers `.package`, et bloque toute page HTML d'erreur ou de login déguisée en téléchargement.
- **`ModUpdateCoordinator` & `ModUpdateActions`** : Compare les versions installées aux catalogues distants et crée une sauvegarde ZIP de rollback (`.sims4_mod_manager/backups/`) avant toute mise à jour.
- **`ModToggleCoordinator` & `ModToggleActions`** : Active ou désactive un mod de manière non destructive via le suffixe `.disabled`.

### 1.3 Domaine Dépendances & Interception Officielle (`src/application/dependencies/`)
- **`DependencyOrchestrator`**, **`DependencyCoordinator`** & **`DependencyActions`** :
  - **Interception Prioritaire (`SPECIAL_DEPENDENCY_CASES`)** : Toute dépendance vers *MC Command Center* (`deaderpool`), *XML Injector* (`scumbumbo`), *RPO / Mood Pack / Toolbox* (`lumpinou`), *WickedWhims / WonderfulWhims* (`wickedcc`), *Basemental* (`basemental`) ou *Andrew's Pose Player* (`sims4studio`) est résolue en priorité absolue sur son site officiel public.
  - **Déduplication Inter-Plateformes (`ModMatcher`)** : Détecte si un mod requis depuis une plateforme A a déjà été installé depuis une plateforme B grâce à son empreinte canonique (`ModMatcher.canonical_fingerprint`).
- **`RequirementReporterService`** : Gère la vérification anti-doublon en direct sur la page du mod, la rédaction du message en anglais standardisé, l'envoi de commentaire ou de message privé (MP) et la suppression de commentaire sur les 13 plateformes supportant l'authentification membre.

---

## 🌐 2. Architecture des 22 Providers (`src/providers/` & `plugins/`)

Tous les connecteurs héritent de `BaseSourceProvider` et sont découverts automatiquement au démarrage par `ProviderRegistry.discover_plugins()` via le décorateur `@register_provider`.

### 2.1 Socles Mutualisés (`src/providers/common/`)
1. **`BaseIPSForumProvider` (`src/providers/common/ips_base.py`)** :
   - Moteur mutualisé pour les forums propulsés par *Invision Community (IPS4)* : **`loverslab`** et **`nsfwmods`**.
   - Gère le scraping multi-catégories, la résolution des confirmations `?do=download&confirm=1`, l'extraction des galeries et les commentaires/MP IPS4.
2. **`BasePortalProvider` (`src/providers/common/portal_base.py`)** :
   - Moteur mutualisé pour les portails officiels de frameworks, les catalogues communautaires et les sites de créateurs :
     - **5 Portails Officiels de Frameworks** : `deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`.
     - **6 Catalogues & Portails SFW** : `gamebanana` (API JSON Core v11 + fallback HTML), `thesimscatalog`, `itchio`, `sims4studio`, `littlemssam`, `sixamcc`.
     - **3 Portails Adultes (`+18`)** : `synthira`, `f95zone`, `smutbase`.

### 2.2 Récapitulatif des 22 Plateformes
Consultez la fiche technique dédiée à chaque provider dans [`documentation/providers/`](./providers/) :
- **Frameworks Officiels** : [Deaderpool](providers/deaderpool.md) • [Scumbumbo](providers/scumbumbo.md) • [Lumpinou](providers/lumpinou.md) • [Wicked.cc](providers/wickedcc.md) • [Basemental](providers/basemental.md)
- **Catalogues SFW** : [CurseForge](providers/curseforge.md) • [The Sims Resource](providers/thesimsresource.md) • [ModTheSims](providers/modthesims.md) • [Nexus Mods](providers/nexusmods.md) • [Patreon](providers/patreon.md) • [SimsFinds](providers/simsfinds.md) • [MMCCWorld](providers/mmccworld.md) • [SimFileShare](providers/simfileshare.md) • [Sims 4 Studio](providers/sims4studio.md) • [GameBanana](providers/gamebanana.md) • [The Sims Catalog](providers/thesimscatalog.md) • [itch.io](providers/itchio.md) • [LittleMsSam](providers/littlemssam.md) • [SixamCC](providers/sixamcc.md)
- **Portails Adultes (`+18`)** : [LoversLab](providers/loverslab.md) • [NSFWMods](providers/nsfwmods.md) • [Synthira](providers/synthira.md) • [F95zone](providers/f95zone.md) • [SmutBase](providers/smutbase.md)

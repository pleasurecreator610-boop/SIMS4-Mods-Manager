# Services Applicatifs Métier & Fournisseurs Externes (Providers)

Ce document détaille le fonctionnement interne de la couche **Application (`src/application/`)** et de la couche **Providers (`src/providers/`)**.

---

## 🛠️ 1. Services Métier Applicatifs (`src/application/`)

La couche applicative encapsule l'ensemble des cas d'utilisation métier selon le modèle **POO 3-Tiers** (Orchestrators $\to$ Coordinators $\to$ Actions). Elle est totalement indépendante du protocole HTTP (FastAPI) et de l'interface graphique (PySide6).

### 1.1 Domaine Catalogue & Synchronisation (`src/application/catalog/`)
- **`CatalogOrchestrator`** (`catalog_orchestrator.py`) : Point d'entrée pour la synchronisation et le statut du catalogue.
- **`CatalogSyncCoordinator`** (`catalog_sync_coordinator.py`) :
  - Orchestre le scraping en tâche de fond des catégories LoversLab via un pool de threads dédié.
  - Gère les 14 catégories actives (WickedWhims, Animations, Clothing, Objects...).
  - Applique un backoff exponentiel (`2s * 2^attempt`) en cas de ralentissement réseau pour éviter les bannissements d'adresse IP.
  - Pilote l'instance thread-safe `SyncTracker` avec verrou mutex (`threading.Lock()`) maintenant le pourcentage global, pages complétées et état en direct.
  - Vérifie systématiquement `ShutdownManager.is_shutting_down()` et `SyncTracker.stop_requested` pour un arrêt gracieux instantané.
- **`CatalogSyncActions`** (`catalog_sync_actions.py`) :
  - Normalisation des chaînes et conversion des dates multiformats.
  - Persistance unitaire en base de données SQLite via `DatabaseManager`.

---

### 1.2 Domaine Mods : Installation & Règle Critique `.ts4script` (`src/application/mods/`)
- **`ModOrchestrator`** (`mod_orchestrator.py`) : Façade d'installation, mise à jour et activation/désactivation.
- **`ModInstallCoordinator`** (`mod_install_coordinator.py`) : Coordonne la chaîne d'installation en cascade des dépendances puis du mod principal.
- **`ModInstallActions`** (`mod_install_actions.py`) :
  - **Règle d'or du moteur des Sims 4** :
    - Les fichiers `.package` peuvent être imbriqués jusqu'à **5 sous-dossiers** de profondeur (grâce à la directive `PackedFile */*/*/*/*.package` de `Resource.cfg`).
    - Les fichiers de script Python compilés **`.ts4script` NE DOIVENT PAS être situés à plus de 1 niveau de profondeur** (`Mods/<DossierDuMod>/script.ts4script`).
  - **Correction Automatique de Profondeur** :
    Si une archive contient des fichiers `.ts4script` logés dans des arborescences profondes (ex. `Archive/Sub/Deep/script.ts4script`), l'action les remonte automatiquement à la racine du dossier du mod (`Mods/nom_du_mod/script.ts4script`).
  - **Validation Binaire DBPF** : Vérifie l'en-tête binaire (`DBPF` magic header) des fichiers `.package` pour détecter les téléchargements corrompus ou les pages HTML déguisées.

---

### 1.3 Domaine Mods : Mises à Jour & Rollback (`src/application/mods/`)
- **`ModUpdateCoordinator`** (`mod_update_coordinator.py`) :
  - Analyse comparative de version : un mod installé est obsolète si `updated_date` sur le catalogue est postérieure à `version_date`, ou si `version_str` diffère.
  - Gère les mises à jour unitaires et les traitements par lot (`coordinate_batch_update`).
- **`ModUpdateActions`** (`mod_update_actions.py`) :
  - **Sauvegarde Automatique de Rollback** : Avant toute mise à jour ou écrasement de dossier, compresse le dossier existant dans un fichier ZIP d'archive (`.sims4_mod_manager/backups/`). En cas d'échec de téléchargement ou d'extraction, l'ancienne version est restaurée automatiquement.

---

### 1.4 Domaine Mods : Activation / Désactivation Propre (`src/application/mods/`)
- **`ModToggleCoordinator`** & **`ModToggleActions`** :
  - **Principe Non-Destructif** : Permet de désactiver un mod sans le supprimer du disque, évitant ainsi de devoir le re-télécharger.
  - **Mécanisme d'Extension `.disabled`** :
    - Désactivation : renomme tous les fichiers `.package` $\rightarrow$ `.package.disabled` et `.ts4script` $\rightarrow$ `.ts4script.disabled`. Le moteur de jeu ignore totalement ces extensions.
    - Activation : retire l'extension `.disabled` pour rétablir les noms de fichiers originaux.
  - **Synchronisation BDD** : Met à jour le statut `is_enabled` dans la table `installed_mods`.

---

### 1.5 Domaine Dépendances & Prérequis (`src/application/dependencies/`)
- **`DependencyOrchestrator`** (`dependency_orchestrator.py`) : Façade d'analyse de dépendances et de signalement.
- **`DependencyResolutionCoordinator`** (`dependency_resolution_coordinator.py`) :
  Catégorise chaque prérequis d'un mod dans l'un des **4 statuts stricts** :

| Statut | Signification | Comportement UI |
| :--- | :--- | :--- |
| `INSTALLED` | Présent dans le dossier `Mods/` | Badge vert, prêt |
| `DETECTED_NOT_INSTALLED` | Présent dans le catalogue mais pas encore installé | Badge bleu, téléchargeable en 1 clic |
| `NOT_DETECTED_SCANNING` | Non trouvé, mais le scraping catalogue est toujours en cours | Badge orange animé "Scan en cours..." |
| `NOT_DETECTED_FINISHED` | Non trouvé et le catalogue a fini d'être parcouru | Badge rouge "Non trouvé" (lien externe ou mod tiers) |

- **`DependencyNormalizer`** (`dependency_normalizer.py`) :
  - **Filtrage du Bruit & Commentaires** : Les phrases narratives, consignes du jeu (*"Script Mods Allowed"*, *"Game Options"*) et disclaimers d'absence de prérequis sont automatiquement classés en `COMMENT_NOISE`.
  - **Table de Correspondance pour Cas Spécifiques (`SPECIAL_DEPENDENCY_CASES`)** : Seul **WickedWhims** fait l'objet d'un cas spécifique répertorié dans la table de correspondance avec son URL fixe (`https://www.loverslab.com/files/file/3169-wickedwhims/`), son ID `3169` et ses alias (`WW`, `ww`, `Wicked-Whims`, `wicked_whims`).
- **`RequirementReportCoordinator`** & **`RequirementReportActions`** :
  - Génère des rapports structurés pour signaler les liens brisés ou prérequis introuvables sur les forums LoversLab.

---

### 1.6 Domaine Jeu & Système (`src/application/game/`)
- **`GameDetector`** :
  - Détection multi-langues du dossier Sims 4 (Français, Anglais, Allemand, Espagnol) avec gestion des dossiers OneDrive et espaces insécables (`\u00a0`).
  - Vérification et génération automatique du fichier standard `Resource.cfg` (support de 5 niveaux de sous-dossiers).
- **`GameLauncher`** :
  - Détection des clés de registre Windows et de la bibliothèque Steam pour repérer `TS4_x64.exe` et lancer le jeu avec supervision.

---

## 🌐 2. Fournisseurs de Contenu (`src/providers/`)

### 2.1 LoversLab (`src/providers/loverslab/`)
- **`parsers.py`** :
  - Fonctions pures de parsing HTML BeautifulSoup complètement découplées des couches réseau.
  - `extract_gallery_screenshots(soup, base_url)` : extrait les URLs d'images haute résolution des carrousels, lightboxes et miniatures.
  - `sanitize_description_html(content_elem, base_url)` : nettoie les scripts, changelogs, styles d'auteurs et résout les URLs absolues.
- **`scraper.py`** :
  - Orchestre les requêtes HTTP avec le pool de sessions `SessionManager`.
  - Parcourt les 14 sous-catégories LoversLab avec pagination intelligente.
- **`downloader.py`** :
  - Évalue les candidats de téléchargement : priorise les archives directes (`.zip`, `.package`) avec taille en Mo/Go sur les liens externes.
  - Résout les pages de confirmation multi-étapes d'Invision Power Board (`?do=download&confirm=1`).
  - Détecte les hébergeurs tiers (Mega, MediaFire, Google Drive, SimFileShare) et informe l'utilisateur si un téléchargement automatisé direct est impossible.

### 2.2 Patreon (`src/providers/patreon/`)
- **`provider.py`** :
  - Interroge l'API interne Patreon (`/api/posts/{post_id}`) à l'aide de la session authentifiée `curl_cffi`.
  - Analyse l'accessibilité : `PUBLIC`, `UNLOCKED` (débloqué par l'abonnement en cours) ou `LOCKED` (nécessite un tier payant, affichage du montant mensuel).
  - **Rejet des Faux Liens de Téléchargement** : Filtre les pièces jointes pour rejeter les simples images de couverture (`.png`, `.jpg`) et sélectionner exclusivement les archives Sims 4.

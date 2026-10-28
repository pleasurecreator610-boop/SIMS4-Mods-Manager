# Schémas de Liaisons et Diagrammes de Classes

Ce document détaille les relations, contrats d'interface et flux d'interaction entre les différentes classes et modules de **SIMS 4 Mods Manager**, structurés selon l'architecture **POO 3-Tiers**.

---

## 📊 1. Modèle de Données (ORM SQLAlchemy)

```mermaid
classDiagram
    class CatalogMod {
        +int id
        +string source
        +string remote_id
        +string title
        +string author
        +string category
        +string page_url
        +string thumbnail_url
        +datetime published_date
        +datetime updated_date
        +string version_str
        +string patreon_status
        +string patreon_tier
        +string requirements_text
        +string requirements_status
        +string requirements_mods_json
        +get_tags_list() List~str~
        +get_download_urls_list() List~dict~
        +get_requirements_mods_list() List~dict~
    }

    class InstalledMod {
        +int id
        +int catalog_mod_id
        +string source
        +string remote_id
        +string title
        +string folder_name
        +string installed_files
        +datetime installed_date
        +datetime version_date
        +string version_str
        +bool is_enabled
        +get_installed_files_list() List~str~
        +set_installed_files_list(files)
    }

    class AccountSession {
        +string provider
        +string cookies_json
        +string user_agent
        +datetime last_authenticated
        +string user_identifier
        +bool is_valid
        +get_cookies_dict() dict
    }

    class AppSettings {
        +int id
        +string key
        +string value
        +datetime updated_at
    }

    CatalogMod "0..1" <-- "0..*" InstalledMod : catalog_mod_id
```

---

## ⚙️ 2. Architecture 3-Tiers POO (`src/application/`)

```mermaid
classDiagram
    %% Tier 1 : Orchestrators
    class CatalogOrchestrator {
        +sync_catalog(max_pages, categories)
        +get_sync_status() CatalogSyncStatusResponse
        +check_dependencies(title, page_url, source)
    }

    class ModOrchestrator {
        +install_mod(payload, progress_cb) CatalogInstallResponse
        +update_mod(installed_id) Tuple~bool, str~
        +update_all_mods() Tuple~int, int~
        +toggle_mod(installed_id, state) Tuple~bool, str~
        +scan_and_sync_installed_mods()
    }

    class DependencyOrchestrator {
        +resolve_dependencies(reqs, session) List~DependencyItem~
        +generate_report(mod_title, page_url) str
    }

    %% Tier 2 : Coordinators
    class CatalogSyncCoordinator {
        +SyncTracker tracker
        +execute_sync(max_pages, categories)
    }

    class ModInstallCoordinator {
        +coordinate_install(payload, progress_cb) CatalogInstallResponse
    }

    class ModUpdateCoordinator {
        +coordinate_update(installed_id) Tuple~bool, str~
        +coordinate_batch_update(ids) Tuple~int, int~
    }

    class ModToggleCoordinator {
        +coordinate_toggle(installed_id, state) Tuple~bool, str~
    }

    class DependencyResolutionCoordinator {
        +coordinate_resolution(requirements) List~DependencyItem~
    }

    %% Tier 3 : Actions
    class CatalogSyncActions {
        +persist_catalog_mod(mod_data, session)
        +normalize_dates(raw_date) datetime
    }

    class ModInstallActions {
        +download_archive(url, dest, progress_cb)
        +extract_and_enforce_ts4script(archive_path, dest_dir)
        +validate_dbpf_headers(folder_path) bool
    }

    class ModUpdateActions {
        +create_rollback_backup(folder_path) Path
        +restore_backup_on_failure(backup_zip, target_folder)
    }

    class ModToggleActions {
        +apply_disabled_extension(folder_path)
        +remove_disabled_extension(folder_path)
    }

    class DependencyResolutionActions {
        +find_mod_in_catalog_or_disk(name) Optional~CatalogMod~
        +classify_requirement_status(mod_entity) RequirementStatus
    }

    %% Liaisons Tier 1 -> Tier 2
    CatalogOrchestrator --> CatalogSyncCoordinator
    ModOrchestrator --> ModInstallCoordinator
    ModOrchestrator --> ModUpdateCoordinator
    ModOrchestrator --> ModToggleCoordinator
    DependencyOrchestrator --> DependencyResolutionCoordinator

    %% Liaisons Tier 2 -> Tier 3
    CatalogSyncCoordinator --> CatalogSyncActions
    ModInstallCoordinator --> ModInstallActions
    ModUpdateCoordinator --> ModUpdateActions
    ModToggleCoordinator --> ModToggleActions
    DependencyResolutionCoordinator --> DependencyResolutionActions
```

---

## 🔌 3. Couche Fournisseurs Externes (Providers)

```mermaid
classDiagram
    class BaseSourceProvider {
        <<Abstract>>
        +string provider_name
        +string display_name
        +string base_url
        +scrape_catalog(page, limit)* List~dict~
        +get_mod_details(mod_url)* dict
        +download_mod_file(download_url, dest, progress_cb)* Tuple~bool, str~
        +check_access(mod_data)* str
    }

    class LoversLabProvider {
        +CATEGORIES List~dict~
        +scrape_category_page(category, page) Tuple~List, int~
        +get_mod_details(mod_url) dict
        +download_mod_file(download_url, dest, progress_cb) Tuple~bool, str~
    }

    class LoversLabScraper {
        +scrape_category(category_id, page) List~dict~
        +parse_mod_page(html) dict
        +extract_requirements(html) Tuple
    }

    class LoversLabDownloader {
        +extract_download_candidates(soup, base_url) List~dict~
        +download_loverslab_file(url, dest, patreon_provider, progress_cb) Tuple
    }

    class PatreonProvider {
        +extract_post_id(url) str
        +check_post_access(post_url) dict
        +download_mod_file(url, dest, progress_cb) Tuple
    }

    class ProviderRegistry {
        <<Singleton>>
        +get_provider(name) BaseSourceProvider
        +list_providers() List~BaseSourceProvider~
    }

    BaseSourceProvider <|-- LoversLabProvider
    BaseSourceProvider <|-- PatreonProvider
    LoversLabProvider *-- LoversLabScraper : utilise
    LoversLabProvider *-- LoversLabDownloader : utilise
    ProviderRegistry o-- BaseSourceProvider : référence
```

---

## 🖥️ 4. Interface Graphique PySide6 & Workers Asynchrones

```mermaid
classDiagram
    class MainWindow {
        +ApiClient api_client
        +I18nManager i18n
        +setup_navigation()
        +switch_view(view_index)
        +retranslate_ui()
    }

    class ResponsiveCardGrid {
        +int card_width
        +int card_height
        +int spacing
        +set_cards(widgets)
        +recalculate_grid(container_width)
    }

    class CatalogView {
        +SyncTriggerWorker sync_worker
        +InstallWorker install_worker
        +ResponsiveCardGrid grid
        +on_search_changed()
        +on_install_clicked()
    }

    class InstalledView {
        +ResponsiveCardGrid grid
        +refresh_installed_mods()
        +on_delete_mod()
    }

    class ModDetailView {
        +FetchDetailsWorker details_worker
        +GalleryBatchWorker gallery_worker
        +load_mod(mod_id, page_url)
    }

    class SyncTriggerWorker {
        <<QThread>>
        +Signal finished_signal(bool, str)
        +run()
    }

    class InstallWorker {
        <<QThread>>
        +Signal progress(int, str, str)
        +Signal finished(bool, str)
        +run()
    }

    MainWindow *-- CatalogView
    MainWindow *-- InstalledView
    MainWindow *-- ModDetailView
    CatalogView *-- ResponsiveCardGrid
    InstalledView *-- ResponsiveCardGrid
    CatalogView ..> SyncTriggerWorker : démarre
    CatalogView ..> InstallWorker : démarre
```

---

## 🔄 5. Séquence d'Installation 3-Tiers avec Dépendances

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilisateur (PySide6)
    participant DetailView as ModDetailView
    participant ApiClient as ApiClient
    participant Router as CatalogInstallRouter (/install-stream)
    participant Orch as ModOrchestrator (Tier 1)
    participant Coord as ModInstallCoordinator (Tier 2)
    participant DepOrch as DependencyOrchestrator (Tier 1)
    participant Actions as ModInstallActions (Tier 3)
    participant DB as DatabaseManager

    User->>DetailView: Clic sur "Installer"
    DetailView->>ApiClient: install_mod_stream(payload)
    ApiClient->>Router: POST /api/catalog/install-stream
    Router->>Orch: install_mod(payload, progress_cb)
    Orch->>Coord: coordinate_install(payload, progress_cb)
    
    Coord->>DepOrch: resolve_dependencies(requirements)
    DepOrch-->>Coord: Liste des dépendances manquantes
    
    loop Pour chaque dépendance requise
        Coord->>Actions: download_archive(dep_url)
        Actions-->>Coord: dep_archive.zip
        Coord->>Actions: extract_and_enforce_ts4script(dep_archive)
        Actions->>DB: create_installed_mod(dep)
        Coord-->>Router: Event progress: "Dépendance installée"
        Router-->>ApiClient: NDJSON chunk
        ApiClient-->>DetailView: Signal progress.emit()
    end

    Coord->>Actions: download_archive(main_mod_url)
    Actions-->>Coord: main_mod.zip
    Coord->>Actions: extract_and_enforce_ts4script(main_mod)
    Actions->>DB: create_installed_mod(main_mod)
    
    Coord-->>Orch: CatalogInstallResponse(success=True)
    Orch-->>Router: Success
    Router-->>ApiClient: Event finished: success=true
    ApiClient-->>DetailView: Signal finished.emit()
    DetailView->>User: Affichage du badge "INSTALLÉ"
```

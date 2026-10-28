from typing import Optional
from pydantic import BaseModel


class SettingsResponse(BaseModel):
    """Classe SettingsResponse : assure la gestion et l'orchestration de Settingsresponse."""

    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    auto_backup: bool
    adult_content_enabled: bool
    check_updates_on_startup: bool
    theme: str
    language: str = "fr"
    max_workers: int
    detected_mods_dir: Optional[str] = None
    detected_game_exe: Optional[str] = None
    backups_dir: str
    thumbnails_cache_dir: str
    db_path: str
    app_dir: str


class SettingsUpdateRequest(BaseModel):
    """Classe SettingsUpdateRequest : assure la gestion et l'orchestration de Settingsupdaterequest."""

    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    auto_backup: Optional[bool] = None
    adult_content_enabled: Optional[bool] = None
    check_updates_on_startup: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    max_workers: Optional[int] = None


class ClearCacheResponse(BaseModel):
    """Classe ClearCacheResponse : assure la gestion et l'orchestration de Clearcacheresponse."""

    success: bool
    message: str
    deleted_count: int


class LaunchGameResponse(BaseModel):
    """Classe LaunchGameResponse : assure la gestion et l'orchestration de Launchgameresponse."""

    success: bool
    message: str


class DatabaseStatsResponse(BaseModel):
    """Classe DatabaseStatsResponse : assure la gestion et l'orchestration de Databasestatsresponse."""

    catalog_mods_count: int
    installed_mods_count: int
    db_path: str


class DatabasePurgeResponse(BaseModel):
    """Classe DatabasePurgeResponse : assure la gestion et l'orchestration de Databasepurgeresponse."""

    success: bool
    deleted_count: int
    message: str


class StorageStatsResponse(BaseModel):
    """Statistiques d'occupation de l'espace disque de l'application."""

    backups_size_bytes: int
    backups_count: int
    cache_size_bytes: int
    cache_count: int
    downloads_size_bytes: int
    downloads_count: int
    total_size_bytes: int

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def backups_size_mb(self) -> float:
        return self.backups_size_bytes / (1024 * 1024)

    @property
    def cache_size_mb(self) -> float:
        return self.cache_size_bytes / (1024 * 1024)

    @property
    def downloads_size_mb(self) -> float:
        return self.downloads_size_bytes / (1024 * 1024)


class StorageCleanupResponse(BaseModel):
    """Résultat du nettoyage de l'espace disque."""

    success: bool
    message: str
    deleted_files_count: int
    freed_bytes: int

    @property
    def freed_size_mb(self) -> float:
        return self.freed_bytes / (1024 * 1024)

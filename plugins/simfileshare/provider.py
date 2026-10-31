"""
SimFileShare Source Provider pour Sims 4 Mods Manager.
Gère la résolution de fichiers/archives et le téléchargement transparent
depuis simfileshare.net sans nécessité d'authentification utilisateur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.core.dto import ModDetailsDTO
from src.infrastructure.network.simfileshare_resolver import SimFileShareResolver
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry


@ProviderRegistry.register_provider("simfileshare")
class SimFileShareProvider(BaseSourceProvider):
    """
    Fournisseur SimFileShare (simfileshare.net).
    Hébergeur pur (CDN/Filehosting) : pas de catalogue public ni de système de commentaires.
    Permet la résolution instantanée de liens de téléchargement directs et dossiers.
    """

    provider_name: str = "simfileshare"
    display_name: str = "SimFileShare"
    base_url: str = "https://simfileshare.net"

    def __init__(self) -> None:
        self.resolver = SimFileShareResolver()

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """
        SimFileShare ne dispose pas de catalogue public explorable (cf. FAQ officielle SFS).
        Les fichiers sont partagés directement par les créateurs via leurs blogs ou réseaux.
        """
        return []

    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """
        Résout les métadonnées et le lien direct d'un fichier hébergé sur SimFileShare.
        """
        direct_url, filename, size = self.resolver.resolve_direct_download(mod_url)
        file_id = self.resolver.extract_file_id(mod_url) or "sfs_file"

        name = filename or f"SimFileShare File #{file_id}"
        dl_url = direct_url or mod_url

        return {
            "title": name,
            "version": "",
            "download_urls": [{"url": dl_url, "name": name, "size": size}],
            "external_links": [],
            "requirements": [],
            "dependencies": [],
            "author": "SimFileShare Creator",
            "is_adult": False,
        }

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Télécharge le fichier depuis SimFileShare via le résolveur haute performance.
        """
        return self.resolver.download_mod_file(
            download_url,
            dest_path,
            progress_callback=progress_callback,
        )

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """
        Sur SimFileShare, les téléchargements sont publics et ne nécessitent aucun compte (cf. FAQ).
        """
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        SimFileShare est un service d'hébergement brut et ne possède pas d'espace commentaires.
        """
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """
        Aucun système de commentaires sur SimFileShare.
        """
        return False, "SimFileShare est un hébergeur pur ne disposant pas d'espace commentaires."

    def delete_mod_comment(self, comment_id: str) -> Tuple[bool, str]:
        """
        Aucun système de commentaires sur SimFileShare.
        """
        return False, "SimFileShare ne supporte pas les commentaires."


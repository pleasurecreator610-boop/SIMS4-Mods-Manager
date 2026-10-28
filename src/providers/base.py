from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional, Callable, Union
from pathlib import Path

from src.core.dto import ModDetailsDTO


class BaseSourceProvider(ABC):
    """Abstract base class for mod source providers (LoversLab, Patreon, etc.)."""

    provider_name: str = "base"
    display_name: str = "Base Provider"
    base_url: str = ""

    @abstractmethod
    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Scrapes a page of the mod catalog and returns raw mod metadata dicts.
        """
        pass

    @abstractmethod
    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """
        Fetches full details for a specific mod page (download links, external links, version).
        """
        pass

    @abstractmethod
    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Downloads a mod file from a direct or resolved download URL.
        """
        pass

    @abstractmethod
    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """
        Checks accessibility status (e.g. PUBLIC, UNLOCKED, LOCKED).
        """
        pass

    @abstractmethod
    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Checks live on the provider's site/forum if the authenticated user has already
        posted a comment/message containing the given keywords.
        Returns (already_commented, formatted_datetime_or_snippet).
        """
        pass

    @abstractmethod
    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """
        Posts a comment or message on the mod page/forum using the authenticated member session.
        Returns (success, message_or_error).
        """
        pass

    def delete_mod_comment(self, page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Deletes a comment posted by the authenticated user on the mod page/forum.
        Returns (success, message_or_error).
        """
        return False, "Ce fournisseur ne supporte pas la suppression de commentaires."

    def get_creator_info(self, page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts creator info (member_id, member_name, profile_url) if supported by provider.
        """
        return None, None, None

    def check_user_already_sent_pm(
        self,
        creator_id: Optional[str] = None,
        creator_name: Optional[str] = None,
        mod_title: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if a private message was already sent to creator.
        """
        return False, None

    def send_private_message(
        self,
        creator_id: str,
        creator_name: str,
        subject: str,
        message: str,
    ) -> Tuple[bool, str]:
        """
        Sends a private message to the creator if supported by provider.
        """
        return False, "Ce fournisseur ne supporte pas l'envoi de messages privés."

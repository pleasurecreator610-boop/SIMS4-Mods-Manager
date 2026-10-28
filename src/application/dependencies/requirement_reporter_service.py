from typing import List, Dict, Any, Optional
from src.providers import ProviderRegistry
from src.core.session_manager import SessionManager
from src.utils.logger import logger


class RequirementReporterService:
    """
    Centralized service for generating standardized English messages and managing
    interpellation (via PM or forum) for unidentified mod requirements across all providers.
    Directly queries the provider for live duplicate prevention (zero local DB storage).
    """

    @staticmethod
    def format_author_mention(author: str) -> str:
        """Sanitizes and formats the author handle with '@'."""
        clean = (author or "Author").strip()
        if not clean:
            return "@Author"
        if not clean.startswith("@"):
            return f"@{clean}"
        return clean

    @staticmethod
    def build_english_subject(mod_title: str) -> str:
        """Builds a standardized subject for creator messaging."""
        title_str = mod_title.strip() if mod_title else "Mod"
        return f'[Sims 4 Mods Manager] Requirements feedback for "{title_str}"'

    @classmethod
    def build_english_message(
        cls,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
    ) -> str:
        """
        Builds a polite, professional, and well-structured English message introducing
        Sims 4 Mods Manager and detailing missing dependencies and unnecessary comments.
        """
        mention = cls.format_author_mention(author)
        title_str = mod_title.strip() if mod_title else "this mod"

        clean_missing = [m.strip() for m in (missing_modules or []) if m and m.strip()]
        clean_unnecessary = [m.strip() for m in (unnecessary_modules or []) if m and m.strip()]

        intro = (
            f"Hi {mention},\n\n"
            f'I am reaching out regarding your mod "{title_str}".\n'
            f'Our community uses "Sims 4 Mods Manager" (an open-source application for The Sims 4 that automates mod management, dependency resolution, and conflict checking).\n\n'
            f"To help players properly locate and install the prerequisites for your mod, we analyzed the Requirements section on your mod page and noticed the following points:"
        )

        sections = []

        if clean_missing:
            items_str = "\n".join(f"- {m}" for m in clean_missing)
            sections.append(
                f"📦 Unresolved / Missing Dependencies:\n"
                f"The following required module(s) could not be identified or matched in our catalog:\n"
                f"{items_str}\n\n"
                f"👉 Could you please check or clarify the exact file name, version, or link for these requirements so that players and mod managers can locate and install them properly?"
            )

        if clean_unnecessary:
            items_str = "\n".join(f"- {m}" for m in clean_unnecessary)
            sections.append(
                f"🧹 Notes / Instructions to clean from Requirements:\n"
                f"The following item(s) are listed under Requirements but appear to be gameplay instructions or general comments rather than mod files:\n"
                f"{items_str}\n\n"
                f"👉 Could you please remove these comments from the Requirements section to ensure a clean dependency list and avoid false detection warnings in automated tools?"
            )

        if not sections:
            sections.append(f'Could you please review the Requirements section for "{title_str}"?')

        explanation = (
            "Why is this helpful?\n"
            "Sims 4 Mods Manager automatically scans mod requirement lists to notify players when prerequisite packages are missing from their game. Keeping the Requirements list strictly limited to real dependency mods (with recognizable names or direct links) helps thousands of players avoid missing files, broken animations, or false-positive errors."
        )

        closing = (
            "Thank you very much for your wonderful work and creations!\n\nBest regards,\nA Sims 4 Mods Manager user"
        )

        body = "\n\n".join(sections)
        return f"{intro}\n\n{body}\n\n{explanation}\n\n{closing}"

    @classmethod
    def check_report_status(
        cls,
        source: str,
        page_url: str,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Checks live on the provider's site whether the user has already contacted
        the creator or posted about this mod and these requirements.
        Also resolves creator profile info and compose PM URL.
        """
        clean_author = cls.format_author_mention(author)
        missing_mods = missing_modules or []
        unnecessary_mods = unnecessary_modules or []
        formatted_message = cls.build_english_message(mod_title, author, missing_mods, unnecessary_mods)
        formatted_subject = cls.build_english_subject(mod_title)

        # 1. Check member authentication
        if not SessionManager.is_member_authenticated(source):
            return {
                "can_report": False,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": formatted_message,
                "formatted_subject": formatted_subject,
                "author": clean_author,
                "creator_id": None,
                "creator_name": None,
                "creator_profile_url": None,
                "compose_pm_url": None,
                "is_authenticated": False,
                "reason": "Compte membre non connecté pour cette source.",
            }

        provider = ProviderRegistry.get_provider(source)
        if not provider:
            return {
                "can_report": False,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": formatted_message,
                "formatted_subject": formatted_subject,
                "author": clean_author,
                "creator_id": None,
                "creator_name": None,
                "creator_profile_url": None,
                "compose_pm_url": None,
                "is_authenticated": True,
                "reason": f"Fournisseur inconnu: '{source}'.",
            }

        # 2. Extract creator profile info
        creator_id, creator_name, creator_profile_url = None, None, None
        try:
            creator_id, creator_name, creator_profile_url = provider.get_creator_info(page_url)
        except Exception as e:
            logger.debug(f"get_creator_info error on {source}: {e}")

        compose_pm_url = None
        if creator_id:
            compose_pm_url = f"https://www.loverslab.com/messenger/compose/?to={creator_id}"

        # 3. Live check: forum comments (or PM if provider only supports PM)
        already_contacted = False
        contacted_date = None

        all_keywords = missing_mods + unnecessary_mods
        if hasattr(provider, "check_user_already_commented"):
            try:
                already_contacted, contacted_date = provider.check_user_already_commented(
                    page_url=page_url, required_keywords=all_keywords
                )
            except Exception as e:
                logger.error(f"Erreur lors de la vérification en direct sur {source}: {e}")
                already_contacted, contacted_date = False, None
        elif creator_id and hasattr(provider, "check_user_already_sent_pm"):
            try:
                already_contacted, contacted_date = provider.check_user_already_sent_pm(
                    creator_id=creator_id,
                    creator_name=creator_name or author,
                    mod_title=mod_title,
                )
            except Exception as e:
                logger.debug(f"check_user_already_sent_pm error on {source}: {e}")

        if already_contacted:
            return {
                "can_report": False,
                "already_reported": True,
                "reported_at": contacted_date or "précédemment",
                "formatted_message": formatted_message,
                "formatted_subject": formatted_subject,
                "author": creator_name or clean_author,
                "creator_id": creator_id,
                "creator_name": creator_name,
                "creator_profile_url": creator_profile_url,
                "compose_pm_url": compose_pm_url,
                "is_authenticated": True,
                "reason": f"Auteur déjà interpelé le {contacted_date or 'précédemment'}.",
            }

        return {
            "can_report": True,
            "already_reported": False,
            "reported_at": None,
            "formatted_message": formatted_message,
            "formatted_subject": formatted_subject,
            "author": creator_name or clean_author,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "creator_profile_url": creator_profile_url,
            "compose_pm_url": compose_pm_url,
            "is_authenticated": True,
            "reason": None,
        }

    @classmethod
    def submit_report(
        cls,
        source: str,
        page_url: str,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
        custom_subject: Optional[str] = None,
        creator_id: Optional[str] = None,
        creator_name: Optional[str] = None,
        send_as_pm: bool = False,
    ) -> Dict[str, Any]:
        """
        Validates anti-duplicate check live on the provider, then sends the message via PM or forum.
        """
        status = cls.check_report_status(
            source=source,
            page_url=page_url,
            mod_title=mod_title,
            author=author,
            missing_modules=missing_modules,
            unnecessary_modules=unnecessary_modules,
        )

        if not status.get("is_authenticated", False):
            logger.error(
                f"submit_report: Non authentifié sur {source} pour envoyer un rapport sur {page_url} (mod: '{mod_title}')"
            )
            return {
                "success": False,
                "message": "Veuillez vous connecter avec votre compte membre dans l'onglet 'Comptes' pour pouvoir poster.",
                "already_reported": False,
                "reported_at": None,
            }

        if status.get("already_reported", False):
            date_info = status.get("reported_at") or "précédemment"
            return {
                "success": False,
                "message": f"L'auteur a déjà été contacté pour ce mod le {date_info}. Aucun nouveau message n'a été envoyé.",
                "already_reported": True,
                "reported_at": status.get("reported_at"),
            }

        provider = ProviderRegistry.get_provider(source)
        if not provider:
            logger.error(f"Fournisseur non trouvé pour le rapport: {source} (mod: '{mod_title}', url: '{page_url}')")
            return {
                "success": False,
                "message": f"Fournisseur non trouvé: {source}",
                "already_reported": False,
                "reported_at": None,
            }

        message_to_send = custom_message or status["formatted_message"]
        subject_to_send = custom_subject or status.get("formatted_subject") or cls.build_english_subject(mod_title)
        effective_creator_id = creator_id or status.get("creator_id")
        effective_creator_name = creator_name or status.get("creator_name") or author

        # Send via PM if requested and creator_id is available
        if send_as_pm and effective_creator_id and hasattr(provider, "send_private_message"):
            success, result_msg = provider.send_private_message(
                effective_creator_id,
                effective_creator_name,
                subject_to_send,
                message_to_send,
            )
        else:
            success, result_msg = provider.post_mod_comment(page_url, message_to_send)

        if success:
            logger.info(f"Rapport de dépendances envoyé pour {mod_title} sur {source}.")
            return {
                "success": True,
                "message": result_msg,
                "already_reported": True,
                "reported_at": "à l'instant",
            }
        logger.error(
            f"Échec de l'envoi du rapport de dépendances pour '{mod_title}' sur {source} ({page_url}) : {result_msg}"
        )
        return {
            "success": False,
            "message": result_msg,
            "already_reported": False,
            "reported_at": None,
        }

    @classmethod
    def delete_report(
        cls,
        source: str,
        page_url: str,
        mod_title: str = "",
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Deletes a previously posted requirements report comment from the provider's forum.
        """
        if not SessionManager.is_member_authenticated(source):
            return {
                "success": False,
                "message": "Veuillez vous connecter avec votre compte membre pour pouvoir supprimer un commentaire.",
            }

        provider = ProviderRegistry.get_provider(source)
        if not provider or not hasattr(provider, "delete_mod_comment"):
            return {
                "success": False,
                "message": f"Fournisseur non trouvé ou suppression non supportée: {source}",
            }

        all_keywords = (missing_modules or []) + (unnecessary_modules or [])
        success, result_msg = provider.delete_mod_comment(page_url, required_keywords=all_keywords)
        if success:
            logger.info(f"Commentaire de rapport supprimé pour '{mod_title}' sur {source}.")
        else:
            logger.warning(f"Échec de suppression du commentaire pour '{mod_title}' sur {source}: {result_msg}")
        return {
            "success": success,
            "message": result_msg,
        }

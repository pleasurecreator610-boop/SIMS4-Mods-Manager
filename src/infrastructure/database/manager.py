"""Gestionnaire principal de la base de données SQLite via SQLAlchemy."""

import re
import threading
import urllib.parse
from typing import Optional
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import create_db_engine, get_session_factory, init_db_schema
from src.infrastructure.database.fts_manager import CatalogFtsManager
from src.infrastructure.database.models import CatalogMod, InstalledMod
from src.utils.logger import logger


class DatabaseManager:
    """Gestionnaire principal de la base de données SQLite via SQLAlchemy."""

    _instance: Optional["DatabaseManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.engine = create_db_engine(db_path)
        init_db_schema(self.engine)
        self.SessionLocal = get_session_factory(self.engine)
        CatalogFtsManager.initialize(self.engine)
        self.clean_and_repair_catalog()
        logger.info(f"Database initialized at: {db_path or self.engine.url}")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        """Accesseur singleton thread-safe avec double vérification."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager(db_path)
        return cls._instance

    def get_session(self) -> Session:
        """Fournit une nouvelle session de base de données."""
        return self.SessionLocal()

    def clean_and_repair_catalog(self) -> None:
        """Répare les enregistrements corrompus et purge les mods fantômes (exécuté de façon optimisée)."""
        try:
            with self.get_session() as session:
                ghosts = (
                    session.query(CatalogMod)
                    .filter((CatalogMod.remote_id == "51260") | (CatalogMod.author == "dohmra"))
                    .all()
                )
                for g in ghosts:
                    logger.info(f"Purge du mod fantôme LoversLab #{g.remote_id} ({g.author})")
                    session.delete(g)

                corrupt_items = (
                    session.query(CatalogMod)
                    .filter(
                        (CatalogMod.title == "")
                        | (CatalogMod.title == "''")
                        | (CatalogMod.title == '""')
                        | (CatalogMod.title == "Mod")
                    )
                    .all()
                )

                repaired_count = 0
                for item in corrupt_items:
                    if item.page_url:
                        slug_match = re.search(r"/files/file/\d+-([^/]+)", urllib.parse.unquote(item.page_url))
                        if slug_match:
                            cleaned_title = (
                                slug_match.group(1)
                                .replace("-", " ")
                                .replace("—", "-")
                                .replace("\u200b", "")
                                .replace("\ufeff", "")
                                .strip()
                                .title()
                            )
                            item.title = cleaned_title
                            repaired_count += 1
                        else:
                            session.delete(item)
                    else:
                        session.delete(item)

                installed_mods = session.query(InstalledMod).filter(InstalledMod.catalog_mod_id.isnot(None)).all()
                repaired_links = 0
                if installed_mods:
                    cat_ids = {im.catalog_mod_id for im in installed_mods if im.catalog_mod_id}
                    catalog_map = {
                        cm.id: cm for cm in session.query(CatalogMod).filter(CatalogMod.id.in_(cat_ids)).all()
                    }
                    for im in installed_mods:
                        cm = catalog_map.get(im.catalog_mod_id)
                        if not cm:
                            im.catalog_mod_id = None
                            repaired_links += 1
                        elif im.remote_id and (cm.remote_id != im.remote_id or cm.source != im.source):
                            logger.warning(
                                f"Réparation clé étrangère erronée : mod installé '{im.title}' (remote_id={im.remote_id}) "
                                f"était faussement lié au mod catalogue #{cm.id} '{cm.title}' (remote_id={cm.remote_id}). Dissociation."
                            )
                            true_match = (
                                session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()
                            )
                            im.catalog_mod_id = true_match.id if true_match else None
                            repaired_links += 1

                if ghosts or repaired_count or repaired_links:
                    session.commit()
                    logger.info(
                        f"Maintenance catalogue : {len(ghosts)} fantôme(s), {repaired_count} titre(s) réparé(s), {repaired_links} lien(s) corrigé(s)."
                    )
        except Exception as e:
            logger.debug(f"Erreur maintenance catalogue: {e}")

    def purge_catalog(self) -> int:
        """Purge l'intégralité du catalogue distant pour réinitialiser."""
        try:
            with self.get_session() as session:
                session.query(InstalledMod).update({InstalledMod.catalog_mod_id: None})
                count = session.query(CatalogMod).delete()
                session.commit()
                logger.info(f"Purge complète du catalogue effectuée : {count} mods supprimés.")
                return count
        except Exception as e:
            logger.error(f"Erreur lors de la purge du catalogue : {e}")
            return 0

    def get_catalog_mods_count(self) -> int:
        """Retourne le nombre total de mods répertoriés dans le catalogue."""
        try:
            with self.get_session() as session:
                return session.query(CatalogMod).count()
        except Exception:
            return 0

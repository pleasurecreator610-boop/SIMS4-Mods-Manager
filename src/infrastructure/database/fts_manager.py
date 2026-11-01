"""
Gestionnaire SQLite FTS5 (Full-Text Search) pour le catalogue de mods.
Indexe les colonnes textuelles (titre, auteur, tags, description) avec tokenization unicode61,
alignement rowid = catalog_mods.id en O(log N), triggers sélectifs UPDATE OF et pertinence BM25.
"""

from __future__ import annotations

import re
import threading
from typing import List, Optional, Set
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.utils.logger import logger

_FTS_SANITIZE_RE = re.compile(r'["\'*^:()\[\]{}\-+~]')


class CatalogFtsManager:
    """Gère la table virtuelle FTS5, ses déclencheurs sélectifs O(log N) et la recherche plein-texte."""

    _initialized: bool = False
    _initialized_engines: Set[int] = set()
    _lock = threading.Lock()

    @classmethod
    def initialize(cls, engine: Engine) -> bool:
        """Initialise la table FTS5 et ses déclencheurs SQLite sur l'instance d'Engine fournie."""
        engine_id = id(engine)
        if engine_id in cls._initialized_engines and cls._initialized:
            return True

        with cls._lock:
            if engine_id in cls._initialized_engines and cls._initialized:
                return True

            try:
                with engine.connect() as conn:
                    # 1. Table virtuelle FTS5 avec rowid aligné sur catalog_mods.id
                    conn.execute(
                        text(
                            """
                            CREATE VIRTUAL TABLE IF NOT EXISTS catalog_mods_fts USING fts5(
                                catalog_id UNINDEXED,
                                title,
                                author,
                                tags,
                                description,
                                tokenize = 'unicode61 remove_diacritics 2'
                            );
                            """
                        )
                    )

                    # 2. Mise à niveau des déclencheurs vers rowid = id (O(log N)) et UPDATE OF sélectif
                    conn.execute(text("DROP TRIGGER IF EXISTS trg_catalog_mods_ai"))
                    conn.execute(text("DROP TRIGGER IF EXISTS trg_catalog_mods_ad"))
                    conn.execute(text("DROP TRIGGER IF EXISTS trg_catalog_mods_au"))

                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER trg_catalog_mods_ai AFTER INSERT ON catalog_mods BEGIN
                                INSERT INTO catalog_mods_fts(rowid, catalog_id, title, author, tags, description)
                                VALUES (
                                    new.id,
                                    new.id,
                                    new.title,
                                    coalesce(new.author, ''),
                                    coalesce(new.tags, ''),
                                    coalesce(new.description, '')
                                );
                            END;
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER trg_catalog_mods_ad AFTER DELETE ON catalog_mods BEGIN
                                DELETE FROM catalog_mods_fts WHERE rowid = old.id;
                            END;
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER trg_catalog_mods_au
                            AFTER UPDATE OF title, author, tags, description ON catalog_mods
                            WHEN old.title IS NOT new.title
                              OR old.author IS NOT new.author
                              OR old.tags IS NOT new.tags
                              OR old.description IS NOT new.description
                            BEGIN
                                DELETE FROM catalog_mods_fts WHERE rowid = old.id;
                                INSERT INTO catalog_mods_fts(rowid, catalog_id, title, author, tags, description)
                                VALUES (
                                    new.id,
                                    new.id,
                                    new.title,
                                    coalesce(new.author, ''),
                                    coalesce(new.tags, ''),
                                    coalesce(new.description, '')
                                );
                            END;
                            """
                        )
                    )

                    # 3. Peuplage initial aligné sur rowid = id si la table FTS est vide
                    fts_count_row = conn.execute(text("SELECT count(*) FROM catalog_mods_fts")).fetchone()
                    fts_count = fts_count_row[0] if fts_count_row else 0
                    if fts_count == 0:
                        cat_count_row = conn.execute(text("SELECT count(*) FROM catalog_mods")).fetchone()
                        cat_count = cat_count_row[0] if cat_count_row else 0
                        if cat_count > 0:
                            conn.execute(
                                text(
                                    """
                                    INSERT INTO catalog_mods_fts(rowid, catalog_id, title, author, tags, description)
                                    SELECT id, id, title, coalesce(author, ''), coalesce(tags, ''), coalesce(description, '')
                                    FROM catalog_mods;
                                    """
                                )
                            )
                            logger.info(f"FTS5 initialisé et indexé avec {cat_count} mods du catalogue.")

                    conn.commit()

                cls._initialized_engines.add(engine_id)
                cls._initialized = True
                return True
            except Exception as e:
                logger.warning(f"Initialisation SQLite FTS5 échouée (repli automatique sur LIKE) : {e}")
                cls._initialized = False
                return False

    @classmethod
    def sanitize_query(cls, raw_query: str) -> Optional[str]:
        """Nettoie et formate la requête utilisateur pour la syntaxe MATCH de FTS5."""
        if not raw_query:
            return None

        cleaned = _FTS_SANITIZE_RE.sub(" ", raw_query).strip()
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
        if not tokens:
            return None

        formatted_tokens = [f'"{tok}"*' for tok in tokens]
        return " AND ".join(formatted_tokens)

    @classmethod
    def search_mod_ids(cls, session: Session, raw_query: str, limit: int = 1000) -> Optional[Set[int]]:
        """
        Recherche plein-texte via FTS5.
        Retourne l'ensemble des IDs correspondants ordonnés par pertinence BM25,
        ou None si FTS5 n'est pas disponible / en cas d'erreur (pour repli vers LIKE).
        """
        if not cls._initialized:
            return None

        match_expr = cls.sanitize_query(raw_query)
        if not match_expr:
            return None

        try:
            sql = text(
                """
                SELECT rowid FROM catalog_mods_fts
                WHERE catalog_mods_fts MATCH :expr
                ORDER BY rank
                LIMIT :limit
                """
            )
            rows = session.execute(sql, {"expr": match_expr, "limit": limit}).fetchall()
            return {int(r[0]) for r in rows if r[0] is not None}
        except Exception as e:
            logger.debug(f"Requête FTS5 échouée pour '{raw_query}' (repli LIKE) : {e}")
            return None

    @classmethod
    def search_candidate_ids_any_token(
        cls, session: Session, tokens: List[str], limit: int = 100
    ) -> Optional[Set[int]]:
        """
        Pré-sélectionne rapidement en O(log N) via l'index inversé FTS5 (opérateur OR sur title)
        les candidats partageant au moins un jeton significatif avec la requête.
        """
        if not cls._initialized or not tokens:
            return None

        clean_toks = []
        for tok in tokens[:4]:
            sanitized = _FTS_SANITIZE_RE.sub("", tok).strip()
            if len(sanitized) >= 2:
                clean_toks.append(f'title : "{sanitized}"*')
        if not clean_toks:
            return None

        match_expr = " OR ".join(clean_toks)
        try:
            sql = text(
                """
                SELECT rowid FROM catalog_mods_fts
                WHERE catalog_mods_fts MATCH :expr
                ORDER BY rank
                LIMIT :limit
                """
            )
            rows = session.execute(sql, {"expr": match_expr, "limit": limit}).fetchall()
            return {int(r[0]) for r in rows if r[0] is not None}
        except Exception:
            return None

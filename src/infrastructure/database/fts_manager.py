"""
Gestionnaire SQLite FTS5 (Full-Text Search) pour le catalogue de mods.
Indexe les colonnes textuelles (titre, auteur, tags, description) avec tokenization unicode61
et recherche ultra-rapide par correspondance préfixée et pertinence BM25.
"""

from __future__ import annotations

import re
import threading
from typing import Optional, Set
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.utils.logger import logger


class CatalogFtsManager:
    """Gère la table virtuelle FTS5, ses déclencheurs de synchronisation et la recherche plein-texte."""

    _initialized: bool = False
    _lock = threading.Lock()

    @classmethod
    def initialize(cls, engine: Engine) -> bool:
        """Initialise la table FTS5 et ses déclencheurs SQLite si FTS5 est supporté."""
        if cls._initialized:
            return True

        with cls._lock:
            if cls._initialized:
                return True

            try:
                with engine.connect() as conn:
                    # 1. Vérification du support SQLite FTS5
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

                    # 2. Déclencheurs de synchronisation automatique avec catalog_mods
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER IF NOT EXISTS trg_catalog_mods_ai AFTER INSERT ON catalog_mods BEGIN
                                INSERT INTO catalog_mods_fts(catalog_id, title, author, tags, description)
                                VALUES (new.id, new.title, coalesce(new.author, ''), coalesce(new.tags, ''), coalesce(new.description, ''));
                            END;
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER IF NOT EXISTS trg_catalog_mods_ad AFTER DELETE ON catalog_mods BEGIN
                                DELETE FROM catalog_mods_fts WHERE catalog_id = old.id;
                            END;
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TRIGGER IF NOT EXISTS trg_catalog_mods_au AFTER UPDATE ON catalog_mods BEGIN
                                DELETE FROM catalog_mods_fts WHERE catalog_id = old.id;
                                INSERT INTO catalog_mods_fts(catalog_id, title, author, tags, description)
                                VALUES (new.id, new.title, coalesce(new.author, ''), coalesce(new.tags, ''), coalesce(new.description, ''));
                            END;
                            """
                        )
                    )

                    # 3. Peuplage initial si la table FTS est vide alors que catalog_mods contient des lignes
                    fts_count_row = conn.execute(text("SELECT count(*) FROM catalog_mods_fts")).fetchone()
                    fts_count = fts_count_row[0] if fts_count_row else 0
                    if fts_count == 0:
                        cat_count_row = conn.execute(text("SELECT count(*) FROM catalog_mods")).fetchone()
                        cat_count = cat_count_row[0] if cat_count_row else 0
                        if cat_count > 0:
                            conn.execute(
                                text(
                                    """
                                    INSERT INTO catalog_mods_fts(catalog_id, title, author, tags, description)
                                    SELECT id, title, coalesce(author, ''), coalesce(tags, ''), coalesce(description, '')
                                    FROM catalog_mods;
                                    """
                                )
                            )
                            logger.info(f"FTS5 initialisé et indexé avec {cat_count} mods du catalogue.")

                    conn.commit()

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

        # Nettoyage des caractères syntaxiques risqués pour FTS5
        cleaned = re.sub(r'["\'*^:()\[\]{}]', " ", raw_query).strip()
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
        if not tokens:
            return None

        # Formulation de recherche : préfixe pour chaque mot (auto-complétion rapide)
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
                SELECT catalog_id FROM catalog_mods_fts
                WHERE catalog_mods_fts MATCH :expr
                ORDER BY rank
                LIMIT :limit
                """
            )
            rows = session.execute(sql, {"expr": match_expr, "limit": limit}).fetchall()
            return {int(r[0]) for r in rows}
        except Exception as e:
            logger.debug(f"Erreur recherche FTS5 '{raw_query}', déclenchement du repli LIKE : {e}")
            return None

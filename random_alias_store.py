# SPDX-License-Identifier: GPL-3.0-only
"""Registry of generated random alias prefixes."""

import sqlite3

from config import resolve_path
from logutils import get_logger

logger = get_logger(__name__)


class RandomAliasStore:
    def __init__(self, db_path: str) -> None:
        path = resolve_path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS random_aliases (
                alias_prefix TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def register(self, alias_prefix: str) -> bool:
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO random_aliases (alias_prefix) VALUES (?)",
                    (alias_prefix,),
                )
            logger.debug("Registered random alias prefix '%s'.", alias_prefix)
            return True
        except sqlite3.IntegrityError:
            return False

    def remove(self, alias_prefix: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM random_aliases WHERE alias_prefix = ?", (alias_prefix,)
            )
        logger.debug("Released random alias prefix '%s'.", alias_prefix)

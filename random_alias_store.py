# SPDX-License-Identifier: GPL-3.0-only
"""Registry of generated random alias prefixes."""

import sqlite3
from typing import Optional

from config import Credentials
from logutils import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS random_aliases (
    alias_prefix TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class RandomAliasStore:
    def __init__(
        self, credentials: Credentials, base_path: Optional[str] = None
    ) -> None:
        db_path = (
            credentials.random_alias_dir(base_path)
            / credentials.RANDOM_ALIAS_DB_FILENAME
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(_SCHEMA)
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

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "RandomAliasStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

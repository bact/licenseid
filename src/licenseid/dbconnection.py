# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""SQLite connections to the licence database."""

import contextlib
import sqlite3
import threading
from collections.abc import Iterator


class Connections:
    """Open SQLite connections to one database.

    Each query opens and closes its own connection, except inside
    ``reading()``, where a thread's queries share one. Resolving a tag value
    takes about five lookups, so a file of thousands of distinct tags spent
    nearly all its time opening connections.
    """

    def __init__(self, path: str, use_uri: bool) -> None:
        self.path = path
        self.use_uri = use_uri
        # Per thread: sqlite3 refuses a connection made in another thread,
        # and two threads may match on one matcher at once.
        self._local = threading.local()

    def connect(self) -> sqlite3.Connection:
        """Open a new connection."""
        conn = sqlite3.connect(self.path, uri=self.use_uri)
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    @contextlib.contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back, and close unless a ``reading()`` block shares
        the connection -- ``Connection.__exit__`` alone only handles the
        transaction, not closing."""
        if getattr(self._local, "depth", 0):
            if getattr(self._local, "conn", None) is None:
                self._local.conn = self.connect()
            with self._local.conn:
                yield self._local.conn
            return
        conn = self.connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def reading(self) -> Iterator[None]:
        """Share one connection among this thread's queries in the block.

        It opens at the first query, so a block that makes none opens none,
        and it closes when the outermost block ends, so a file deleted
        between two blocks is not read through a stale connection.
        """
        self._local.depth = getattr(self._local, "depth", 0) + 1
        try:
            yield
        finally:
            self._local.depth -= 1
            conn = getattr(self._local, "conn", None)
            if not self._local.depth and conn is not None:
                self._local.conn = None
                conn.close()

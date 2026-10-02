# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""SQLite connections to the licence database."""

import contextlib
import sqlite3
import threading
from collections.abc import Iterator


class _ThreadState(threading.local):
    """One thread's share: sqlite3 refuses a connection made in another
    thread, and two threads may match on one matcher at once."""

    blocks = 0  # reading() blocks open
    queries = 0  # connection() blocks open on the shared connection
    conn: sqlite3.Connection | None = None


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
        self._state = _ThreadState()

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
        state = self._state
        if not state.blocks:
            conn = self.connect()
            try:
                with conn:
                    yield conn
            finally:
                conn.close()
            return
        if state.conn is None:
            state.conn = self.connect()
        conn = state.conn
        # Each query starts as on a new connection. A query nested in
        # another joins its transaction: committing there would commit the
        # outer one's writes before it knows whether they stand. There is no
        # savepoint, so a nested write whose error the outer query catches
        # still commits with it; nothing nests a write today.
        conn.row_factory = None
        transaction = contextlib.nullcontext() if state.queries else conn
        state.queries += 1
        try:
            with transaction:
                yield conn
        finally:
            state.queries -= 1

    @contextlib.contextmanager
    def reading(self) -> Iterator[None]:
        """Share one connection among this thread's queries in the block.

        It opens at the first query, so a block that makes none opens none,
        and it closes when the outermost block ends, so a file deleted
        between two blocks is not read through a stale connection.
        """
        state = self._state
        state.blocks += 1
        try:
            yield
        finally:
            state.blocks -= 1
            if not state.blocks and state.conn is not None:
                conn, state.conn = state.conn, None
                conn.close()

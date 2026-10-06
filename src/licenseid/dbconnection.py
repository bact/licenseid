# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""SQLite connections to the licence database."""

import contextlib
import sqlite3
import threading
from collections.abc import Iterator

from licenseid.dbcheck import is_memory_database, lookup_error, read_only_uri

QueryConnection = contextlib.AbstractContextManager[sqlite3.Connection]


class _ThreadState(threading.local):
    """One thread's share: sqlite3 refuses a connection made in another
    thread, and two threads may match on one matcher at once."""

    blocks = 0  # reading() blocks open
    block = 0  # outermost reading() blocks entered so far
    queries = 0  # connection() blocks open on the shared connection
    conn: sqlite3.Connection | None = None


class Connections:
    """Open SQLite connections to one database.

    Each query opens and closes its own connection, except inside
    ``reading()``, where a thread's queries share one. Resolving a tag value
    takes about five lookups, so a file of thousands of distinct tags spent
    nearly all its time opening connections.
    """

    def __init__(self, path: str, use_uri: bool, label: str | None = None) -> None:
        self.path = path
        self.use_uri = use_uri
        self.label = label or path  # the file, for a message
        # A read opens read-only, so it never creates the file; an in-memory
        # database has no file and opens as it is.
        self._read_uri = None if is_memory_database(path) else read_only_uri(path)
        self._state = _ThreadState()

    def connect(self, write: bool = False) -> sqlite3.Connection:
        """Open a new connection.

        Read-only unless *write*: a plain read-write open creates a missing
        file, so a lookup after the database was deleted left an empty one
        behind. An in-memory database has no file and opens as it is.
        """
        if write or self._read_uri is None:
            conn = sqlite3.connect(self.path, uri=self.use_uri)
        else:
            conn = sqlite3.connect(self._read_uri, uri=True)
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    @contextlib.contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """One query's connection (``_open``). A read that fails in SQLite
        raises ``DatabaseNotReadyError`` (``dbcheck.lookup_error``), whatever
        the caller: the file was deleted, truncated or overwritten after the
        readiness check. A write keeps its own error, which ``update`` words.
        """
        try:
            with self._open(write) as conn:
                yield conn
        except sqlite3.Error as exc:
            if write:
                raise
            raise lookup_error(self.label, exc) from exc

    @contextlib.contextmanager
    def _open(self, write: bool) -> Iterator[sqlite3.Connection]:
        """Commit or roll back, and close unless a ``reading()`` block shares
        the connection -- ``Connection.__exit__`` alone only handles the
        transaction, not closing. A *write* query always has a connection of
        its own: the shared one is read-only."""
        state = self._state
        if write or not state.blocks:
            conn = self.connect(write)
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
        if not state.blocks:
            state.block += 1
        state.blocks += 1
        try:
            yield
        finally:
            state.blocks -= 1
            if not state.blocks and state.conn is not None:
                conn, state.conn = state.conn, None
                conn.close()

    def current_block(self) -> int:
        """This thread's outermost ``reading()`` block, counted from 1, or 0
        outside one."""
        state = self._state
        return state.block if state.blocks else 0

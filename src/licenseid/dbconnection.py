# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""SQLite connections to the licence database."""

import contextlib
import os
import sqlite3
import threading
from collections.abc import Iterator

from licenseid.dbcheck import (
    absolute_path,
    is_memory_database,
    is_plain_path,
    lookup_error,
    open_uri,
    os_reason,
    pin_relative_uri,
    reject_blocking_file,
    unreadable_error,
)

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

    def __init__(
        self,
        path: str,
        use_uri: bool,
        label: str | None = None,
        create: bool = True,
    ) -> None:
        # A relative path names one file for good: reads and writes alike
        # must not follow a later chdir to another.
        try:
            path = (
                absolute_path(path) if is_plain_path(path) else pin_relative_uri(path)
            )
        except OSError as exc:  # no working directory to resolve against
            raise unreadable_error(path, os_reason(exc)) from exc
        self.path = path
        self.use_uri = use_uri
        self.label = label or path  # the file, for a message
        self.create = create
        # What a read and a write of an existing file open. A read never
        # creates the file; an in-memory database has no file and opens as it
        # is (None).
        self._uris = (
            None if is_memory_database(path) else (open_uri(path), open_uri(path, "rw"))
        )
        self._state = _ThreadState()

    def connect(self, write: bool = False) -> sqlite3.Connection:
        """Open a new connection.

        Read-only unless *write*: a plain read-write open creates a missing
        file, so a lookup after the database was deleted left an empty one
        behind. An in-memory database has no file and opens as it is. A write
        creates the file only when the database was made to *create* it;
        otherwise the file must be there.
        """
        if self._uris is None:
            conn = sqlite3.connect(self.path, uri=self.use_uri)
        else:
            reject_blocking_file(self.path)
            if write and self.create:
                conn = sqlite3.connect(self.path, uri=self.use_uri)
            else:
                conn = sqlite3.connect(self._uris[write], uri=True)
        try:
            conn.execute("PRAGMA mmap_size=268435456")
        except BaseException:
            conn.close()
            raise
        return conn

    @contextlib.contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """One query's connection (``_open``). A read that fails in SQLite
        raises ``DatabaseNotReadyError`` (``dbcheck.lookup_error``), whatever
        the caller: the file was deleted, truncated or overwritten after the
        readiness check. A write keeps its own error when the database may
        create its file: ``update`` words that one.
        """
        try:
            with self._open(write) as conn:
                yield conn
        except sqlite3.Error as exc:
            if write and self.create:
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

    def recover(self) -> None:
        """Open for writing and read once: SQLite then rolls back a hot
        journal a crashed writer left, or creates the ``-shm`` of a WAL
        database, which no read-only open can do. Never creates the file
        unless the database was made to *create* it."""
        with self.connection(write=True) as conn:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()

    def leave_wal(self) -> None:
        """Take a database built by an earlier version out of WAL mode, which
        leaves ``-wal`` and ``-shm`` files beside it that a read-only
        connection cannot remove. Best effort and never waiting: a reader or
        a lock leaves it as it is, to be converted by a later run."""
        with (
            contextlib.suppress(sqlite3.Error),
            contextlib.closing(self.connect(write=True)) as conn,
        ):
            conn.execute("PRAGMA busy_timeout = 0")
            mode = conn.execute("PRAGMA journal_mode = DELETE").fetchone()
            main = conn.execute("PRAGMA database_list").fetchone()
            if mode and str(mode[0]).lower() == "delete" and main and main[2]:
                # SQLite removes ``-wal`` but leaves ``-shm`` behind; no
                # connection uses it once the database is out of WAL.
                with contextlib.suppress(OSError):
                    os.unlink(f"{main[2]}-shm")

    def current_block(self) -> int:
        """This thread's outermost ``reading()`` block, counted from 1, or 0
        outside one."""
        state = self._state
        return state.block if state.blocks else 0

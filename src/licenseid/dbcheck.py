# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Check that a license database is ready to answer, before anything opens it.

``LicenseDatabase`` creates its tables on open, so an unready or foreign file
opened through it would be written to, and a partly built database would
answer "no license found" as if it were complete. The check here opens the
file read-only and never modifies it.

Stdlib only, so importing it does not pull in ``requests``.
"""

import contextlib
import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode

from licenseid.errors import DatabaseNotReadyError

_ACTION = "; run 'licenseid update'"

_REQUIRED_COLUMNS = "license_id, name, is_spdx, is_osi_approved, is_fsf_libre"


def _is_idle_wal_database(file_path: str) -> bool:
    """Whether the file is in write-ahead-log mode with no log beside it.

    Opened read-only, such a file still makes an -shm and a -wal file. With
    no log there is nothing outside the main file to read, so it can be read
    as immutable instead. A rollback-journal database, which every database
    licenseid writes is, is never read that way: immutable turns SQLite's
    locking off, and an ``update`` may be rewriting the file.

    SQLite looks beside the file a symlink points to, so resolve it first.
    """
    real = os.path.realpath(file_path)
    if any(os.path.exists(real + suffix) for suffix in ("-wal", "-journal")):
        return False
    try:
        with open(real, "rb") as handle:
            header = handle.read(20)
    except OSError:
        return False
    # Bytes 18 and 19 are the file-format versions: 2 means write-ahead log.
    return header[18:20] == b"\x02\x02"


def _uri_file_path(base: str) -> str | None:
    """The file a ``file:`` URI names, or None when it names a host."""
    rest = base[len("file:") :]
    if rest.startswith("//"):
        rest = rest[2:]
        if not rest.startswith("/"):
            return None
    return unquote(rest)


def _read_only_uri(db_path: str) -> str:
    """The SQLite URI that opens *db_path* read-only, without creating it.

    A write-ahead-log database with no log is read as immutable, so the read
    leaves no -shm or -wal file behind (see ``_is_idle_wal_database``).
    ``mode=memory`` URIs (a shared in-memory database) stay as they are: they
    cannot create a file, and ``mode=ro`` would contradict them.
    """
    if db_path == ":memory:":
        return "file::memory:"
    if not db_path.startswith("file:"):
        path = str(Path(db_path).absolute())
        # An empty authority ("file://" + "/path"), so a path that starts
        # with "//" is not read as a host name.
        uri = f"file://{quote(path)}?mode=ro"
        return uri + "&immutable=1" if _is_idle_wal_database(path) else uri
    # Split by hand: urlunsplit would rewrite "file::memory:" as a file path.
    # SQLite ignores a fragment, and mode=ro placed after one would be lost.
    base, _, raw_query = db_path.split("#", 1)[0].partition("?")
    query = parse_qsl(raw_query, keep_blank_values=True)
    if ("mode", "memory") in query or base.startswith("file::memory:"):
        return db_path
    query = [(key, value) for key, value in query if key != "mode"]
    query.append(("mode", "ro"))
    file_path = _uri_file_path(base)
    if (
        file_path
        and all(key != "immutable" for key, _ in query)
        and _is_idle_wal_database(file_path)
    ):
        query.append(("immutable", "1"))
    return f"{base}?{urlencode(query, quote_via=quote)}"


def _exists(db_path: str) -> bool:
    """Whether a plain path names something; URIs are checked by SQLite."""
    if db_path == ":memory:" or db_path.startswith("file:"):
        return True
    return os.path.exists(db_path)


def _shown(db_path: str) -> str:
    """*db_path* for a message: a control character (a newline in a file name)
    is written as an escape, so the message stays one line."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in db_path
    )


def _one_line(exc: Exception) -> str:
    """The error text on one line; some SQLite errors have none."""
    return " ".join(str(exc).split()) or type(exc).__name__


def unreadable_error(db_path: str, exc: Exception) -> DatabaseNotReadyError:
    """The refusal for a database that SQLite could not read."""
    return DatabaseNotReadyError(
        f"database: unreadable: {_shown(db_path)}: {_one_line(exc)}"
    )


def _is_ready(conn: sqlite3.Connection) -> bool:
    """Whether the schema, the recorded version and the rows are all there."""
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('licenses', 'db_metadata')"
        )
    }
    if tables != {"licenses", "db_metadata"}:
        return False
    row = conn.execute(
        "SELECT value FROM db_metadata WHERE key = 'license_list_version'"
    ).fetchone()
    if row is None or not isinstance(row[0], str) or not row[0].strip():
        return False
    # Selecting the columns every answer reads proves they exist, so a table of
    # the right name but a damaged or foreign layout is reported here, not as a
    # KeyError on the first query. The norm_* columns are left out: opening the
    # database with LicenseDatabase adds them to an older file.
    return (
        conn.execute(f"SELECT {_REQUIRED_COLUMNS} FROM licenses LIMIT 1").fetchone()
        is not None
    )


def check_database_ready(db_path: str) -> None:
    """Raise :class:`DatabaseNotReadyError` unless *db_path* is a ready database.

    Ready means the ``licenses`` and ``db_metadata`` tables exist, the metadata
    holds a non-blank ``license_list_version`` (written in the same
    transaction as the license rows, so it marks a complete update), and
    ``licenses`` has at least one row.

    The file is opened read-only and is never created or changed.
    """
    if not _exists(db_path):
        raise DatabaseNotReadyError(f"database: not found: {_shown(db_path)}{_ACTION}")
    try:
        with contextlib.closing(
            sqlite3.connect(_read_only_uri(db_path), uri=True)
        ) as conn:
            ready = _is_ready(conn)
    except (sqlite3.Error, UnicodeError, ValueError) as exc:
        raise unreadable_error(db_path, exc) from exc
    if not ready:
        raise DatabaseNotReadyError(f"database: empty: {_shown(db_path)}{_ACTION}")

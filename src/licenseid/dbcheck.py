# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Check that a license database is ready to answer, before anything opens it.

``LicenseDatabase`` creates its tables on open, so an unready or foreign file
opened through it would be written to, and a partly built database would
answer "no license found" as if it were complete. The check here opens the
file read-only and never writes to it.

Stdlib only, so importing it does not pull in ``requests``.
"""

import contextlib
import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote_to_bytes, urlencode

from licenseid.errors import DatabaseNotReadyError

_ACTION = "; run 'licenseid update'"

_REQUIRED_COLUMNS = ("license_id", "name", "is_spdx", "is_osi_approved", "is_fsf_libre")

# An object licenseid does not create: not one of its tables or indexes, the
# shadow tables of the FTS5 index, or SQLite's own.
_FOREIGN_OBJECT = r"""
    SELECT 1 FROM sqlite_master
    WHERE name NOT IN ('licenses', 'exceptions', 'license_index', 'db_metadata',
                       'license_fingerprints', 'idx_fp_ngram', 'idx_licenses_name')
      AND name NOT LIKE 'license\_index\_%' ESCAPE '\'
      AND name NOT LIKE 'sqlite\_%' ESCAPE '\'
    LIMIT 1
"""


def is_plain_path(db_path: str) -> bool:
    """Whether *db_path* names a file, not ``:memory:`` or a ``file:`` URI."""
    return db_path != ":memory:" and not db_path.startswith("file:")


def _uri_file_path(base: str) -> str | None:
    """The file a ``file:`` URI names, or None when it names a host."""
    rest = base[len("file:") :]
    if rest.startswith("//"):
        rest = rest[2:]
        if not rest.startswith("/"):
            return None
    return os.fsdecode(unquote_to_bytes(os.fsencode(rest)))


def _split_file_uri(uri: str) -> tuple[str, list[tuple[str, str]]]:
    """The part of a ``file:`` URI before the query, and its query pairs.

    Split by hand: urlunsplit would rewrite "file::memory:" as a file path.
    SQLite ignores a fragment, so it is dropped here.
    """
    base, _, raw_query = uri.split("#", 1)[0].partition("?")
    return base, parse_qsl(raw_query, keep_blank_values=True)


def _is_memory_uri(base: str, query: list[tuple[str, str]]) -> bool:
    return ("mode", "memory") in query or base.startswith("file::memory:")


def _read_only_uri(db_path: str) -> str:
    """The SQLite URI that opens *db_path* read-only, without creating it.

    ``mode=memory`` URIs (a shared in-memory database) stay as they are: they
    cannot create a file, and ``mode=ro`` would contradict them.
    """
    if db_path == ":memory:":
        return "file::memory:"
    if is_plain_path(db_path):
        # os.fsencode keeps a file name that is not valid UTF-8 (a surrogate
        # escape in the str) intact. The empty authority ("file://" + "/path")
        # keeps a path that starts with "//" from being read as a host name.
        path = os.fsencode(Path(db_path).absolute())
        return f"file://{quote(path)}?mode=ro"
    base, query = _split_file_uri(db_path)
    if _is_memory_uri(base, query):
        return db_path
    query = [(key, value) for key, value in query if key != "mode"]
    query.append(("mode", "ro"))
    return f"{base}?{urlencode(query, quote_via=quote)}"


def _exists(db_path: str) -> bool:
    """Whether the file *db_path* names exists; anything else (a memory
    database, a URI with a host) is left to SQLite."""
    if db_path == ":memory:":
        return True
    if is_plain_path(db_path):
        return os.path.exists(db_path)
    base, query = _split_file_uri(db_path)
    if _is_memory_uri(base, query) or any(key == "vfs" for key, _ in query):
        return True
    file_path = _uri_file_path(base)
    return not file_path or os.path.exists(file_path)


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


def _has_content(conn: sqlite3.Connection, index_sql: str | None) -> bool:
    """Whether the version, the rows and the search index are all there."""
    # A plain table of that name cannot be searched with MATCH.
    if "fts5" not in (index_sql or "").lower():
        return False
    row = conn.execute(
        "SELECT value FROM db_metadata WHERE key = 'license_list_version'"
    ).fetchone()
    if row is None or not isinstance(row[0], str) or not row[0].strip():
        return False
    # Rows must be there, and the id of each must be text: SQLite lets a TEXT
    # key hold NULL or a blob, and normalising one raises. NOT INDEXED reads
    # the table itself, not the key's index, which a damaged table page
    # would not show.
    if conn.execute("SELECT 1 FROM licenses LIMIT 1").fetchone() is None:
        return False
    if conn.execute(
        "SELECT 1 FROM licenses NOT INDEXED WHERE typeof(license_id) != 'text' LIMIT 1"
    ).fetchone():
        return False
    # The search index is what match reads: an empty one answers "no license".
    return conn.execute("SELECT 1 FROM license_index LIMIT 1").fetchone() is not None


def _not_ready(conn: sqlite3.Connection) -> str | None:
    """The condition that keeps the database from answering, or None if it can.

    ``invalid`` is a file that holds objects licenseid does not create beside
    an incomplete set of its own tables: ``licenseid update`` would write into
    it, so no action is offered.
    """
    tables = dict(
        conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('licenses', 'db_metadata', 'license_index')"
        )
    )
    if tables.keys() != {"licenses", "db_metadata", "license_index"}:
        return "invalid" if conn.execute(_FOREIGN_OBJECT).fetchone() else "empty"
    # The columns every answer reads, spelt as the code reads them: SQLite
    # matches column names case-insensitively, a dict lookup does not.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
    if not set(_REQUIRED_COLUMNS) <= columns:
        return "invalid"
    return None if _has_content(conn, tables["license_index"]) else "empty"


def check_database_ready(db_path: str | os.PathLike[str]) -> None:
    """Raise :class:`DatabaseNotReadyError` unless *db_path* is a ready database.

    Ready means the ``licenses``, ``db_metadata`` and ``license_index`` tables
    exist, the metadata holds a non-blank ``license_list_version``, and
    ``licenses`` and ``license_index`` each have a row. The version is written
    in the same transaction as those rows, so it marks them complete. The
    fingerprints are computed in a later transaction and are not checked (an
    open item in the tech-debt roadmap).

    The file is opened read-only and is never created or written. A
    write-ahead-log file may get -shm and -wal files beside it, which stay
    until a writer next closes it. In a directory that cannot be written to,
    that read fails ("attempt to write a readonly database").
    """
    db_path = os.fspath(db_path)  # a Path worked before the check existed
    if not _exists(db_path):
        raise DatabaseNotReadyError(f"database: not found: {_shown(db_path)}{_ACTION}")
    try:
        with contextlib.closing(
            sqlite3.connect(_read_only_uri(db_path), uri=True)
        ) as conn:
            condition = _not_ready(conn)
    except (sqlite3.Error, UnicodeError, ValueError) as exc:
        raise unreadable_error(db_path, exc) from exc
    if condition:
        action = "" if condition == "invalid" else _ACTION
        raise DatabaseNotReadyError(f"database: {condition}: {_shown(db_path)}{action}")

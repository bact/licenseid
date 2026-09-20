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
import stat
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, quote, unquote_to_bytes, urlencode

from licenseid.errors import DatabaseNotReadyError

_ACTION = "; run 'licenseid update'"

_REQUIRED_TABLES = {"licenses", "db_metadata", "license_index"}
_REQUIRED_COLUMNS = ("license_id", "name", "is_spdx", "is_osi_approved", "is_fsf_libre")
_META_COLUMNS = ("key", "value")
_SQLITE_HEADER = b"SQLite format 3\x00"

# Seconds to wait for a lock. This is a pre-flight probe, and the command
# that follows opens the file with SQLite's own default wait, so waiting the
# full five seconds here (twice per command) would only stall the answer.
_BUSY_WAIT = 1.0

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
    """The file a ``file:`` URI names, or None when another host names it."""
    rest = base[len("file:") :]
    if rest.startswith("//"):
        rest = rest[2:]
        # SQLite accepts an empty authority and "localhost"; any other names
        # a machine whose files are not this one's to find.
        if rest.startswith("localhost/"):
            rest = rest[len("localhost") :]
        elif not rest.startswith("/"):
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
    # Exactly "file::memory:": SQLite compares the whole name, so
    # "file::memory:notes" is an ordinary file called ":memory:notes".
    return ("mode", "memory") in query or base == "file::memory:"


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


def is_memory_database(db_path: str) -> bool:
    """Whether *db_path* is an in-memory database, which has no file."""
    if db_path == ":memory:":
        return True
    if is_plain_path(db_path):
        return False
    base, query = _split_file_uri(db_path)
    return _is_memory_uri(base, query)


def _os_file(db_path: str) -> str | None:
    """The file the operating system would open, or None when there is none
    (an in-memory database) or another host names it.

    The name is normalised, because everything that acts on it goes through
    ``Path`` (which drops a trailing separator and a ``/.``) while ``os.stat``
    does not. Without this, ``licenses.db/.`` would be checked as one file
    and then opened, written or deleted as another.
    """
    if is_memory_database(db_path):
        return None
    if is_plain_path(db_path):
        return str(Path(db_path))
    file_path = _uri_file_path(_split_file_uri(db_path)[0])
    return str(Path(file_path)) if file_path else None


def _has_own_vfs(db_path: str) -> bool:
    """Whether the URI names a VFS of its own, which licenseid cannot assume
    reads an ordinary file."""
    if is_plain_path(db_path):
        return False
    return any(key == "vfs" for key, _ in _split_file_uri(db_path)[1])


def named_file(db_path: str) -> str | None:
    """The file licenseid may act on, or None when it cannot say which one
    that is: an in-memory database, another host, or a URI with its own VFS.

    A ``vfs=`` URI still opens an ordinary file for every VFS the standard
    library ships, so the readiness check stats it (through :func:`_os_file`)
    rather than opening a named pipe read-only and waiting for ever. Writing
    to it or deleting it is another matter, and this is what guards those.
    """
    return None if _has_own_vfs(db_path) else _os_file(db_path)


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


def os_reason(exc: OSError) -> Exception:
    """The OS message alone: str(OSError) repeats the errno and the path,
    which the diagnostic line already carries."""
    return OSError(exc.strerror or type(exc).__name__)


Refusal = tuple[str, DatabaseNotReadyError]  # the condition, and how to say it


def _stat_failure(db_path: str, exc: OSError | ValueError) -> Refusal:
    """The refusal for a name the file system would not describe.

    Nothing at that name is ``not found`` (and a ValueError means an embedded
    NUL, a name no file system can hold). A name it will not even look at is
    ``unreadable``: the database may well be there, and ``licenseid update``
    could not write it either, so pointing at that command would mislead.
    """
    looked = isinstance(exc, OSError) and not isinstance(
        exc, (FileNotFoundError, NotADirectoryError)
    )
    if looked:
        return "unreadable", unreadable_error(db_path, os_reason(cast(OSError, exc)))
    return "not found", DatabaseNotReadyError(
        f"database: not found: {_shown(db_path)}{_ACTION}"
    )


def _path_problem(db_path: str) -> Refusal | None:
    """The refusal for a path SQLite never gets to open, or None.

    Anything the file system can describe is left to SQLite, except a file
    it could not be a database in: opening a pipe read-only waits for a
    writer that never comes, so the command would hang with no exit code.
    """
    path = _os_file(db_path)
    if path is None:
        return None
    try:
        mode = os.stat(path).st_mode
    except (OSError, ValueError) as exc:
        # A URI with its own VFS may not name a file at all, so what the file
        # system says about the name decides nothing. The type below still
        # does: a pipe blocks whoever opens it read-only, VFS or no VFS.
        return None if _has_own_vfs(db_path) else _stat_failure(db_path, exc)
    if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
        # Reading opens read-only, and opening a FIFO that way waits for a
        # writer that never comes. A directory is left to SQLite, which says
        # so at once; nothing else can be a database.
        return "unreadable", unreadable_error(db_path, OSError("not a regular file"))
    return None


def unreadable_error(db_path: str, exc: Exception) -> DatabaseNotReadyError:
    """The refusal for a database that SQLite could not read."""
    return DatabaseNotReadyError(
        f"database: unreadable: {_shown(db_path)}: {_one_line(exc)}"
    )


def invalid_error(db_path: str) -> DatabaseNotReadyError:
    """The refusal for a file licenseid did not build and must not write to.

    No action: every one licenseid could offer would change the file.
    """
    return DatabaseNotReadyError(f"database: invalid: {_shown(db_path)}")


def delete_failed_error(db_path: str, exc: OSError) -> DatabaseNotReadyError:
    """The refusal for a cache file the operating system would not remove."""
    return DatabaseNotReadyError(
        f"database: delete failed: {_shown(db_path)}: {_one_line(os_reason(exc))}"
    )


def _has_columns(
    conn: sqlite3.Connection, table: str, required: tuple[str, ...]
) -> bool:
    """Whether *table* has every column in *required*, spelt the same way:
    SQLite matches column names case-insensitively, a set lookup does not."""
    # table is one of the fixed names below, never user input.
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return set(required) <= columns


def _foreign_schema(conn: sqlite3.Connection, tables: dict[str, str]) -> bool:
    """Whether a table carrying one of licenseid's names is not licenseid's.

    Another program's ``licenses`` table is the dangerous case: the name is
    one licenseid creates, so without this the file would be called ``empty``
    and the user told to run ``update``, which writes licenseid's schema into
    it.
    """
    if "licenses" in tables and not _has_columns(conn, "licenses", _REQUIRED_COLUMNS):
        return True
    if "db_metadata" in tables and not _has_columns(conn, "db_metadata", _META_COLUMNS):
        return True
    # A plain table of that name cannot be searched with MATCH.
    return "license_index" in tables and "fts5" not in tables["license_index"].lower()


def _has_content(conn: sqlite3.Connection) -> bool:
    """Whether the version, the rows and the search index are all there."""
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

    ``invalid`` is a file licenseid did not build: one of its table names
    carrying somebody else's schema, or objects licenseid does not create
    beside an incomplete set of its own tables. ``licenseid update`` would
    write into such a file, so no action is offered.
    """
    tables = dict(
        conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('licenses', 'db_metadata', 'license_index')"
        )
    )
    if _foreign_schema(conn, tables):
        return "invalid"
    if tables.keys() != _REQUIRED_TABLES:
        return "invalid" if conn.execute(_FOREIGN_OBJECT).fetchone() else "empty"
    return None if _has_content(conn) else "empty"


# What SQLite says when somebody else is holding the database, and what it
# says when only this read-only way of opening it is the problem.
_LOCKED = ("database is locked", "database table is locked")
_NEEDS_WRITING = ("attempt to write a readonly database",)  # a WAL needs -shm


def _open_failure(exc: Exception) -> str | None:
    """The condition for a read-only open that failed, or None for no verdict.

    A lock another process holds says nothing about the file, so the
    condition is ``unknown``: reading may go on and find out, but writing and
    deleting may not, because the file could be anybody's. A write-ahead log
    that cannot create its -shm is not in doubt at all — only this way of
    opening it is — so it gets no verdict, and whatever opens it next reports
    its own failure.
    """
    if not isinstance(exc, sqlite3.OperationalError):
        return "unreadable"
    if any(text in str(exc) for text in _LOCKED):
        return "unknown"
    return None if any(text in str(exc) for text in _NEEDS_WRITING) else "unreadable"


def _open_condition(db_path: str) -> Refusal | None:
    """The refusal the file's own contents call for, or None."""
    try:
        with contextlib.closing(
            sqlite3.connect(_read_only_uri(db_path), uri=True, timeout=_BUSY_WAIT)
        ) as conn:
            condition = _not_ready(conn)
    except (sqlite3.Error, UnicodeError, ValueError) as exc:
        failure = _open_failure(exc)
        return (failure, unreadable_error(db_path, exc)) if failure else None
    if condition is None:
        return None
    if condition == "invalid":
        return condition, invalid_error(db_path)
    return condition, DatabaseNotReadyError(
        f"database: {condition}: {_shown(db_path)}{_ACTION}"
    )


def _refusal(db_path: str) -> Refusal | None:
    """Why *db_path* cannot answer, or None when it is ready."""
    return _path_problem(db_path) or _open_condition(db_path)


def _header_is_foreign(path: str) -> bool:
    """Whether the file's first bytes are not SQLite's. Read with the stat
    already done, so *path* is known to be a regular file."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(len(_SQLITE_HEADER))
    except OSError:
        return True  # it was there a moment ago: not ours to claim
    return bool(head) and head != _SQLITE_HEADER


def _not_our_file(db_path: str) -> bool:
    """Whether *db_path* holds something licenseid cannot have built.

    True for a path naming no file at all (``.``, ``/``), anything that is
    not a regular file (a directory, a FIFO, a socket, a device), a file this
    process may not look at, and a file whose first bytes are not SQLite's. A
    damaged database keeps its header, so the commands that repair one still
    work on it.

    False only for a regular SQLite-headed file, an empty one, and a path
    with nothing at it: ``update`` may create a database at any of those.
    """
    path = named_file(db_path)
    if path is None:
        # An in-memory database has no file to protect. Any other name
        # SQLite alone can resolve (a URI with its own VFS, or a host) names
        # a file this cannot check, so it is not licenseid's to touch.
        return not is_memory_database(db_path)
    if not Path(path).name:
        return True  # "." and "/" name no file of their own
    try:
        mode = os.stat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return False
    except (OSError, ValueError):
        # ValueError: an embedded NUL. Either way it cannot be looked at, so
        # it cannot be claimed.
        return True
    # Never open() what is not a regular file: a FIFO with no writer blocks.
    return not stat.S_ISREG(mode) or _header_is_foreign(path)


def reject_foreign_database(db_path: str | os.PathLike[str]) -> None:
    """Raise :class:`DatabaseNotReadyError` unless *db_path* is licenseid's to
    write to and delete.

    ``update`` and ``--clear-cache`` change the file, so they call this
    first: one mistyped ``--db`` must not write licenseid's schema over
    another program's database, or delete somebody's notes. A missing, empty
    or damaged database is fine — that is what those two commands are for.

    A database the check could not read (``unknown``: another process holds a
    lock, or a journal it may not replay) is refused as well. Reading may go
    ahead on a guess; writing and deleting may not.
    """
    db_path = os.fspath(db_path)
    if _not_our_file(db_path):
        raise invalid_error(db_path)
    refusal = _refusal(db_path)
    if refusal and refusal[0] in ("invalid", "unknown"):
        raise refusal[1]


def check_database_ready(db_path: str | os.PathLike[str]) -> None:
    """Raise :class:`DatabaseNotReadyError` unless *db_path* is a ready database.

    Ready means the ``licenses``, ``db_metadata`` and ``license_index``
    (FTS5) tables exist with the columns licenseid reads, the metadata holds
    a non-blank ``license_list_version``, ``licenses`` and ``license_index``
    each have a row, and every ``license_id`` is text (a NULL or blob key
    counts as not ready, because normalising one raises). The version is
    written in the same transaction as those rows, so it marks them complete.
    The fingerprints are computed in a later transaction and are not checked
    (an open item in the tech-debt roadmap).

    The file is opened read-only and is never created or written. A
    write-ahead-log file may get -shm and -wal files beside it, which stay
    until a writer next closes it. Where that read cannot be done at all —
    a directory that cannot be written to, or a lock somebody else holds —
    the check makes no claim and lets the command go on to find out.
    """
    refusal = _refusal(os.fspath(db_path))  # a Path worked before this check
    if refusal and refusal[0] != "unknown":
        raise refusal[1]

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the contents of an open licence database call for: the verdict of
``dbcheck`` once SQLite has opened the file (``connection_refusal``), and
what ``update`` builds again (``rebuild_refusal``).

``invalid`` is another program's file, ``empty`` one licenseid built with
too few tables or rows, ``outdated`` one of older rules or of 0.9.x's shape
(the texts in the FTS5 table, never read), ``newer`` one a newer licenseid
built in a shape this one cannot read. Each refusal keeps its condition
tag (:data:`Refusal`), so a read (fail-open) and a write or delete
(fail-closed) apply their own policy to it. Reads only. Standard library,
``dbschema`` and ``errors`` only.
"""

import sqlite3

from licenseid.dbschema import (
    RETIRED_SHADOWS,
    RETIRED_TABLES,
    SCHEMA_OBJECTS,
    TEXT_TABLE,
    has_shape,
    stamped_rules,
)
from licenseid.errors import DatabaseNotReadyError, shown

ACTION = "; run 'licenseid update'"
# The tag of a newer licenseid's file this one cannot read.
NEWER = "newer"

_REQUIRED_TABLES = {"licenses", "db_metadata"}
# The table of the texts: this build's, or the FTS5 one of 0.9.x, which only
# tells that the file is licenseid's (never read).
_TEXT_TABLES = (TEXT_TABLE, *RETIRED_TABLES)
_REQUIRED_COLUMNS = ("license_id", "name", "is_spdx", "is_osi_approved", "is_fsf_libre")
_META_COLUMNS = ("key", "value")
_TEXT_COLUMNS = ("license_id", "search_text")

_KNOWN_OBJECTS = (*SCHEMA_OBJECTS, *RETIRED_TABLES)
# A table of an older build: the FTS5 table, or one of its shadow tables.
_RETIRED_OBJECT = f"""
    SELECT 1 FROM sqlite_master
    WHERE name IN ({", ".join(repr(name) for name in RETIRED_TABLES)})
       OR name LIKE '{RETIRED_SHADOWS}' ESCAPE '\\'
    LIMIT 1
"""
# An object licenseid does not create: not one of its tables or indexes, nor
# the FTS5 table of an older build (with its shadow tables), nor SQLite's own.
_FOREIGN_OBJECT = f"""
    SELECT 1 FROM sqlite_master
    WHERE name NOT IN ({", ".join(repr(name) for name in _KNOWN_OBJECTS)})
      AND name NOT LIKE '{RETIRED_SHADOWS}' ESCAPE '\\'
      AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\'
    LIMIT 1
"""

Refusal = tuple[str, DatabaseNotReadyError]  # the condition, and how to say it


def refused(condition: str, detail: str, action: str = "") -> DatabaseNotReadyError:
    """The refusal ``database: <condition>: <detail>[<action>]``, which keeps
    its *condition* and *detail* apart (``DatabaseNotReadyError.condition``)
    for a caller that answers each condition its own way. *action* starts
    with ``"; "``."""
    return DatabaseNotReadyError(
        f"database: {condition}: {detail}{action}", condition, detail
    )


def invalid_error(db_path: str) -> DatabaseNotReadyError:
    """The refusal for a file licenseid did not build and must not write to.

    No action: every one licenseid could offer would change the file.
    """
    return refused("invalid", shown(db_path))


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
    # The name of 0.9.x's FTS5 table: licenseid never made a plain table of it.
    if "license_index" in tables and "fts5" not in tables["license_index"].lower():
        return True
    # Another program's table of texts; one of these columns and another
    # shape is a misshaped table of this build (``dbschema.has_shape``).
    return TEXT_TABLE in tables and not _has_columns(conn, TEXT_TABLE, _TEXT_COLUMNS)


# A row whose normalised id or name, which ``update`` always writes and a
# lookup reads as stored, is not text (NULL in a row a script inserted): the
# lookups find one where they read the names (``dbcache``); ``update``
# rebuilds a file that holds one (:func:`rebuild_refusal`).
_NORM_NOT_TEXT = """
    SELECT 1 FROM licenses NOT INDEXED
    WHERE typeof(norm_license_id) != 'text' OR typeof(norm_name) != 'text'
    LIMIT 1
"""


def _has_content(conn: sqlite3.Connection) -> bool:
    """Whether the version and the licence rows are there. The texts are
    judged with the shape (:func:`connection_refusal`): a file of 0.9.x
    holds them in a table that is never read."""
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
    return not conn.execute(
        "SELECT 1 FROM licenses NOT INDEXED WHERE typeof(license_id) != 'text' LIMIT 1"
    ).fetchone()


def _not_ready(conn: sqlite3.Connection) -> str | None:
    """The condition that keeps the database from answering, or None if it can.

    ``invalid`` is a file licenseid did not build: one of its table names
    carrying somebody else's schema, or objects licenseid does not create
    beside an incomplete set of its own tables (the licences, the metadata,
    and the texts' table of this build or of 0.9.x). ``licenseid update``
    would write into such a file, so no action is offered.
    """
    names = ("licenses", "db_metadata", *_TEXT_TABLES)
    tables: dict[str, str] = {
        name: str(sql)
        for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            f" AND name IN ({', '.join('?' * len(names))})",
            names,
        )
    }
    if _foreign_schema(conn, tables):
        return "invalid"
    if not _REQUIRED_TABLES <= tables.keys() or tables.keys().isdisjoint(_TEXT_TABLES):
        return "invalid" if conn.execute(_FOREIGN_OBJECT).fetchone() else "empty"
    return None if _has_content(conn) else "empty"


def connection_refusal(conn: sqlite3.Connection, db_path: str) -> Refusal | None:
    """The refusal the contents of the file open on *conn* call for, or None
    when it can answer. Reads only.

    ``invalid`` is another program's file and ``empty`` one with too few
    tables or rows (as :func:`_not_ready` says). A file licenseid built is
    then judged by its stamps: one of older rules is ``outdated`` (``database:
    build v7 outdated: current v10; run 'licenseid update'``, normalisation
    first), a file of 0.9.x too, whose texts are in the FTS5 table this build
    never reads. Last, a file that lacks a table, index or column of this
    build, or has no text, cannot be read: with a newer stamp it is
    ``newer`` (``database: build v11 newer: current v10``, no action:
    ``update`` never builds a newer licenseid's file again), else ``empty``,
    as a lookup has no second way to read an older shape and ``update``
    builds it again. The stamps are read before the shape: no query more. A
    row whose normalised id or name is not text is found where the
    names are read (``dbcache``), not here: that pass cost every opening a
    scan of the licences."""
    condition = _not_ready(conn)
    if condition == "invalid":
        return condition, invalid_error(db_path)
    if condition is not None:
        return empty_refusal(db_path)
    stamps = _stamps(conn)
    older = stamped_rules(stamps, newer=False)
    if older:
        return "outdated", refused(*older[0], ACTION)
    if not has_shape(conn) or not conn.execute(_ANY_TEXT).fetchone():
        return _newer_refusal(stamps) or empty_refusal(db_path)
    return None


def _stamps(conn: sqlite3.Connection) -> dict[str, object]:
    """The build and normalisation stamps of the file, by key."""
    return dict(
        conn.execute(
            "SELECT key, value FROM db_metadata"
            " WHERE key IN ('normalization_version', 'build_version')"
        )
    )


def _newer_refusal(stamps: dict[str, object]) -> Refusal | None:
    """``newer`` for *stamps* newer than this licenseid's (``database:
    build v11 newer: current v10``, no action), else None."""
    newer = stamped_rules(stamps, newer=True)
    return (NEWER, refused(*newer[0])) if newer else None


# The texts are what a text match reads: none answers "no licence".
_ANY_TEXT = f"SELECT 1 FROM {TEXT_TABLE} LIMIT 1"


def empty_refusal(db_path: str) -> Refusal:
    """The refusal of a file licenseid built that has too few tables or rows
    to answer: ``database: empty: <path>; run 'licenseid update'``."""
    return "empty", refused("empty", shown(db_path), ACTION)


def rebuild_refusal(conn: sqlite3.Connection, db_path: str) -> Refusal | None:
    """:func:`connection_refusal`, for ``update``. A file it can read whose
    stamp is newer is ``newer`` too: ``update`` never writes a newer
    licenseid's file but with ``--force``, and judges nothing more in it.
    Else ``empty`` for a row whose normalised id or name is not text, which
    the lookups refuse only where they read the names, or for a table of an
    older build left beside this one's, which they never read: what
    ``update`` builds again although it holds the release asked for. Reads
    only."""
    refusal = connection_refusal(conn, db_path)
    if refusal is not None:
        return refusal
    newer = _newer_refusal(_stamps(conn))
    if newer is not None:
        return newer
    if (
        conn.execute(_NORM_NOT_TEXT).fetchone()
        or conn.execute(_RETIRED_OBJECT).fetchone()
    ):
        return empty_refusal(db_path)
    return None

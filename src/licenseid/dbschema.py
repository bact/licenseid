# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The tables and indexes of a licence database: what makes one, and whether
a file has them all.

Stdlib only, so ``dbcheck`` can name them without importing a connection.
"""

import sqlite3
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from licenseid.dbconnection import Connections

# Every table and index licenseid creates, but not the shadow tables of the
# FTS5 index (``license_index_*``) or SQLite's own.
SCHEMA_OBJECTS = (
    "licenses",
    "exceptions",
    "license_index",
    "db_metadata",
    "license_fingerprints",
    "idx_fp_ngram",
    "idx_licenses_name",
)

# Columns that databases of an earlier version lack; ``create_schema`` adds
# them.
_ADDED_COLUMNS = ("norm_license_id", "norm_name")

SchemaState = Literal["current", "older", "none"]


def schema_state(connections: "Connections") -> SchemaState:
    """``current`` when every object of ``SCHEMA_OBJECTS`` and every added
    column is there (opening the database needs no write), ``older`` when the
    ``licenses`` table is there but something is missing, ``none`` when it is
    not. Read-only: it raises ``DatabaseNotReadyError`` for a file it cannot
    open."""
    marks = ", ".join("?" * len(SCHEMA_OBJECTS))
    with connections.connection() as conn:
        found = {
            row[0]
            for row in conn.execute(
                f"SELECT name FROM sqlite_master WHERE name IN ({marks})",
                SCHEMA_OBJECTS,
            )
        }
        columns = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
    if found == set(SCHEMA_OBJECTS) and set(_ADDED_COLUMNS) <= columns:
        return "current"
    return "older" if "licenses" in found else "none"


def create_schema(conn: sqlite3.Connection) -> None:
    """Create what is missing: every table and index, and the added columns of
    a database that predates them.

    One transaction that takes the write lock first: two processes opening an
    older database at once would else both see a column missing, and the
    second ``ALTER TABLE`` would fail with ``duplicate column name``."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _create_objects(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _create_objects(conn: sqlite3.Connection) -> None:
    """The statements of ``create_schema``, inside its transaction."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_id TEXT PRIMARY KEY,
            name TEXT,
            xml_template TEXT,
            legacy_template TEXT,
            ignorable_metadata TEXT,
            is_spdx BOOLEAN,
            is_osi_approved BOOLEAN,
            is_fsf_libre BOOLEAN,
            is_high_usage BOOLEAN,
            is_deprecated BOOLEAN,
            superseded_by TEXT,
            pop_score INTEGER DEFAULT 1,
            word_count INTEGER,
            norm_license_id TEXT,
            norm_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exceptions (
            exception_id TEXT PRIMARY KEY,
            name TEXT,
            is_deprecated BOOLEAN,
            superseded_by TEXT
        )
    """)

    # Create FTS5 virtual table for trigram search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS license_index USING fts5(
            license_id UNINDEXED,
            search_text,
            tokenize = 'trigram'
        )
    """)
    # Metadata table for version tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS db_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Discriminative n-gram fingerprints.
    # idf_norm: IDF score normalised to [0, 1] where 1.0 means the
    # n-gram appears in exactly one license in the corpus.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_fingerprints (
            license_id  TEXT NOT NULL,
            ngram       TEXT NOT NULL,
            idf_norm    REAL NOT NULL,
            PRIMARY KEY (license_id, ngram),
            FOREIGN KEY (license_id) REFERENCES licenses(license_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fp_ngram
        ON license_fingerprints(ngram)
    """)
    # get_license_by_name() and every case-insensitive name lookup
    # in markers.py's _try_license_lookup() (tried for ~10 name
    # variants per marker candidate) query "name COLLATE NOCASE"
    # with no index otherwise available, forcing SQLite to do a
    # full table scan every time.  This index lets it seek instead.
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_licenses_name
        ON licenses(name COLLATE NOCASE)
    """)

    # Migration: databases created before norm_license_id/norm_name
    # existed have a "licenses" table without them (CREATE TABLE IF
    # NOT EXISTS above only creates the table when missing entirely,
    # it doesn't add columns to one that already exists).
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
    if "norm_license_id" not in existing_cols:
        conn.execute("ALTER TABLE licenses ADD COLUMN norm_license_id TEXT")
    if "norm_name" not in existing_cols:
        conn.execute("ALTER TABLE licenses ADD COLUMN norm_name TEXT")

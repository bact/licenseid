# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The one shape of a licence database: its tables and indexes, the stamps of
the rules that built it, what makes one, and whether a file has it all.

licenseid reads only a file of its own build: one with an older stamp, or
without a table or column of this shape, is not ready (``dbcheck``), and
``update`` builds it again from nothing (:func:`replace_schema`).

Stdlib only, so ``dbcheck`` can judge a file without importing a connection
or the builder.
"""

import re
import sqlite3
from collections.abc import Mapping

# Version of the normalize_text() rule set used to build the stored
# search_text and fingerprints. Bump whenever normalization rules change: a
# database built with the old rules is then not ready until ``update``.
# Version 2: SPDX Matching Guidelines rules (varietal words, bullets,
# copyright notices, comment prefixes, separators).
NORMALIZATION_VERSION = "2"

# Version of the rules that turn a release into rows (``records``) and of
# this shape. A database stores the version it was built with; one built
# with older rules is not ready until ``update`` builds it again.
# Version 2: a renamed deprecated ID records its successor (StandardML-NJ).
# Version 3: a deprecated ID without a text keeps the OSI and FSF flags the
# List gives it (wxWindows, eCos-2.0); they were both False.
# Version 4: the pages of each kept licence and every exception (``seeAlso``)
# go to ``license_urls``, so that a licence URL can be read as its licence.
# Version 5: ``core_text``, ``core_word_count`` (the template without its
# optional parts, when that is shorter) and ``same_text`` (the licences whose
# text is the same) are stored.
# Version 6: ``text_codes`` holds the List texts as word codes
# (``textstore.stored_rows``), so the search of whole texts reads
# them instead of coding every text again at its first use.
# Version 7: ``text_codes`` holds the regions of each text's variable parts
# (``templatevars``) and their patterns, so the search of whole texts leaves
# a copy's own copyright holder or project name out of its fit.
# Version 8: ``text_postings`` and ``text_posting_ids`` hold the word 3-gram
# postings of the List texts (``gramstore``), with their stamp; a change to
# the gram spec (``textgrams``) bumps it too.
# Version 9: ``text_code_checks`` holds a check of the head of
# ``text_codes`` and one of each entry (``textentries.write_checks``), so a
# lookup reads the entries of its candidates only; ``text_codes`` holds the
# gram counts of the cores and no check of the whole corpus.
# Version 10: the texts are in a plain table, ``license_texts``; the FTS5
# table ``license_index``, whose trigram index nothing read, is gone.
BUILD_VERSION = "10"

# The flags of a licence: BOOLEAN columns, which SQLite stores as integers.
LICENSE_FLAGS = (
    "is_spdx",
    "is_osi_approved",
    "is_fsf_libre",
    "is_high_usage",
    "is_deprecated",
)
# Every table licenseid creates, with every column it creates in it. A file
# that lacks one is not of this build. SQLite's own tables are not listed:
# ``dbcheck`` calls any other object foreign, but those of RETIRED_TABLES.
TABLES: Mapping[str, tuple[str, ...]] = {
    "licenses": (
        "license_id",
        "name",
        "xml_template",
        "legacy_template",
        "ignorable_metadata",
        *LICENSE_FLAGS,
        "superseded_by",
        "pop_score",
        "word_count",
        "norm_license_id",
        "norm_name",
        "core_text",
        "core_word_count",
        "same_text",
    ),
    "exceptions": ("exception_id", "name", "is_deprecated", "superseded_by"),
    "license_texts": ("text_id", "license_id", "search_text"),
    "db_metadata": ("key", "value"),
    "license_fingerprints": ("license_id", "ngram", "idf_norm"),
    "license_urls": ("owner_id", "is_exception", "url"),
    "text_codes": ("kind", "owner_id", "body"),
    "text_postings": ("h", "ids"),
    "text_posting_ids": ("k", "id", "size"),
    "text_code_checks": ("owner_id", "digest"),
}
INDEXES = ("idx_fp_ngram", "idx_licenses_name")
SCHEMA_OBJECTS = (*TABLES, *INDEXES)
#: The table of the texts, read by every reader of a text by ID or by row.
TEXT_TABLE = "license_texts"
#: Tables an older build made and this one does not (the FTS5 index of the
#: texts until build 9, with its shadow tables ``license_index_*``): known
#: only so that a file of 0.9.x is seen as licenseid's own (``dbverdict``) and
#: so that ``update`` drops them (:func:`replace_schema`). Never read.
RETIRED_TABLES = ("license_index",)
#: The shadow tables of the FTS5 table, as a ``LIKE`` pattern (escaped with
#: ``\``): SQLite drops them with their table, a damaged file may hold one alone.
RETIRED_SHADOWS = "license\\_index\\_%"
#: The column that names the rowid of a table whose row order readers keep.
ROWID_KEYS: Mapping[str, str] = {TEXT_TABLE: "text_id"}
# The tables made WITHOUT ROWID; every other one has a rowid.
WITHOUT_ROWID = frozenset({"text_codes", "text_code_checks"})
_WITHOUT_ROWID_SQL = re.compile(r"\bWITHOUT\s+ROWID\s*\Z", re.ASCII | re.IGNORECASE)


def has_shape(conn: sqlite3.Connection) -> bool:
    """Whether every table and index of this build is there, each table a
    table (not a view), with a rowid unless it is made WITHOUT ROWID
    (:data:`WITHOUT_ROWID`), with every column of :data:`TABLES`, and the
    rowid of the texts named by their integer key (:data:`ROWID_KEYS`).
    Reads only."""
    marks = ", ".join("?" * len(SCHEMA_OBJECTS))
    found = {
        name: (kind, sql)
        for name, kind, sql in conn.execute(
            f"SELECT name, type, sql FROM sqlite_master WHERE name IN ({marks})",
            SCHEMA_OBJECTS,
        )
    }
    if found.keys() != set(SCHEMA_OBJECTS) or any(
        found[name][0] != "index" for name in INDEXES
    ):
        return False
    if any(
        found[table][0] != "table"
        or bool(_WITHOUT_ROWID_SQL.search(str(found[table][1])))
        != (table in WITHOUT_ROWID)
        for table in TABLES
    ):
        return False
    for table, columns in TABLES.items():
        # Each table is one of the fixed names above, never user input.
        info = {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}
        key = ROWID_KEYS.get(table)
        if not set(columns) <= info.keys() or (key and not _rowid_key(info, key)):
            return False
    return True


def _rowid_key(info: Mapping[str, tuple[object, ...]], key: str) -> bool:
    """Whether the column *key* of a table (its ``PRAGMA table_info`` rows by
    name) is its one ``INTEGER PRIMARY KEY``, the rowid's own name: an order
    ``VACUUM`` keeps."""
    column = info[key]
    keys = [row for row in info.values() if row[5]]
    return str(column[2]).upper() == "INTEGER" and keys == [column]


def stamp(value: object) -> int:
    """A build stamp as a number to compare: -1 for one that is no short
    ASCII number, which no licenseid wrote, so it is older than any."""
    return (
        int(value)
        if isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) < 10
        else -1
    )


def stamped_rules(metadata: Mapping[str, object], newer: bool) -> list[tuple[str, str]]:
    """The rules a database's *metadata* says it was built with that are
    older than this licenseid's, each as a condition and its detail
    (``normalization v1 outdated``, ``current v2``), normalisation first; a
    stamp that is missing or no number counts as older. With *newer*, the
    newer ones (``build v8 newer``): a later licenseid built it, and
    rebuilding would downgrade it.

    Stored search_text and fingerprints are normalised at build time; if the
    normalize_text() rules changed since, query-side normalisation no longer
    matches the index. Rows built by older records rules miss what those
    rules now record."""
    built = (
        (
            "normalization",
            metadata.get("normalization_version", "1"),
            NORMALIZATION_VERSION,
        ),
        ("build", metadata.get("build_version", "1"), BUILD_VERSION),
    )
    condition = "newer" if newer else "outdated"
    found = []
    for rules, stored, current in built:
        ahead = stamp(stored) - stamp(current)
        if (ahead > 0) if newer else (ahead < 0):
            found.append((f"{rules} v{stored} {condition}", f"current v{current}"))
    return found


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every table and index a file with none of them lacks.

    One transaction that takes the write lock first, so two processes
    making the tables at once do not interleave."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _create_objects(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def replace_schema(conn: sqlite3.Connection) -> None:
    """Drop licenseid's tables, with their indexes, and those of an older
    build (:data:`RETIRED_TABLES`: the FTS5 table, which drops its shadow
    tables, then any shadow table left alone), and create the shape of this
    build: ``update`` builds every file from nothing, whatever build made it.
    Inside the caller's transaction.

    An object of one of its names that has another kind (a view, or an index
    of a table's name) is dropped as what it is (roadmap item 66)."""
    names = (*SCHEMA_OBJECTS, *RETIRED_TABLES)
    marks = ", ".join("?" * len(names))
    found = conn.execute(
        f"SELECT type, name FROM sqlite_master WHERE name IN ({marks})", names
    ).fetchall()
    for kind, name in found:  # a fixed name; a table, index, view or trigger
        conn.execute(f"DROP {kind.upper()} IF EXISTS {name}")
    shadows = conn.execute(
        "SELECT type, name FROM sqlite_master"
        f" WHERE name LIKE '{RETIRED_SHADOWS}' ESCAPE '\\'"
    ).fetchall()
    for kind, name in shadows:  # left alone; the name quoted, as it may be any
        quoted = name.replace('"', '""')
        conn.execute(f'DROP {kind.upper()} IF EXISTS "{quoted}"')
    _create_objects(conn)


def _create_objects(conn: sqlite3.Connection) -> None:
    """The statements that make every table and index, inside a transaction."""
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
            norm_name TEXT,
            core_text TEXT,
            core_word_count INTEGER,
            same_text TEXT
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
    # The normalised text of each licence that has one, in List order: the
    # rowid (text_id) is the order every reader keeps (the first row of an
    # ID wins), and a lookup by ID seeks on it through the IDs that
    # dbcache.TableCache reads once (index_rows), so none scans.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_texts (
            text_id     INTEGER PRIMARY KEY,
            license_id  TEXT,
            search_text TEXT
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
    # get_license_by_name(), and through it markers' _try_license_lookup()
    # (about 10 name variants per marker candidate), query
    # "name COLLATE NOCASE": this index lets SQLite seek, not scan.
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_licenses_name
        ON licenses(name COLLATE NOCASE)
    """)
    # The pages (seeAlso) of each kept licence and every exception, as the
    # List writes them, in List order (rowid): the licences, then the
    # exceptions. No index: the table is read whole, once per rebuild
    # (dbcache.TableCache.ids_by_url), and keyed in memory.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_urls (
            owner_id     TEXT NOT NULL,
            is_exception BOOLEAN NOT NULL,
            url          TEXT NOT NULL
        )
    """)
    # The List texts as word codes (textstore.stored_rows): the head (the
    # vocabulary, the patterns, the gram counts of the cores) and one row for
    # each text and core, read per candidate (textentries), each under its
    # check in text_code_checks (the head's has the owner '').
    conn.execute("""
        CREATE TABLE IF NOT EXISTS text_codes (
            kind     TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            body     TEXT NOT NULL,
            PRIMARY KEY (kind, owner_id)
        ) WITHOUT ROWID
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS text_code_checks (
            owner_id TEXT PRIMARY KEY,
            digest   TEXT
        ) WITHOUT ROWID
    """)
    # The word 3-gram postings of the texts (gramstore.write_postings): the
    # texts by number, then per gram hash the numbers of the texts that hold
    # it, one blob. Used only under their stamp in db_metadata.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS text_postings (
            h   INTEGER PRIMARY KEY,
            ids BLOB
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS text_posting_ids (
            k    INTEGER PRIMARY KEY,
            id   TEXT,
            size INTEGER
        )
    """)

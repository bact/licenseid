# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The INSERT statements that seed a test database.

A module of its own, with no import from the tests, so ``conftest`` (through
``resolver_corpus``) and ``matcher_db`` (which imports ``conftest``) can both
use it without a cycle. ``tests/cli_matrix_env.py`` keeps its own statements:
it is a ``tools.cli_matrix`` helper that inserts fewer columns.
"""

import sqlite3

from licenseid.normalize import normalize_text

INSERT_LICENSE = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved,"
    " is_fsf_libre, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
)
INSERT_INDEX = "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)"
INSERT_EXCEPTION = (
    "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?)"
)
INSERT_URL = "INSERT INTO license_urls (owner_id, is_exception, url) VALUES (?, ?, ?)"
INSERT_METADATA = "INSERT INTO db_metadata (key, value) VALUES (?, ?)"
SET_METADATA = "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)"


def fill_norm_columns(conn: sqlite3.Connection) -> None:
    """Give each row a script inserted without them the normalised ID and
    name ``update`` writes (``records``): a lookup reads them as stored, and
    a row without them is not ready (``dbcheck``)."""
    rows = conn.execute(
        "SELECT rowid, license_id, name FROM licenses"
        " WHERE norm_license_id IS NULL OR norm_name IS NULL"
    ).fetchall()
    conn.executemany(
        "UPDATE licenses SET norm_license_id = coalesce(norm_license_id, ?),"
        " norm_name = coalesce(norm_name, ?) WHERE rowid = ?",
        [
            (normalize_text(str(license_id)), normalize_text(str(name or "")), rowid)
            for rowid, license_id, name in rows
        ],
    )

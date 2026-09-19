# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Seeding helper for matcher tests that build their own licence tables.

Import as ``from matcher_db import Lic, seeded_db`` (tests have no
``__init__.py``).  ``seeded_db`` is a fixture *body*: a fixture yields
from it so the in-memory database is torn down with the test.
"""

import sqlite3
from collections.abc import Generator, Sequence
from typing import NamedTuple

from conftest import make_memory_db_path

_INSERT_LICENSE = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved,"
    " is_fsf_libre, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
)
_INSERT_INDEX = "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)"
_INSERT_EXCEPTION = (
    "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?)"
)
_INSERT_METADATA = "INSERT INTO db_metadata (key, value) VALUES (?, ?)"


class Lic(NamedTuple):
    """One row of the ``licenses`` table, plus its ``license_index`` text.

    A row is indexed for FTS5 only when ``search_text`` is non-empty, so
    a licence can be given a name but no searchable body.
    """

    license_id: str
    name: str
    is_spdx: bool = True
    is_osi_approved: bool = False
    is_fsf_libre: bool = False
    is_deprecated: bool = False
    superseded_by: str | None = None
    search_text: str = ""


def seeded_db(
    prefix: str,
    rows: Sequence[Lic],
    exception_ids: Sequence[str] = (),
) -> Generator[str, None, None]:
    """Yield the path of an in-memory database seeded with *rows*.

    Closes the keep-alive connection afterwards, which drops the
    shared-cache database.
    """
    db_path, keep_alive = make_memory_db_path(prefix)
    with sqlite3.connect(db_path, uri=True) as conn:
        for row in rows:
            conn.execute(_INSERT_LICENSE, tuple(row)[:7])
            if row.search_text:
                conn.execute(_INSERT_INDEX, (row.license_id, row.search_text))
        for exception_id in exception_ids:
            conn.execute(_INSERT_EXCEPTION, (exception_id, exception_id, False, None))
        conn.execute(_INSERT_METADATA, ("last_check_datetime", "2026-01-01T00:00:00"))
    yield db_path
    keep_alive.close()

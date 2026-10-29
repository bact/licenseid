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
from seed_sql import INSERT_EXCEPTION, INSERT_INDEX, INSERT_LICENSE, INSERT_METADATA

# Prose long enough to push an input over the 30-word threshold, so
# Tier 0.5 (marker detection) runs instead of Tier 0 (short text).
PROSE = (
    " * This module implements the widget scheduler used by the runtime.\n"
    " * It keeps a queue of pending widgets and dispatches them to worker\n"
    " * threads in arrival order, retrying transient failures a few times\n"
    " * before giving up and reporting an error to the caller.\n"
)


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


# The GPL-2.0 family: both canonical IDs and the deprecated bare one, whose
# own flags differ from GPL-2.0-only's, which it answers.
GPL2_ROWS = (
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True, True),
    Lic(
        "GPL-2.0-or-later", "GNU General Public License v2.0 or later", True, True, True
    ),
    Lic("GPL-2.0", "GNU General Public License v2.0", False, is_deprecated=True),
)


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
            conn.execute(INSERT_LICENSE, tuple(row)[:7])
            if row.search_text:
                conn.execute(INSERT_INDEX, (row.license_id, row.search_text))
        if rows and not any(row.search_text for row in rows):
            # A database with an empty search index is not ready; this text
            # matches nothing the tests search for.
            conn.execute(INSERT_INDEX, (rows[0].license_id, "unmatchable filler"))
        for exception_id in exception_ids:
            conn.execute(INSERT_EXCEPTION, (exception_id, exception_id, False, None))
        conn.execute(INSERT_METADATA, ("last_check_datetime", "2026-01-01T00:00:00"))
    yield db_path
    keep_alive.close()

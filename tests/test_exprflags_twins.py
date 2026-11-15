# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A kept bare deprecated ID (``GPL-2.0``) and a deprecated ``-with-`` ID are
judged by their ``-only`` twin, not by their own List rows
(``licenseid.exprflags.judged_id``, roadmap item 52)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.deprecatedids import BARE_TO_OR_LATER, DEPRECATED_BARE_LICENSE_IDS
from licenseid.exprflags import judged_flags, judged_id, with_judged_flags
from licenseid.retrieval import _inject_hinted_candidates

# The developer's cache, read only; the fixture of the home folder moves HOME.
_CACHE = Path.home() / ".local" / "share" / "licenseid" / "licenses.db"

ROWS = (
    # The bare rows say what the twins do not (as List 3.29.0 AGPL-1.0, and
    # its GPL-2.0-with-* rows): they must not be read.
    Lic("GPL-2.0", "GNU GPL v2.0 only", True, False, False, True),
    Lic("GPL-2.0-only", "GNU GPL v2.0 only", True, True, True),
    Lic("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, True, True),
    Lic("AGPL-1.0", "Affero GPL v1.0", True, False, True, True),
    Lic("AGPL-1.0-only", "Affero GPL v1.0 only", True, False, False),
    Lic("GPL-2.0-with-classpath-exception", "w/Classpath", True, False, False, True),
)


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("exprflags_twins", ROWS, ["Classpath-exception-2.0"]):
        yield LicenseDatabase(path, create=False)


@pytest.mark.parametrize(
    ("value", "osi", "fsf"),
    [
        ("GPL-2.0", True, True),  # the bare row is 0/0
        ("gpl-2.0", True, True),
        ("AGPL-1.0", False, False),  # the bare row is FSF-libre; its twins are not
        ("GPL-2.0-with-classpath-exception", True, True),
        ("GPL-2.0-only WITH Classpath-exception-2.0", True, True),
        ("GPL-2.0-or-later", True, True),
    ],
)
def test_a_kept_deprecated_id_is_judged_by_its_twin(
    db: LicenseDatabase, value: str, osi: bool, fsf: bool
) -> None:
    flags = judged_flags(value, db)
    assert flags is not None
    assert flags["is_spdx"] is True  # on the List as written, whatever its twin says
    assert (flags["is_osi_approved"], flags["is_fsf_libre"]) == (osi, fsf)


def test_a_row_of_a_deprecated_id_takes_the_flags_of_its_twin(
    db: LicenseDatabase,
) -> None:
    row = db.get_license_details("GPL-2.0")
    assert row is not None and not row["is_osi_approved"]
    judged = with_judged_flags(row, db)
    assert (judged["license_id"], judged["is_osi_approved"]) == ("GPL-2.0", True)
    assert row["is_osi_approved"] is False  # the row is not changed


def test_a_hinted_bare_id_keeps_its_name_and_the_flags_of_its_twin(
    db: LicenseDatabase,
) -> None:
    cand = _inject_hinted_candidates(db, [], ["GPL-2.0"])[0]
    assert (cand["license_id"], cand["is_osi_approved"], cand["is_fsf_libre"]) == (
        "GPL-2.0",
        True,
        True,
    )


@pytest.mark.parametrize(
    ("ident", "twin"),
    [
        ("GPL-2.0", "GPL-2.0-only"),
        ("gpl-2.0-WITH-classpath-exception", "GPL-2.0-only"),  # any case
        ("MIT", "MIT"),
        ("GPL-2.0-only", "GPL-2.0-only"),
    ],
)
def test_the_judged_id(ident: str, twin: str) -> None:
    assert judged_id(ident) == twin


def test_the_twins_of_the_real_list_have_equal_flags() -> None:
    """The reason to judge by one twin: every ``-only``/``-or-later`` pair of
    a bare deprecated ID has the same OSI and FSF flags (read-only on the
    developer's cache; skipped when there is none)."""
    path = _CACHE
    if not path.is_file():
        pytest.skip("no database in the cache")
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as conn:
        for bare, only in DEPRECATED_BARE_LICENSE_IDS.items():
            later = BARE_TO_OR_LATER[bare]
            rows = {
                i: conn.execute(
                    "SELECT is_osi_approved, is_fsf_libre FROM licenses"
                    " WHERE license_id = ?",
                    (i,),
                ).fetchone()
                for i in (only, later)
            }
            assert rows[only] == rows[later], bare

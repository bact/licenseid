# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the readers of the texts' table give, by ID and by row, on the List
of the fixtures: written before the texts moved from the FTS5 table to a
plain one (database build 10), and held to the same values after.

Each text is the one ``records`` builds, in List order: the row order every
reader keeps (the first row of an ID wins) is the order of the records."""

# pylint: disable=missing-function-docstring,protected-access

import sqlite3
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import database_of, fixture_bundle, fixture_data

from licenseid.database import LicenseDatabase, candidate_rows
from licenseid.fingerprint import compute_idf_fingerprints
from licenseid.records import build_records
from licenseid.textentries import read_rows


@pytest.fixture(name="built", scope="module")
def _built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[LicenseDatabase, list[tuple[str, str]]]:
    """The fixtures' List built by ``update``, and the texts ``records``
    makes of it, in their order."""
    path = tmp_path_factory.mktemp("texts") / "licenses.db"
    texts = list(build_records(fixture_data(), {}).index_entries)
    return database_of(fixture_bundle(), path), texts


def test_each_id_has_the_row_of_its_place_in_the_records(
    built: tuple[LicenseDatabase, list[tuple[str, str]]],
) -> None:
    db, texts = built
    assert len(texts) > 100
    assert dict(db._tables.index_rows()) == {
        license_id: row for row, (license_id, _) in enumerate(texts, start=1)
    }


def test_each_text_is_read_by_its_id(
    built: tuple[LicenseDatabase, list[tuple[str, str]]],
) -> None:
    db, texts = built
    assert {i: db.get_search_text(i) for i, _ in texts} == dict(texts)
    assert db.get_search_text("mit") == ""  # exact case
    assert db.get_search_text("LicenseRef-x") == ""


def test_candidates_come_in_the_order_asked_with_their_texts(
    built: tuple[LicenseDatabase, list[tuple[str, str]]],
) -> None:
    db, texts = built
    asked = [license_id for license_id, _ in texts[-20:]][::-1]
    rows = candidate_rows(db, [*asked, "NOT-AN-ID"])
    assert [(row["license_id"], row["search_text"]) for row in rows] == [
        (license_id, dict(texts)[license_id]) for license_id in asked
    ]


def test_a_build_reads_the_texts_in_row_order(
    built: tuple[LicenseDatabase, list[tuple[str, str]]],
) -> None:
    db, texts = built
    with db._connection() as conn:
        rows = read_rows(conn, db._tables.text_parts())
    assert [(row.license_id, row.text) for row in rows] == [
        (license_id, text) for license_id, text in texts if text
    ]


def test_the_fingerprints_are_those_of_the_texts(
    built: tuple[LicenseDatabase, list[tuple[str, str]]],
) -> None:
    db, texts = built
    with sqlite3.connect(Path(db.db_path)) as conn:
        stored = conn.execute(
            "SELECT license_id, ngram, idf_norm FROM license_fingerprints"
        ).fetchall()
    assert sorted(stored) == sorted(compute_idf_fingerprints(texts))

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The BSD marker: a licence's numbered conditions name BSD-N-Clause.

BSD-1-Clause with its copyright line filled in ("Copyright (c) 2024 Jane
Doe") is not among Tier 1's candidates on the full 3.29.0 list: the
copyright words take a quarter of the query, and it was answered as a
BSD-2-Clause variant. BSD-2, 3 and 4 survive the same fill through the
marker; one numbered condition gave none, and now gives BSD-1-Clause. A
text cut short after condition 1 of BSD-2 or 3 holds the same condition,
and must not get BSD-1-Clause.

The database holds the BSD family and its near neighbours, each with its
text, so Tiers 1 and 2 retrieve them: a negative test is not trivially true.
"""
# pylint: disable=missing-function-docstring,protected-access

import json
import re
from collections.abc import Generator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid import detector
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.markers import MarkerDetector
from licenseid.normalize import normalize_text
from licenseid.retrieval import get_candidates
from licenseid.types import CandidateMatch

LONG = Path(__file__).parent / "fixtures" / "license-text-long"

NEIGHBOURS = (
    "BSD-1-Clause",
    "BSD-2-Clause",
    "BSD-2-Clause-Darwin",
    "BSD-2-Clause-Patent",
    "BSD-2-Clause-Views",
    "BSD-2-Clause-first-lines",
    "BSD-2-Clause-pkgconf-disclaimer",
    "BSD-3-Clause",
    "BSD-3-Clause-Attribution",
    "BSD-3-Clause-Clear",
    "BSD-3-Clause-LBNL",
    "BSD-3-Clause-No-Military-License",
    "BSD-4-Clause",
    "BSD-4-Clause-UC",
    "BSD-Source-Code",
    "ISC",
    "MIT",
    "Sleepycat",
    "Spencer-94",
)

# The fills the finding was measured with: a year and an owner.
FILLS = (
    ("2024", "Jane Doe"),
    ("2019-2024", "John Smith"),
    ("2023", "Acme Corp."),
    ("2021", "Bob"),
    ("2020", "The Foo Authors"),
    ("2024", "Jane Doe <jane@example.com>"),
    ("1999", "Regents of the University of California"),
)
FILL_IDS = [owner.split()[0] for _, owner in FILLS]


@cache
def text(lic_id: str) -> str:
    with open(LONG / f"{lic_id}.json", encoding="utf-8") as f:
        value: str = json.load(f)["license_text"]
    return value


def filled(lic_id: str, year: str = "2024", owner: str = "Jane Doe") -> str:
    return text(lic_id).replace("<year>", year).replace("<owner>", owner)


def before_condition_2(value: str) -> str:
    """The text cut short just before its condition 2."""
    found = re.search(r"^\s*2\.", value, re.MULTILINE)
    assert found is not None
    return value[: found.start()]


def first_paragraphs(value: str, count: int) -> str:
    return "\n\n".join(value.split("\n\n")[:count])


@pytest.fixture(name="db_path", scope="module")
def _db_path() -> Generator[str, None, None]:
    rows = [
        Lic(lic_id, lic_id, search_text=normalize_text(text(lic_id)))
        for lic_id in NEIGHBOURS
    ]
    yield from seeded_db("test_bsd1_marker", rows)


def marker_ids(db_path: str, value: str) -> list[str]:
    markers = MarkerDetector(LicenseDatabase(db_path, create=False))
    return [c["license_id"] for c in markers._detect_bsd_headers(value)]


def top(db_path: str, value: str) -> str:
    results = LicenseDetector(db_path).detect(text=value)
    return results[0]["expression"] if results else ""


BSD1 = filled("BSD-1-Clause")
DISCLAIMER = BSD1.index("THIS SOFTWARE")


@pytest.mark.parametrize(("year", "owner"), FILLS, ids=FILL_IDS)
def test_a_filled_bsd_1_clause_gets_its_marker(
    db_path: str, year: str, owner: str
) -> None:
    # Was none: on the full list a BSD-2-Clause variant answered it.
    assert marker_ids(db_path, filled("BSD-1-Clause", year, owner)) == ["BSD-1-Clause"]


def test_the_plain_bsd_1_clause_gets_its_marker(db_path: str) -> None:
    assert marker_ids(db_path, text("BSD-1-Clause")) == ["BSD-1-Clause"]


@pytest.mark.parametrize("lic_id", ["BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause"])
@pytest.mark.parametrize(("year", "owner"), FILLS, ids=FILL_IDS)
def test_bsd_n_clause_gets_its_marker(
    db_path: str, lic_id: str, year: str, owner: str
) -> None:
    value = filled(lic_id, year, owner)
    assert marker_ids(db_path, value) == [lic_id]
    assert top(db_path, value) == lic_id


@pytest.mark.parametrize("lic_id", ["BSD-1-Clause", "BSD-2-Clause", "BSD-3-Clause"])
def test_the_plain_text_is_answered_exactly(db_path: str, lic_id: str) -> None:
    results = LicenseDetector(db_path).detect(text=text(lic_id))
    assert results[0]["expression"] == lic_id
    assert results[0]["exact"]


# A BSD-2, 3 or 4 text cut short after its condition 1: the same condition
# as BSD-1-Clause, with no disclaimer after it.
TRUNCATED = {
    f"{lic_id} {how}": value
    for lic_id in ("BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause")
    for how, value in (
        ("before 2", before_condition_2(text(lic_id))),
        ("before 2, filled", before_condition_2(filled(lic_id))),
        ("3 paragraphs", first_paragraphs(text(lic_id), 3)),
        ("3 paragraphs, filled", first_paragraphs(filled(lic_id), 3)),
    )
}


# What Tiers 1 and 2 answer for them, which the marker leaves alone: a BSD-4
# text cut after its condition 1 is the BSD-1-Clause text, word for word,
# but for the clause count.
TRUNCATED_ANSWERS = {
    "BSD-2-Clause before 2": "BSD-2-Clause",
    "BSD-2-Clause before 2, filled": "BSD-2-Clause-pkgconf-disclaimer",
    "BSD-2-Clause 3 paragraphs": "BSD-2-Clause",
    "BSD-2-Clause 3 paragraphs, filled": "BSD-2-Clause-pkgconf-disclaimer",
    "BSD-3-Clause before 2": "BSD-2-Clause",
    "BSD-3-Clause before 2, filled": "BSD-2-Clause-pkgconf-disclaimer",
    "BSD-3-Clause 3 paragraphs": "BSD-2-Clause",
    "BSD-3-Clause 3 paragraphs, filled": "BSD-2-Clause-pkgconf-disclaimer",
    "BSD-4-Clause before 2": "BSD-1-Clause",
    "BSD-4-Clause before 2, filled": "BSD-1-Clause",
    "BSD-4-Clause 3 paragraphs": "BSD-1-Clause",
    "BSD-4-Clause 3 paragraphs, filled": "BSD-1-Clause",
}


@pytest.mark.parametrize("case", TRUNCATED, ids=TRUNCATED.keys())
def test_a_truncated_bsd_text_gets_no_marker(db_path: str, case: str) -> None:
    assert not marker_ids(db_path, TRUNCATED[case])
    assert top(db_path, TRUNCATED[case]) == TRUNCATED_ANSWERS[case]


@pytest.fixture(name="tier1_misses_bsd_1")
def _tier1_misses_bsd_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 1 as the full list makes it: BSD-1-Clause not among the
    candidates of a filled BSD-1-Clause text."""

    def without_bsd_1(*args: Any, **kwargs: Any) -> list[CandidateMatch]:
        found = get_candidates(*args, **kwargs)
        return [c for c in found if c["license_id"] != "BSD-1-Clause"]

    monkeypatch.setattr(detector, "get_candidates", without_bsd_1)


@pytest.mark.usefixtures("tier1_misses_bsd_1")
@pytest.mark.parametrize(("year", "owner"), FILLS, ids=FILL_IDS)
def test_a_filled_bsd_1_clause_missed_by_tier_1_is_answered(
    db_path: str, year: str, owner: str
) -> None:
    # Was a BSD-2-Clause variant, with no marker to bring BSD-1-Clause back.
    assert top(db_path, filled("BSD-1-Clause", year, owner)) == "BSD-1-Clause"


@pytest.mark.usefixtures("tier1_misses_bsd_1")
@pytest.mark.parametrize("case", TRUNCATED, ids=TRUNCATED.keys())
def test_a_truncated_bsd_text_missed_by_tier_1_is_not_bsd_1(
    db_path: str, case: str
) -> None:
    assert top(db_path, TRUNCATED[case]) != "BSD-1-Clause"


# Not BSD-1-Clause, or not a numbered condition this marker reads.
NO_MARKER = {
    "no disclaimer": BSD1[:DISCLAIMER],
    "bulleted": BSD1.replace("1. Redistributions", "* Redistributions"),
    "unnumbered": BSD1.replace("1. Redistributions", "Redistributions"),
    "1) numbered": BSD1.replace("1. Redistributions", "1) Redistributions"),
    "reflowed": " ".join(BSD1.split()),
    "disclaimer first": BSD1[DISCLAIMER:] + "\n\n" + BSD1[:DISCLAIMER],
    "binary form unnumbered": BSD1[:DISCLAIMER]
    + "Redistributions in binary form must reproduce the above copyright"
    " notice.\n\n" + BSD1[DISCLAIMER:],
    "endorse unnumbered": BSD1[:DISCLAIMER]
    + "Neither the name of the copyright holder may be used to endorse or"
    " promote products.\n\n" + BSD1[DISCLAIMER:],
    "advertising unnumbered": BSD1[:DISCLAIMER]
    + "All advertising materials must display the following"
    " acknowledgement.\n\n" + BSD1[DISCLAIMER:],
    "Spencer-94": text("Spencer-94"),
    "other condition 1": BSD1.replace(
        "1. Redistributions of source code must retain",
        "1. Redistributions of the documentation must retain",
    ),
}


@pytest.mark.parametrize("value", NO_MARKER.values(), ids=NO_MARKER.keys())
def test_what_is_not_one_numbered_bsd_condition_gets_no_marker(
    db_path: str, value: str
) -> None:
    assert not marker_ids(db_path, value)

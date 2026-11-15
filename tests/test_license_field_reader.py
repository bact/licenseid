# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The loose ``License:`` field reader (``MarkerDetector``) reads each
distinct value once and only the first ``FIELD_VALUES_READ`` of them, so a
text of thousands of such lines costs a bounded number of lookups and
candidates (item 23). What it answers for an ordinary text is pinned."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import time
from collections.abc import Generator

import pytest
from matcher_db import Lic, seeded_db
from timing import slack

from licenseid.candidates import (
    FIELD_LICENSES_KEPT,
    FIELD_VALUES_READ,
    first_per_license,
)
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.markers import MarkerDetector
from licenseid.types import LicenseDetails

MANY = [f"Lic-{i}-1.0" for i in range(FIELD_LICENSES_KEPT + 8)]
ROWS = (
    Lic("MIT", "MIT License", search_text="mit license permission is granted"),
    Lic("Apache-2.0", "Apache License 2.0", search_text="apache license version 2"),
    Lic("ISC", "ISC License", search_text="isc license permission to use"),
    *(Lic(lic_id, f"Licence {lic_id}") for lic_id in MANY),
)


@pytest.fixture(name="db_path")
def _db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_license_field_reader", ROWS)


@pytest.fixture
def markers(db_path: str) -> MarkerDetector:
    return MarkerDetector(LicenseDatabase(db_path, create=False))


def fields(markers: MarkerDetector, text: str) -> list[tuple[str, float]]:
    """The loose reader's candidates, one per licence (as ``detect`` keeps
    them), as ``(ID, score)`` in order."""
    found = markers._detect_explicit_identifiers(text)  # pylint: disable=W0212
    return [(c["license_id"], c["score"]) for c in first_per_license(found)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("License: MIT\nLicense: Apache-2.0\n", ["MIT", "Apache-2.0"]),
        ("License: Apache-2.0\nLicense: MIT\n", ["Apache-2.0", "MIT"]),
        ("license: MIT\nLicense = MIT\nLICENSE: MIT\n", ["MIT"]),
        ("License: MIT\nLicense: nonsense\nLicense: ISC", ["MIT", "ISC"]),
        ("ISC License: Copyright (c) 2026 Someone", []),
        ("License: MIT\r\nLicense: ISC\r\n", ["MIT", "ISC"]),
        ("License:\tMIT\n", ["MIT"]),
        ("License: 麻省理工\nLicense：MIT\n", []),
        ("", []),
    ],
    ids=[
        "two-licences",
        "reverse-order",
        "same-value-thrice",
        "mixed-valid-invalid",
        "incidental-copyright",
        "crlf",
        "tab",
        "cjk",
        "empty",
    ],
)
def test_an_ordinary_text_answers_as_before(
    markers: MarkerDetector, text: str, expected: list[str]
) -> None:
    got = fields(markers, text)
    assert [lic for lic, _ in got] == expected
    assert all(score == 0.95 for _, score in got)


def test_the_order_of_the_fields_ranks_the_answers(db_path: str) -> None:
    detector = LicenseDetector(db_path)
    ranked = [
        r["expression"] for r in detector.detect(text="License: ISC\nLicense: MIT")
    ]
    assert ranked[:2] == ["ISC", "MIT"]


def test_a_manifest_is_not_read_by_the_loose_reader(markers: MarkerDetector) -> None:
    text = '{"license": "MIT"}'
    assert not any(
        c["score"] == 0.95 for c in markers.detect(text, file_path="package.json")
    )


def test_declared_reads_no_field(markers: MarkerDetector) -> None:
    assert not markers.detect_declared("License: MIT", [])


def lookups(markers: MarkerDetector, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The values the reader looks up by ID, in order."""
    calls: list[str] = []
    real = markers.db.get_license_details

    def spy(value: str) -> LicenseDetails | None:
        calls.append(value)
        return real(value)

    monkeypatch.setattr(markers.db, "get_license_details", spy)
    return calls


def distinct(n: int, tail: str = "") -> str:
    return "".join(f"License: x{i}\n" for i in range(n)) + tail


@pytest.mark.parametrize(
    ("distinct_before", "found"),
    [
        (FIELD_VALUES_READ - 1, ["MIT"]),
        (FIELD_VALUES_READ, []),
        (FIELD_VALUES_READ * 1000, []),
    ],
    ids=["last-read", "first-unread", "far-unread"],
)
def test_the_cap_counts_distinct_values(
    markers: MarkerDetector, distinct_before: int, found: list[str]
) -> None:
    text = distinct(distinct_before, "License: MIT\n")
    assert [lic for lic, _ in fields(markers, text)] == found


@pytest.mark.parametrize(
    ("n", "kept"),
    [
        (FIELD_LICENSES_KEPT - 1, FIELD_LICENSES_KEPT - 1),
        (FIELD_LICENSES_KEPT, FIELD_LICENSES_KEPT),
        (FIELD_LICENSES_KEPT + 8, FIELD_LICENSES_KEPT),
    ],
    ids=["below", "at", "above"],
)
def test_a_notice_file_keeps_a_bounded_number_of_licences(
    markers: MarkerDetector, n: int, kept: int
) -> None:
    """One ``License:`` line per package, each a different licence: all are
    kept up to the bound, which the first ones fill."""
    text = "".join(
        f"Package p{i}\nLicense: {lic}\n\n" for i, lic in enumerate(MANY[:n])
    )
    assert [lic for lic, _ in fields(markers, text)] == MANY[:kept]


def test_a_repeated_value_costs_one_read(
    markers: MarkerDetector, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = lookups(markers, monkeypatch)
    # 17 distinct values hide behind 2,000 repeats of the first.
    text = "License: MIT\n" * 2000 + distinct(FIELD_VALUES_READ) + "License: ISC"
    assert [lic for lic, _ in fields(markers, text)] == ["MIT"]
    # normalize_identifier looks each value up too: two lookups at most.
    assert len(calls) <= 2 * FIELD_VALUES_READ


def test_100k_distinct_values_read_a_bounded_number(
    markers: MarkerDetector, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = lookups(markers, monkeypatch)
    fields(markers, distinct(100_000))
    # normalize_identifier looks each value up too: two lookups at most.
    assert len(calls) <= 2 * FIELD_VALUES_READ


@pytest.mark.parametrize(
    "text",
    [
        "license:a" * 50_000,
        "license:" + " " * 1_000_000,
        "License: " + "x" * 1_000_000,
        "".join(f"License: x{i}\r\n" for i in range(10_000)),
        "".join(f"License: 麻{i}\n" for i in range(10_000)),
    ],
    ids=["one-line", "spaces", "huge-value", "crlf", "cjk"],
)
def test_a_large_text_reads_in_bounded_time(markers: MarkerDetector, text: str) -> None:
    start = time.monotonic()
    fields(markers, text)
    assert time.monotonic() - start < slack(1.0)


@pytest.mark.benchmark
def test_100k_distinct_lines_detect_in_bounded_time(db_path: str) -> None:
    text = distinct(100_000)
    start = time.monotonic()
    LicenseDetector(db_path).detect(text=text)
    assert time.monotonic() - start < slack(30)

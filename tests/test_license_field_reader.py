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

# The text of MIT and, without its one condition, of MIT-0.
MIT_TEXT = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software and associated documentation files (the "
    '"Software"), to deal in the Software without restriction, including '
    "without limitation the rights to use, copy, modify, merge, publish, "
    "distribute, sublicense, and/or sell copies of the Software, and to "
    "permit persons to whom the Software is furnished to do so, subject to "
    "the following conditions:\n\nThe above copyright notice and this "
    "permission notice shall be included in all copies or substantial "
    "portions of the Software.\n\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS '
    "OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF "
    "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. "
    "IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY "
    "CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, "
    "TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE "
    "SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"
)
MIT0_TEXT = MIT_TEXT.replace(
    ", subject to the following conditions:\n\nThe above copyright notice and "
    "this permission notice shall be included in all copies or substantial "
    "portions of the Software.",
    ".",
)
# Enough to pass any bound the tests name. The notice tests and the
# three-spellings test write 48 as 48, not as the constant, so that changing
# the bound fails them.
MANY = [f"Zed-{i}-1.0" for i in range(60)]
ROWS = (
    Lic("MIT", "MIT License", search_text=MIT_TEXT),
    Lic("MIT-0", "MIT No Attribution", search_text=MIT0_TEXT),
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
    # Under 30 words only the name tier reads it: two licences named, none.
    text = "License: ISC\nLicense: MIT\n" + "filler words for the length " * 6
    ranked = [r["expression"] for r in detector.detect(text=text)]
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


def test_repeats_and_unread_values_cost_no_lookup(
    markers: MarkerDetector, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = lookups(markers, monkeypatch)
    # MIT, repeated, and 255 other values fill the 256 read; ISC is the 257th.
    text = "License: MIT\n" * 2000 + distinct(FIELD_VALUES_READ - 1) + "License: ISC"
    assert [lic for lic, _ in fields(markers, text)] == ["MIT"]
    assert calls.count("MIT") <= 2  # normalize_identifier looks it up too
    assert "ISC" not in calls


@pytest.mark.parametrize(
    "text",
    [
        distinct(100_000),
        "".join(f"license:a{i} ;" for i in range(50_000)),
        "".join(f"License: x{i}\r\n" for i in range(10_000)),
    ],
    ids=["lines", "one-line", "crlf"],
)
def test_distinct_values_read_a_bounded_number(
    markers: MarkerDetector, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    calls = lookups(markers, monkeypatch)
    fields(markers, text)
    # normalize_identifier looks each value up too: two lookups at most.
    assert 0 < len(calls) <= 2 * FIELD_VALUES_READ


def test_one_licence_in_three_spellings_counts_once(markers: MarkerDetector) -> None:
    """The bound is on licences, not on values: MIT, mit and MIT License, and
    47 others, are 48 licences, all kept."""
    text = "".join(f"License: {v}\n" for v in ("MIT", "mit", "MIT License", *MANY[:47]))
    assert [lic for lic, _ in fields(markers, text)] == ["MIT", *MANY[:47]]


def notice(*licences: str) -> str:
    """A DEP-5-style notice: a block per licence, then the MIT text itself."""
    blocks = (
        f"Files: src/p{i}/*\nCopyright: 2020 Someone {i}\nLicense: {lic}\n\n"
        for i, lic in enumerate(licences)
    )
    return "".join(blocks) + f"License: MIT\n {MIT_TEXT}"


def answer(db_path: str, text: str) -> str:
    return LicenseDetector(db_path).detect(text=text)[0]["expression"]


def test_a_notice_at_the_bound_still_answers_its_text(
    db_path: str, markers: MarkerDetector
) -> None:
    """MIT-0 first, 46 others, then MIT: 48 field licences. MIT is kept, so
    it answers (the real database scores MIT 0.934 over MIT-0 0.931 by its
    text; here all field candidates tie and ID order, Zed-* last, decides).
    A bound of 32 dropped MIT and answered MIT-0."""
    text = notice("MIT-0", *MANY[:46])
    assert "MIT" in [lic for lic, _ in fields(markers, text)]
    assert answer(db_path, text) == "MIT"


def test_a_notice_past_the_bound_loses_its_last_licence(
    db_path: str, markers: MarkerDetector
) -> None:
    """A known limit, not a promise: with one more licence, MIT is the 49th
    field licence and is dropped, so the first one, MIT-0, answers."""
    text = notice("MIT-0", *MANY[:47])
    assert "MIT" not in [lic for lic, _ in fields(markers, text)]
    assert answer(db_path, text) == "MIT-0"


@pytest.mark.benchmark
def test_100k_distinct_lines_detect_in_bounded_time(db_path: str) -> None:
    text = distinct(100_000)
    start = time.monotonic()
    LicenseDetector(db_path).detect(text=text)
    assert time.monotonic() - start < slack(30)

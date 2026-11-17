# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The candidates ``hint`` adds (``licenseid.retrieval.hinted_candidates``):
the filters that drop one, the text it carries, the cap on that text, and
what it costs. How ``detect()`` orders them is in
``tests/test_detect_options_paths.py``.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from long_text_db import LONG_TEXTS, long_text_detector
from matcher_db import Lic, seeded_db
from timing import slack

from licenseid.database import LicenseDatabase
from licenseid.idoptions import upgraded_options
from licenseid.retrieval import MAX_HINTS_WITH_TEXT, add_free_text, hinted_candidates
from licenseid.types import DetectOptions

# Common (OSI, FSF), rare (neither), not on the List, and a bare deprecated
# row that has no text, as the List's own bare IDs have none.
COMMON = Lic("Common-1.0", "Common", True, True, True, search_text="common text")
RARE = Lic("Rare-1.0", "Rare", True, search_text="rare text")
OFF_LIST = Lic("Off-List-1.0", "Off the List", False, search_text="off list text")
BARE = Lic("Bare-1.0", "Bare", True, False, False, True, "Common-1.0")
CAPPED = [
    Lic(f"Cap-{i:02d}", "Cap", True, search_text=f"cap term{i}")
    for i in range(MAX_HINTS_WITH_TEXT + 1)
]
ROWS = (COMMON, RARE, OFF_LIST, BARE, *CAPPED)
ALL = ["Common-1.0", "Rare-1.0", "Off-List-1.0"]


@pytest.fixture(scope="module")
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_hint_candidates", ROWS):
        yield LicenseDatabase(path, create=False)


def ids(
    db: LicenseDatabase, present: list[str] | None = None, **options: Any
) -> list[str]:
    got = hinted_candidates(db, cast(DetectOptions, options), present or [])
    return [c["license_id"] for c in got]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        # only_spdx is on by default: the row off the List is dropped.
        ({}, ["Common-1.0", "Rare-1.0"]),
        ({"only_spdx": False}, ALL),
        ({"only_common": True}, ["Common-1.0"]),
        ({"only_common": True, "only_spdx": False}, ["Common-1.0"]),
        ({"exclude": ["Rare-1.0"]}, ["Common-1.0"]),
        ({"exclude": ["rare-1.0", "COMMON-1.0"]}, []),  # folded
        ({"exclude": ["Off-List-1.0"], "only_spdx": False}, ALL[:2]),
    ],
    ids=repr,
)
def test_a_hint_passes_the_same_filters_as_full_text_search(
    db: LicenseDatabase, options: dict[str, Any], expected: list[str]
) -> None:
    assert ids(db, hint=ALL, **options) == expected


def test_a_hint_for_an_id_with_no_row_adds_nothing(db: LicenseDatabase) -> None:
    assert ids(db, hint=["Nope-1.0"]) == []


def test_a_hint_keeps_the_shape_of_a_candidate(db: LicenseDatabase) -> None:
    """The row's own text and flags; a deprecated row keeps what Tier 2
    reads of it (``is_deprecated``, ``superseded_by``) and has no text."""
    got = hinted_candidates(db, DetectOptions(hint=["Common-1.0", "Bare-1.0"]), [])
    common, bare = got[0], got[1]
    assert common["search_text"] == "common text"
    assert common["is_osi_approved"] is True
    assert (bare["search_text"], bare["is_deprecated"]) == ("", True)
    assert bare["superseded_by"] == "Common-1.0"


def test_an_id_present_or_given_twice_is_added_once(db: LicenseDatabase) -> None:
    assert ids(db, hint=["rare-1.0", "Rare-1.0", "Common-1.0"]) == [
        "Rare-1.0",
        "Common-1.0",
    ]
    assert ids(db, present=["RARE-1.0"], hint=["Rare-1.0", "Common-1.0"]) == [
        "Common-1.0"
    ]


@pytest.mark.parametrize("written", ["rare-1.0", " Rare-1.0 ", "RARE-1.0"])
def test_a_hint_in_another_case_carries_its_text(
    db: LicenseDatabase, written: str
) -> None:
    """The text is the row's, whatever way the ID was written."""
    got = hinted_candidates(db, DetectOptions(hint=[written]), [])
    assert [(c["license_id"], c["search_text"]) for c in got] == [
        ("Rare-1.0", "rare text")
    ]


def test_a_set_of_hints_is_read_in_sorted_order() -> None:
    """Which hints carry their text must not depend on the hash seed."""
    hints = {f"Cap-{i:02d}" for i in range(60)}
    for kind in (set, frozenset):
        got = upgraded_options(DetectOptions(hint=kind(hints)))["hint"]
        assert got == sorted(hints)


def test_a_present_id_costs_no_lookup(db: LicenseDatabase) -> None:
    with mock.patch.object(
        db, "get_license_details", wraps=db.get_license_details
    ) as spy:
        assert ids(db, present=["Rare-1.0"], hint=["rare-1.0"]) == []
        spy.assert_not_called()
        assert ids(db, hint=["Rare-1.0"]) == ["Rare-1.0"]
        spy.assert_called_once()


def test_add_free_text_looks_up_no_hint_a_candidate_already_is(
    db: LicenseDatabase,
) -> None:
    """Markers, then hints; a hint that a candidate (a marker's too) already
    names costs no lookup and no second candidate."""
    marker = hinted_candidates(db, DetectOptions(hint=["Common-1.0"]), [])
    candidates = hinted_candidates(db, DetectOptions(hint=["Rare-1.0"]), [])
    options = DetectOptions(hint=["rare-1.0", "COMMON-1.0", "Bare-1.0"])
    with mock.patch.object(
        db, "get_license_details", wraps=db.get_license_details
    ) as spy:
        add_free_text(db, options, candidates, marker)
    assert [c["license_id"] for c in candidates] == [
        "Rare-1.0",
        "Common-1.0",
        "Bare-1.0",
    ]
    assert spy.call_count == 1  # only Bare-1.0


def test_only_the_first_hints_carry_their_text(db: LicenseDatabase) -> None:
    """The text stops at MAX_HINTS_WITH_TEXT hints: the next one is added
    with none, so it scores 0 (a Tier 2 pass costs the same for each)."""
    hints = [row.license_id for row in CAPPED]
    got = hinted_candidates(db, DetectOptions(hint=hints), [])
    assert [c["license_id"] for c in got] == hints
    with_text = [bool(c["search_text"]) for c in got]
    assert with_text == [True] * MAX_HINTS_WITH_TEXT + [False]


def test_the_cap_counts_the_hints_given_not_the_ones_added(
    db: LicenseDatabase,
) -> None:
    """Unknown IDs use up places: it bounds the work by the list's head."""
    hints = ["Nope-1.0"] * MAX_HINTS_WITH_TEXT + ["Rare-1.0"]
    got = hinted_candidates(db, DetectOptions(hint=hints), [])
    assert [(c["license_id"], c["search_text"]) for c in got] == [("Rare-1.0", "")]


# --- Cost: the text of a hint costs a Tier 2 pass ---

MIT_TEXT = json.loads((LONG_TEXTS / "MIT.json").read_text(encoding="utf-8"))[
    "license_text"
]


def _hint_run(hints: int) -> float:
    """Seconds to detect the MIT text with *hints* other licences hinted, on
    the database of every long-text fixture (555 rows, as large as the
    List's own texts), which the seeded rows above cannot show."""
    detector = long_text_detector()
    other = sorted(p.stem for p in Path(LONG_TEXTS).glob("*.json"))
    other = [i for i in other if i != "MIT"][:hints]
    start = time.monotonic()
    detector.detect(text=MIT_TEXT, hint=other)
    return time.monotonic() - start


def test_a_list_of_hints_stays_fast() -> None:
    """Measured 0.5 s on a quiet laptop (0.3 s with no hint)."""
    assert _hint_run(20) < slack(5.0)


@pytest.mark.benchmark
def test_two_hundred_hints_stay_fast() -> None:
    """Measured 0.7 s (0.3 s with no hint; 50 hints 0.7 s, as the text stops
    at 50). On the 740 rows of the List: 3.4-3.8 s, and 10 s were it not
    capped."""
    assert _hint_run(200) < slack(10.0)

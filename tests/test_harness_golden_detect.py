# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden snapshot of ``detect()``: the top result of each case on the
text fixtures (``tests/fixtures/golden/detect_*.tsv``). Every commit runs a
slice of each kind; ``--run-benchmark`` runs them all (about 8 minutes).
A value that moved must be listed in ``harness_changes.DETECT_CHANGES``
with its new value and the reason; a value that did not move must not be."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import harness_golden as hg
import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_changes import DETECT_CHANGES
from harness_db import harness_detector


def expected_for(kind: str) -> dict[str, tuple[str, str]]:
    return hg.select(DETECT_CHANGES, lambda case: case.startswith(f"{kind}/"))


@pytest.mark.parametrize("kind", hg.KINDS)
def test_the_slice_of_detect_is_the_golden(kind: str) -> None:
    golden = hg.read_golden(hg.GOLDEN / hg.FILES[kind])
    current = hg.snapshot(harness_detector(), kind, short=True)
    assert current, kind
    report = hg.diff_report(golden, current, expected_for(kind))
    assert not report, "\n" + report


@pytest.mark.benchmark
@pytest.mark.parametrize("kind", hg.KINDS)
def test_all_of_detect_is_the_golden(kind: str) -> None:
    golden = hg.read_golden(hg.GOLDEN / hg.FILES[kind])
    current = hg.snapshot(harness_detector(), kind)
    report = hg.diff_report(golden, current, expected_for(kind), complete=True)
    assert not report, "\n" + report


@pytest.mark.parametrize("kind", hg.KINDS)
def test_a_golden_file_is_in_order_and_short(kind: str) -> None:
    """Under the file-size limit, and exactly the cases the generator makes
    (so a fixture added or removed fails here, with no detect() run)."""
    path = hg.GOLDEN / hg.FILES[kind]
    assert len(path.read_text(encoding="utf-8").splitlines()) < 800
    golden = hg.read_golden(path)
    assert sorted(golden) == sorted(case for case, _ in hg.detect_cases(kind))
    assert list(golden) == sorted(golden)
    assert all(len(row.split("\t")) == 4 for row in golden.values())


@pytest.mark.parametrize("kind", hg.KINDS)
def test_the_slice_is_a_part_of_the_golden(kind: str) -> None:
    cases = hg.detect_cases(kind)
    part = [case for case, _ in hg.take_slice(kind, cases)]
    assert 0 < len(part) < len(cases) or kind in ("id", "name")
    assert set(part) <= set(hg.read_golden(hg.GOLDEN / hg.FILES[kind]))


GOLD = {"a": "x", "b": "y"}


@pytest.mark.parametrize(
    ("current", "expected", "complete", "mentions"),
    [
        (GOLD, {}, True, ""),
        ({"a": "x", "b": "z"}, {}, False, "b: 'y' -> 'z', not in"),
        ({"a": "x", "c": "z"}, {}, False, "c: None -> 'z', not in"),
        ({"a": "x", "b": "z"}, {"b": ("z", "why")}, True, ""),
        ({"a": "x", "b": "z"}, {"b": ("w", "why")}, False, "b: listed as 'w', got 'z'"),
        (GOLD, {"b": ("y", "why")}, False, "b: listed (why), unchanged"),
        ({"a": "x"}, {}, True, "b: in the golden, not run"),
        ({"a": "x"}, {}, False, ""),
        ({"a": "x"}, {"b": ("z", "why")}, True, "b: listed, not run"),
    ],
    ids=[
        "same",
        "moved",
        "new",
        "listed",
        "listed-wrong-value",
        "listed-unchanged",
        "missing-complete",
        "missing-slice",
        "listed-not-run",
    ],
)
def test_the_diff_accepts_only_listed_changes(
    current: dict[str, str],
    expected: dict[str, tuple[str, str]],
    complete: bool,
    mentions: str,
) -> None:
    """Mutation check of the diff itself: each way a golden can drift."""
    report = hg.diff_report(GOLD, current, expected, complete=complete)
    assert (mentions in report) if mentions else (report == "")

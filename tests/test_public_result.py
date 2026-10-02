# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What match() returns and the CLI prints: the same keys for every method,
a 0-1 score, an exact flag, and JSON Lines in RFC 8785 form. Roadmap item
22: --json printed each tier's own record, ranking keys and licence text
included."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator
from typing import Any, get_type_hints

import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT, RESULT_KEYS, json_lines
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.result import json_line, public_result, text_line
from licenseid.types import LicenseMatch, RawMatch

# Long enough that a fragment of it is aligned to a window of its own.
LONG_TEXT = " ".join(
    f"{a}{b}" for a in ("alpha", "beta", "gamma", "delta") for b in "abcdefghijklmno"
)
FRAGMENT = " ".join(LONG_TEXT.split()[10:22]) + " zulu"


def test_the_keys_are_those_of_the_public_type() -> None:
    assert set(get_type_hints(LicenseMatch)) == RESULT_KEYS


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        Lic("MIT", "MIT License", True, True, True, search_text=MIT_SEARCH_TEXT),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True),
        # Shares every word of "MIT License": a look-alike, not exact.
        Lic("MIT-Variant", "MIT License Variant"),
        *GPL2_ROWS[:2],
        Lic("Long-1.0", "Long License", search_text=LONG_TEXT),
    ]
    yield from seeded_db("test_public_result", rows)


@pytest.mark.parametrize(
    ("kwargs", "method", "measured"),
    [
        ({"text": "// SPDX-License-Identifier: MIT"}, "tag", (False, False)),
        ({"text": '{"license": "MIT"}'}, "field", (False, False)),
        ({"license_id": "MIT"}, "id", (False, False)),
        ({"text": "MIT"}, "id", (False, False)),
        ({"text": "MIT License"}, "name", (True, False)),
        ({"text": MIT_SEARCH_TEXT}, "text", (True, True)),
    ],
    ids=["tag", "field", "id", "lone-id", "name", "text"],
)
def test_every_method_gives_the_same_keys(
    db: str, kwargs: dict[str, Any], method: str, measured: tuple[bool, bool]
) -> None:
    top = AggregatedLicenseMatcher(db).match(**kwargs)[0]
    assert set(top) == RESULT_KEYS
    assert (top["license_id"], top["method"], top["exact"]) == ("MIT", method, True)
    # None where nothing was measured: a tag, a field and an ID compare no
    # text, and a name covers none.
    assert (top["similarity"] is not None, top["coverage"] is not None) == measured
    assert 0.0 <= top["score"] <= 1.0
    assert (top["is_spdx"], top["is_osi_approved"], top["is_fsf_libre"]) == (
        True,
        True,
        True,
    )


def test_a_loosely_written_field_is_still_found_by_field(db: str) -> None:
    """The value "Apache 2.0" is no ID, so the name match reads it."""
    top = AggregatedLicenseMatcher(db).match(text='{"license": "Apache 2.0"}')[0]
    assert (top["license_id"], top["method"], top["exact"]) == (
        "Apache-2.0",
        "field",
        True,
    )
    # Its ID, spelt loosely: nothing measured.
    assert (top["similarity"], top["coverage"]) == (None, None)


def test_only_the_exact_hit_of_a_field_is_found_by_field(db: str) -> None:
    """The field names MIT; MIT-Variant only shares its name's words. (A
    value spelt exactly as a name resolves before the name match.)"""
    results = AggregatedLicenseMatcher(db).match(text='{"license": "MIT-License"}')
    assert [(r["license_id"], r["method"], r["exact"]) for r in results] == [
        ("MIT", "field", True),
        ("MIT-Variant", "name", False),
    ]


def test_an_or_later_phrase_is_found_by_id(db: str) -> None:
    """The deprecated-ID fast path: an ID, nothing measured."""
    top = AggregatedLicenseMatcher(db).match(text="GPL-2.0 or later")[0]
    assert (top["license_id"], top["method"], top["exact"]) == (
        "GPL-2.0-or-later",
        "id",
        True,
    )
    assert (top["score"], top["similarity"], top["coverage"]) == (1.0, None, None)


def _raw(score: float, similarity: float | None = 0.98765) -> RawMatch:
    return RawMatch(
        license_id="MIT",
        method="text",
        exact=False,
        score=score,
        similarity=similarity,
        coverage=1.23456,  # input words over licence words: can pass 1
        is_spdx=True,
    )


@pytest.mark.parametrize(
    ("raw", "score"),
    [(1.05, 1.0), (1.02, 1.0), (1.0, 1.0), (0.98765, 0.9877), (-0.01, 0.0)],
)
def test_the_score_is_capped_to_0_1_and_rounded(raw: float, score: float) -> None:
    result = public_result(_raw(raw))
    assert result["score"] == score
    assert (result["similarity"], result["coverage"]) == (0.9877, 1.2346)
    # Flags a tier did not set are False, not missing.
    assert (result["is_osi_approved"], result["is_fsf_libre"]) == (False, False)


def test_the_cap_keeps_the_ranking_order_and_exact_tells_them_apart(
    db: str,
) -> None:
    """An exact name (1.02) ranks above a look-alike (1.01): both print 1,
    in that order, and only the first is exact."""
    matcher = AggregatedLicenseMatcher(db)
    raw = matcher._match_raw("MIT License")  # pylint: disable=protected-access
    assert [(r["license_id"], r["score"]) for r in raw] == [
        ("MIT", 1.02),
        ("MIT-Variant", 1.01),
    ]
    results = matcher.match("MIT License")
    assert [(r["license_id"], r["score"], r["exact"]) for r in results] == [
        ("MIT", 1.0, True),
        ("MIT-Variant", 1.0, False),
    ]


def test_a_text_match_is_exact_only_word_for_word(db: str) -> None:
    matcher = AggregatedLicenseMatcher(db)
    assert matcher.match(text=LONG_TEXT)[0]["exact"]
    near = matcher.match(text=LONG_TEXT + " zulu")[0]
    assert (near["license_id"], near["exact"]) == ("Long-1.0", False)


def _public(
    license_id: str = "GPL-2.0-only WITH Classpath-exception-2.0",
    score: float = 1.0,
    similarity: float | None = None,
    coverage: float | None = None,
) -> LicenseMatch:
    return LicenseMatch(
        license_id=license_id,
        method="tag",
        exact=True,
        score=score,
        similarity=similarity,
        coverage=coverage,
        is_spdx=True,
        is_osi_approved=True,
        is_fsf_libre=False,
    )


def test_a_json_line_is_canonical() -> None:
    """Sorted keys, no white space, 1.0 printed as 1, null and false."""
    assert json_line(_public()) == (
        '{"coverage":null,"exact":true,"is_fsf_libre":false,'
        '"is_osi_approved":true,"is_spdx":true,'
        '"license_id":"GPL-2.0-only WITH Classpath-exception-2.0",'
        '"method":"tag","score":1,"similarity":null}'
    )
    assert '"score":0.9877' in json_line(_public(score=0.9877))


def test_a_text_line_has_every_field_and_empty_for_none() -> None:
    assert text_line(_public(license_id="MIT")) == (
        "LICENSE_ID=MIT METHOD=tag EXACT=true SCORE=1.0000 SIMILARITY= COVERAGE="
    )
    assert text_line(_public(license_id="MIT", similarity=0.5, coverage=1.25)) == (
        "LICENSE_ID=MIT METHOD=tag EXACT=true SCORE=1.0000 SIMILARITY=0.5000"
        " COVERAGE=1.2500"
    )


def test_json_prints_one_line_per_result(db: str) -> None:
    """Two tags, two results, two lines; each line one JSON value."""
    text = "// SPDX-License-Identifier: MIT\n// SPDX-License-Identifier: Apache-2.0"
    result = CliRunner().invoke(cli, ["--db", db, "match", "--json", "--text", text])
    assert result.exit_code == 0
    assert result.stdout.count("\n") == 2
    lines = json_lines(result.stdout)
    assert [(r["license_id"], r["method"]) for r in lines] == [
        ("MIT", "tag"),
        ("Apache-2.0", "tag"),
    ]
    assert all(set(r) == RESULT_KEYS for r in lines)
    # The bytes match() results print as.
    expected = AggregatedLicenseMatcher(db).match(text=text)
    assert result.stdout == "".join(json_line(r) + "\n" for r in expected)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], ["MIT", "MIT-Variant"]),
        (["--exact"], ["MIT"]),
        (["--exact", "--top", "1"], ["MIT"]),
    ],
)
def test_exact_keeps_only_exact_matches(
    db: str, args: list[str], expected: list[str]
) -> None:
    result = CliRunner().invoke(
        cli, ["--db", db, "match", "--json", *args, "--text", "MIT License"]
    )
    assert result.exit_code == 0
    assert [r["license_id"] for r in json_lines(result.stdout)] == expected


def test_exact_with_no_exact_match_finds_none(db: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", db, "match", "--exact", "--text", LONG_TEXT + " zulu"]
    )
    assert (result.exit_code, result.stdout) == (1, "")
    assert result.stderr.endswith("ERROR: match: no license found\n")


@pytest.mark.parametrize("threshold", ["1.01", "-0.1", "nan", "inf"])
def test_a_threshold_outside_0_1_is_a_usage_error(db: str, threshold: str) -> None:
    """A score is 0-1: a threshold above 1 kept nothing, and said only
    "no license found"."""
    result = CliRunner().invoke(
        cli, ["--db", db, "match", "--threshold", threshold, "--text", "MIT"]
    )
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith("ERROR: option: invalid: --threshold: ")
    assert result.stderr.endswith("; pass a value from 0 to 1\n")


@pytest.mark.parametrize("threshold", ["0", "1"])
def test_a_threshold_of_0_or_1_is_accepted(db: str, threshold: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", db, "match", "--threshold", threshold, "--text", "MIT"]
    )
    assert result.exit_code == 0
    assert result.stdout.startswith("LICENSE_ID=MIT ")


@pytest.mark.parametrize(
    "text",
    # The tag names no license, so Tier 2 matched the text without it.
    [FRAGMENT, "SPDX-License-Identifier: LicenseRef-x+\n" + FRAGMENT],
    ids=["fragment", "tagged"],
)
def test_the_diff_window_is_the_one_ranking_aligned(db: str, text: str) -> None:
    """--diff recomputes the window Tier 2 aligned, for one license."""
    matcher = AggregatedLicenseMatcher(db)
    raw = matcher._match_raw(text)  # pylint: disable=protected-access
    assert (raw[0]["license_id"], raw[0]["method"]) == ("Long-1.0", "text")
    window = raw[0].get("best_window")
    # A window of its own, not the whole text.
    assert isinstance(window, str)
    assert window and len(window.split()) < len(LONG_TEXT.split())
    assert matcher.diff_window(text, "Long-1.0") == window
    assert matcher.diff_window(text, "NoSuch-1.0") == ""


def test_a_with_expression_with_no_row_aligns_with_its_license(db: str) -> None:
    """A "WITH Font-exception-2.0" the License List lacks was ranked on its
    license's text (markers), and --diff showed nothing."""
    matcher = AggregatedLicenseMatcher(db)
    window = matcher.diff_window(FRAGMENT, "Long-1.0")
    assert window
    assert matcher.diff_window(FRAGMENT, "Long-1.0 WITH Font-exception-2.0") == window

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
from conftest import (
    MIT_SEARCH_TEXT,
    RESULT_KEYS,
    invoke_match,
    json_lines,
    public_match,
)
from matcher_db import GPL2_ROWS, Lic, seeded_db

import licenseid
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
        # Shares MIT's name, but deprecated: MIT is the exact answer.
        Lic("MIT-Old", "MIT License", is_deprecated=True),
        # Deprecated, with a name of its own, and a look-alike in use (as
        # AGPL-3.0 beside AGPL-3.0-only): the deprecated row is exact.
        Lic("Old-1.0", "Old Unique License", is_deprecated=True),
        Lic("Old-1.0-only", "Old Unique License only"),
        *GPL2_ROWS[:2],
        Lic("Long-1.0", "Long License", search_text=LONG_TEXT),
    ]
    yield from seeded_db("test_public_result", rows)


def _match(db: str, **kwargs: Any) -> list[LicenseMatch]:
    return AggregatedLicenseMatcher(db).match(**kwargs)


@pytest.mark.parametrize(
    ("kwargs", "license_id", "method", "measured"),
    [
        ({"text": "// SPDX-License-Identifier: MIT"}, "MIT", "tag", (0, 0)),
        ({"text": '{"license": "MIT"}'}, "MIT", "field", (0, 0)),
        # No ID, so the name match reads it; its ID, spelt loosely.
        ({"text": '{"license": "Apache 2.0"}'}, "Apache-2.0", "field", (0, 0)),
        ({"license_id": "MIT"}, "MIT", "id", (0, 0)),
        ({"text": "MIT"}, "MIT", "id", (0, 0)),
        # The deprecated-ID fast path.
        ({"text": "GPL-2.0 or later"}, "GPL-2.0-or-later", "id", (0, 0)),
        ({"text": "GPL-2.0 only"}, "GPL-2.0-only", "id", (0, 0)),
        ({"text": "MIT License"}, "MIT", "name", (1, 0)),
        ({"text": MIT_SEARCH_TEXT}, "MIT", "text", (1, 1)),
    ],
    ids=[
        "tag",
        "field",
        "loose-field",
        "id",
        "lone-id",
        "or-later",
        "only",
        "name",
        "text",
    ],
)
def test_every_method_gives_the_same_keys(
    db: str,
    kwargs: dict[str, Any],
    license_id: str,
    method: str,
    measured: tuple[int, int],
) -> None:
    top = _match(db, **kwargs)[0]
    assert set(top) == RESULT_KEYS
    assert (top["license_id"], top["method"], top["exact"], top["score"]) == (
        license_id,
        method,
        True,
        1.0,
    )
    # None where nothing was measured: a tag, a field and an ID compare no
    # text, and a name covers none.
    assert (top["similarity"] is not None, top["coverage"] is not None) == (
        bool(measured[0]),
        bool(measured[1]),
    )
    assert top["is_spdx"]


@pytest.mark.parametrize(
    ("text", "first"),
    [
        # A value spelt exactly as a name resolves before the name match.
        ('{"license": "MIT-License"}', ("MIT", "field", True, None)),
        ("MIT License", ("MIT", "name", True, 1.0)),
    ],
    ids=["field", "name"],
)
def test_only_the_exact_hit_is_exact_and_found_by_field(
    db: str, text: str, first: tuple[str, str, bool, float | None]
) -> None:
    """MIT-Variant only shares MIT's words, and MIT-Old is deprecated: both
    were found by name, and neither is exact. All three score 1 or near it;
    the order and ``exact`` tell them apart."""
    results = _match(db, text=text)
    assert [
        (r["license_id"], r["method"], r["exact"], r["similarity"]) for r in results
    ] == [first, ("MIT-Variant", "name", False, 1.0), ("MIT-Old", "name", False, 1.0)]
    assert [r["score"] for r in results][:2] == [1.0, 1.0]


def test_a_deprecated_name_of_its_own_is_exact(db: str) -> None:
    """Only a deprecated row that shares its name with a row in use gives
    way: --exact found nothing for "GNU Affero General Public License v3.0"."""
    results = _match(db, text="Old Unique License")
    assert [(r["license_id"], r["exact"]) for r in results] == [
        ("Old-1.0-only", False),
        ("Old-1.0", True),
    ]


def test_the_cap_keeps_the_ranking_order(db: str) -> None:
    matcher = AggregatedLicenseMatcher(db)
    raw = matcher._match_raw("MIT License")  # pylint: disable=protected-access
    assert [r["score"] for r in raw][:2] == [1.02, 1.01]
    assert [r["license_id"] for r in raw] == [
        r["license_id"] for r in matcher.match("MIT License")
    ]


def test_a_text_match_is_exact_only_for_the_whole_text(db: str) -> None:
    assert _match(db, text=LONG_TEXT)[0]["exact"]
    near = _match(db, text=LONG_TEXT + " zulu")[0]
    assert (near["license_id"], near["exact"]) == ("Long-1.0", False)


@pytest.mark.parametrize("text", ["...", "SPDX-License-Identifier: Foo"])
def test_an_input_with_no_words_is_no_exact_text(db: str, text: str) -> None:
    """A hinted candidate has no text, and an input that normalises to
    nothing (a short one whose only tag names no license, once the tag is
    dropped) equalled it: an exact match of nothing."""
    results = _match(db, text=text, hint=["Apache-2.0"])
    assert [(r["license_id"], r["exact"]) for r in results] == [("Apache-2.0", False)]


def _raw(
    score: float, similarity: float | None = 0.98765, coverage: float = 1.23456
) -> RawMatch:
    # No flags: a tier that sets none gets False, not a missing key.
    return RawMatch(
        license_id="MIT",
        method="text",
        exact=False,
        score=score,
        similarity=similarity,
        coverage=coverage,  # input words over licence words: can pass 1
    )


@pytest.mark.parametrize(
    ("raw", "score"),
    [(1.08, 1.0), (1.02, 1.0), (1.0, 1.0), (0.98765, 0.9877), (-0.01, 0.0)],
)
def test_the_score_is_capped_to_0_1_and_rounded(raw: float, score: float) -> None:
    assert public_result(_raw(raw))["score"] == score


def test_the_other_values_are_rounded_and_the_flags_filled() -> None:
    """Similarity and coverage are rounded, not capped; a flag a tier did
    not set is False; and -0.0 is 0.0, which text printed as "-0.0000"."""
    result = public_result(_raw(0.5))
    assert (result["similarity"], result["coverage"]) == (0.9877, 1.2346)
    assert (result["is_spdx"], result["is_osi_approved"], result["is_fsf_libre"]) == (
        False,
        False,
        False,
    )
    tiny = public_result(_raw(0.5, similarity=-1e-6))
    assert " SIMILARITY=0.0000 " in text_line(tiny)


def test_a_json_line_is_canonical() -> None:
    """Sorted keys, no white space, 1.0 printed as 1, null and false."""
    assert json_line(public_match("GPL-2.0-only WITH Classpath-exception-2.0")) == (
        '{"coverage":null,"exact":true,"is_fsf_libre":false,'
        '"is_osi_approved":true,"is_spdx":true,'
        '"license_id":"GPL-2.0-only WITH Classpath-exception-2.0",'
        '"method":"tag","score":1,"similarity":null}'
    )


@pytest.mark.parametrize(
    ("raw", "fields"),
    [
        (_raw(0.9876543), '"coverage":1.2346,'),
        (_raw(0.00004, similarity=0.0), '"score":0,"similarity":0}'),
        (_raw(0.5, coverage=13.0), '"coverage":13,'),
    ],
    ids=["rounded", "zero", "integral"],
)
def test_json_numbers_are_ecmascript_numbers(raw: RawMatch, fields: str) -> None:
    """Never an exponent or a trailing ".0", whatever the value."""
    assert fields in json_line(public_result(raw))


@pytest.mark.parametrize(
    ("similarity", "coverage", "tail"),
    [
        (None, None, "SIMILARITY= COVERAGE="),
        (0.5, 1.25, "SIMILARITY=0.5000 COVERAGE=1.2500"),
        (1.0, 13.0, "SIMILARITY=1.0000 COVERAGE=13.0000"),
    ],
)
def test_a_text_line_has_every_field_and_empty_for_none(
    similarity: float | None, coverage: float | None, tail: str
) -> None:
    line = text_line(public_match(similarity=similarity, coverage=coverage))
    assert line == f"LICENSE_ID=MIT METHOD=tag EXACT=true SCORE=1.0000 {tail}"


def test_json_prints_one_line_per_result(db: str) -> None:
    """Two tags, two results, two lines, in the bytes match() results print
    as."""
    text = "// SPDX-License-Identifier: MIT\n// SPDX-License-Identifier: Apache-2.0"
    result = invoke_match(db, "--json", "--text", text)
    assert result.exit_code == 0
    lines = json_lines(result.stdout)
    assert [(r["license_id"], r["method"]) for r in lines] == [
        ("MIT", "tag"),
        ("Apache-2.0", "tag"),
    ]
    assert result.stdout == "".join(json_line(r) + "\n" for r in _match(db, text=text))


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--text", "MIT License"], ["MIT", "MIT-Variant", "MIT-Old"]),
        (["--exact", "--text", "MIT License"], ["MIT"]),
        # --exact filters before --top cuts.
        (["--exact", "--top", "1", "--text", "MIT License"], ["MIT"]),
        (["--exact", "--text", LONG_TEXT + " zulu"], []),
        (["--threshold", "0", "--text", "MIT"], ["MIT"]),
        (["--threshold", "1", "--text", "MIT"], ["MIT"]),
    ],
)
def test_exact_and_threshold_filter_the_results(
    db: str, args: list[str], expected: list[str]
) -> None:
    result = invoke_match(db, "--json", *args)
    assert result.exit_code == (0 if expected else 1)
    assert [r["license_id"] for r in json_lines(result.stdout)] == expected


@pytest.mark.parametrize("threshold", ["1.01", "-0.1", "nan", "inf"])
def test_a_threshold_outside_0_1_is_a_usage_error(db: str, threshold: str) -> None:
    """A score is 0-1: a threshold above 1 kept nothing, and said only
    "no license found"."""
    result = invoke_match(db, "--threshold", threshold, "--text", "MIT")
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith("ERROR: option: invalid: --threshold: ")
    assert result.stderr.endswith("; pass a value from 0 to 1\n")


# The tag names no license, so Tier 2 matched the text without it.
TAGGED = "SPDX-License-Identifier: LicenseRef-x+\n" + FRAGMENT


@pytest.mark.parametrize("text", [FRAGMENT, TAGGED], ids=["fragment", "tagged"])
def test_the_diff_pair_is_what_ranking_aligned(db: str, text: str) -> None:
    """--diff recomputes the window Tier 2 aligned, for one license, against
    the input Tier 2 read. (Characterisation: reads the internal window.)"""
    matcher = AggregatedLicenseMatcher(db)
    raw = matcher._match_raw(text)  # pylint: disable=protected-access
    assert (raw[0]["license_id"], raw[0]["method"]) == ("Long-1.0", "text")
    window = raw[0].get("best_window")
    # A window of its own, not the whole text.
    assert isinstance(window, str)
    assert window and len(window.split()) < len(LONG_TEXT.split())
    assert matcher.diff_pair(text, "Long-1.0") == (FRAGMENT, window)
    assert matcher.diff_pair(text, "NoSuch-1.0") == ("", "")
    # A "WITH Font-exception-2.0" the License List lacks was ranked on its
    # license's text (markers), and --diff showed nothing.
    pair = matcher.diff_pair(text, "Long-1.0 WITH Font-exception-2.0")
    assert pair == (FRAGMENT, window)


@pytest.mark.parametrize("text", [FRAGMENT, TAGGED], ids=["fragment", "tagged"])
def test_diff_shows_one_diff_of_the_text_matched(db: str, text: str) -> None:
    """One diff, for the top result only, and without the tag Tier 2 did
    not match (it printed a diff of the tag's words alone)."""
    result = invoke_match(
        db, "--diff", "--threshold", "0", "--top", "2", "--text", text
    )
    assert result.exit_code == 0
    assert result.stdout.count("WORD DIFF:") == 1
    assert "+zulu" in result.stdout
    assert "spdx" not in result.stdout.lower()


def test_diff_is_for_the_top_result_only() -> None:
    rows = [
        Lic("Long-1.0", "Long License", search_text=LONG_TEXT),
        Lic("Long-2.0", "Long License Two", search_text=LONG_TEXT + " omega"),
    ]
    for db in seeded_db("test_public_result_diff", rows):
        out = invoke_match(
            db, "--diff", "--threshold", "0", "--top", "2", "--text", FRAGMENT
        ).stdout
        assert (out.count("LICENSE_ID="), out.count("WORD DIFF:")) == (2, 1)


def test_the_result_types_are_exported() -> None:
    assert {"LicenseMatch", "Method"} <= set(licenseid.__all__)

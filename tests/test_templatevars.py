# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.templatevars``: where a template's variable parts sit in the
stored text (real List templates and made-up ones), the regions a same-text
group shares, and a ``match`` pattern read on normalised words."""
# pylint: disable=missing-function-docstring

import json
import time

import pytest
from template_texts import PATTERNS, long_text, template
from timing import slack

from licenseid import templatevars
from licenseid.normalize import normalize_text
from licenseid.templatevars import (
    CLOSE,
    OPEN,
    fill_matches,
    fill_pattern,
    marked_text,
    row_regions,
    shared_regions,
    var_regions,
)
from licenseid.textcorpus import VarRegion, split_words

LIST_PATTERNS: list[str] = json.loads(PATTERNS.read_text(encoding="utf-8"))
BEGIN, END = "<<beginOptional>>", "<<endOptional>>"


def var(original: str, match: str = ".+", name: str = "n") -> str:
    return f'<<var;name="{name}";original="{original}";match="{match}">>'


def _words(text: str) -> list[str]:
    return split_words(normalize_text(text))


def _spans(license_id: str) -> list[tuple[int, int, str]]:
    """The regions of a List text that hold words, and those words."""
    words = _words(long_text(license_id))
    source = template(license_id)
    assert source is not None
    return [
        (r.start, r.end, " ".join(words[r.start : r.end]))
        for r in var_regions(source, words, True)
        if r.end > r.start
    ]


def test_a_var_is_marked_where_it_stands() -> None:
    assert marked_text(f"a {var('X')} b", True) == f"a  {OPEN} X {CLOSE}  b"


def test_a_var_that_starts_a_line_stays_at_the_start_of_one() -> None:
    """A list number stays where normalisation drops it."""
    marked = marked_text(f"a\n  {var('1.', '.{0,20}')} text", True)
    assert marked == f"a\n  {OPEN}\n1. {CLOSE}  text"
    assert _words(marked or "") == ["a", OPEN, CLOSE, "text"]


def test_the_core_drops_the_vars_of_optional_parts() -> None:
    source = f"a {BEGIN}b {var('X')}{END} c {var('Y')}"
    assert _words(marked_text(source, False) or "") == ["a", "c", OPEN, "y", CLOSE]
    assert _words(marked_text(source, True) or "").count(OPEN) == 2


def test_a_malformed_template_has_no_regions() -> None:
    assert marked_text(f"a {BEGIN}b", True) is None
    assert not var_regions(f"a {BEGIN}b {var('X')}", ["a", "b", "x"], True)


def test_the_regions_of_bsd_3_clause() -> None:
    assert _spans("BSD-3-Clause") == [
        (0, 4, "copyright c year owner"),
        (16, 17, "are"),
        (27, 29, "source code"),
        (32, 33, "above"),
        (50, 51, "above"),
        (
            72,
            86,
            (
                "neither the name of the copyright holder nor the names of its"
                " contributors may"
            ),
        ),
        (96, 97, "software"),
        (103, 104, "software"),
        (106, 112, "by the copyright holders and contributors"),
        (116, 117, "express"),
        (142, 147, "the copyright holder or contributors"),
        (208, 209, "software"),
    ]


def test_the_regions_of_mit_hpnd_and_apache() -> None:
    assert _spans("MIT")[0] == (2, 7, "copyright c year copyright holders")
    assert _spans("MIT")[-3] == (128, 133, "the authors or copyright holders")
    source = template("HPND")
    assert source is not None
    assert len(var_regions(source, _words(long_text("HPND")), True)) == 13
    assert _spans("Apache-2.0") == [(1504, 1509, "yyyy name of copyright holder")]


def test_a_var_whose_words_do_not_match_one_run_is_no_region() -> None:
    source = f"one two {var('alpha beta')} three {var('gamma')} four"
    stored = ["one", "two", "alpha", "new", "beta", "three", "gamma", "four"]
    assert var_regions(source, stored, True) == (VarRegion(6, 7, ".+"),)
    assert var_regions(source, ["one", "two", "three", "gamma", "four"], True) == (
        VarRegion(3, 4, ".+"),
    )
    middle = f"one {var('alpha beta gamma')} two"
    assert not var_regions(middle, ["one", "alpha", "delta", "gamma", "two"], True)


@pytest.mark.parametrize(
    ("source", "stored", "expected"),
    [
        (f"one {var('')} two", ["one", "two"], (VarRegion(1, 1, ".+"),)),
        (f"{var('')} one two", ["one", "two"], (VarRegion(0, 0, ".+"),)),
        (f"one two {var('')}", ["one", "two"], (VarRegion(2, 2, ".+"),)),
        (f"one {var('')} two", ["one", "extra", "two"], ()),
        (f"one {var('')} two", ["zero", "two"], ()),
        (f"zero {var('')} one two", ["one", "two"], ()),
    ],
    ids=[
        "between",
        "first",
        "last",
        "not-adjacent",
        "neighbour-unmatched",
        "left-unmatched-at-start",
    ],
)
def test_an_empty_var_is_a_point_between_matched_neighbours(
    source: str, stored: list[str], expected: tuple[VarRegion, ...]
) -> None:
    assert var_regions(source, stored, True) == expected


def test_a_group_shares_only_the_regions_of_every_template() -> None:
    """GPL-2.0-only and GPL-2.0-or-later: the "or later" var of one template
    is fixed text in the other, so it is no region of their text."""
    only = f"version {var('2', '2')} of the licence only {var('A')}"
    grant = var("only", "only|or later")
    later = f"version {var('2', '2')} of the licence {grant} {var('A')}"
    text = normalize_text("version 2 of the licence only A")
    texts, cores = row_regions(text, None, [only, later])
    assert texts == (VarRegion(1, 2, "2"), VarRegion(6, 7, ".+"))
    assert cores == ()
    alone, _ = row_regions(text, None, [later])
    assert VarRegion(5, 6, "only|or later") in alone


def test_a_region_with_another_pattern_is_not_shared() -> None:
    first = (VarRegion(0, 1, "a|b"), VarRegion(2, 3, ".+"))
    second = (VarRegion(0, 1, "a"), VarRegion(2, 3, ".+"))
    assert shared_regions([first, second]) == (VarRegion(2, 3, ".+"),)
    assert shared_regions([]) == ()
    assert row_regions("a b", "a", []) == ((), ())


def test_the_core_has_regions_of_its_own() -> None:
    source = f"{BEGIN}title {var('X')}{END} body {var('holder')} end"
    texts, cores = row_regions("title x body holder end", "body holder end", [source])
    assert texts == (VarRegion(1, 2, ".+"), VarRegion(3, 4, ".+"))
    assert cores == (VarRegion(1, 2, ".+"),)


@pytest.mark.parametrize(
    ("pattern", "fill", "expected"),
    [
        (".{0,20}", "a", True),
        (".{0,20}", "x" * 21, False),
        ("are|is", "is", True),
        ("are|is", "were", False),
        (r"EXPRESS(ED)?", "expressed", True),
        (r"The\s+name\s+of.+may\s+not", "the name of the author may not", True),
        (r"The\s+name\s+of.+may\s+not", "thename ofx maynot", True),
        ("this software, and", "this software and", True),
        ("(c) 2001", "c 2001", True),
        (r"\(c\) 2001", "c 2001", True),
        (r"CC-[ \t\r\n\f]{0,10}licensed", "cc licensed", True),
        (r"Ce[\[\(]a[\]\)]", "ce a", True),
        ("[^x]+", "abc", True),
        ("[^,]+", "abc", True),  # negated: any character but a mark
        (r"\d+", "2001", True),
        (r"\d+", "two", False),
        ("-{1,2}", "", True),
        ("(To obtain permission, contact .*)?", "", True),
        (
            "(To obtain permission, contact .*)?",
            "to obtain permission contact a b",
            True,
        ),
        (
            "(To obtain permission, contact .*)?",
            "redistributions of any form whatsoever must retain",
            False,
        ),
        ("(", "(", False),  # not a pattern Python compiles: never exempt
    ],
)
def test_a_fill_is_read_on_normalised_words(
    pattern: str, fill: str, expected: bool
) -> None:
    assert fill_matches(pattern, fill) is expected


def test_a_pattern_python_cannot_compile_is_none() -> None:
    assert fill_pattern("(") is None
    assert fill_pattern(".+") is not None


def test_a_fill_of_3000_characters_is_read_and_one_more_is_not() -> None:
    assert fill_matches(".+", "x" * 3000)
    assert not fill_matches(".+", "x" * 3001)


def test_every_pattern_of_the_list_compiles() -> None:
    assert len(LIST_PATTERNS) == 142
    assert [p for p in LIST_PATTERNS if fill_pattern(p) is None] == []


@pytest.mark.parametrize(
    "fill",
    [
        "x" + " " * 2999,
        " " * 3000,
        "a " * 1500,
        ("neither " * 375)[:3000],
        ("the name of " * 273)[:3000],
        "x" * 3000,
    ],
    ids=["x-spaces", "spaces", "a-space", "neither", "the-name-of", "one-word"],
)
def test_no_pattern_of_the_list_backtracks(fill: str) -> None:
    """Each space as one optional space: read literally (``\\s*``), one
    pattern took 0.15 s on 3,000 characters; this way the worst takes about
    0.07 ms and all 142 about 3 ms (compiled first: compiling is no part of
    a search's cost after the first call)."""
    for pattern in LIST_PATTERNS:
        fill_pattern(pattern)
    start = time.monotonic()
    for pattern in LIST_PATTERNS:
        fill_matches(pattern, fill)
    assert time.monotonic() - start < slack(0.1)


@pytest.mark.parametrize(
    "tokens",
    [
        [OPEN, "a", OPEN, "b", CLOSE],
        [OPEN, "a", CLOSE, OPEN, "b", CLOSE],
        [CLOSE, "a"],
        [OPEN, "a"],
        ["a"],
    ],
    ids=["open-twice", "more-vars", "close-first", "never-closed", "no-var"],
)
def test_sentinels_that_do_not_pair_with_the_vars_give_none(
    tokens: list[str],
) -> None:
    """Normalisation keeps the sentinels, so this never happens on a List
    template; the reading still refuses rather than guess."""
    # pylint: disable-next=protected-access
    assert templatevars._unmarked(tokens, [".+"]) is None


def test_sentinels_that_pair_give_the_var_and_the_words() -> None:
    # pylint: disable-next=protected-access
    found = templatevars._unmarked(["x", OPEN, "a", "b", CLOSE, "y"], [".+"])
    assert found is not None
    assert found.words == ["x", "a", "b", "y"]
    assert found.spans == [(1, 3, ".+")]


@pytest.mark.parametrize(("count", "codes"), [(55040, True), (55041, False)])
def test_words_past_the_codes_below_the_surrogates_give_none(
    count: int, codes: bool
) -> None:
    """Each word is one code point from U+0100 up to U+D7FF: 55,040 words;
    no List template comes near."""
    words = [f"w{i}" for i in range(count)]
    # pylint: disable-next=protected-access
    assert (templatevars._matches(words, []) is not None) is codes

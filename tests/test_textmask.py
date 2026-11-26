# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.textmask``: the fit of a text with its variable parts left
out, on made-up texts: a fill its pattern accepts costs nothing, one it
refuses costs what it costs today, the key never passes the text's length,
and Han and kana fills are cut by token."""
# pylint: disable=missing-function-docstring,protected-access

import dataclasses
import time

import pytest
from test_wholetexts import fake
from timing import slack

from licenseid import textmask, wholetexts
from licenseid.templatevars import fill_matches
from licenseid.textcorpus import RunChars, TextCorpus, TextRow, VarRegion, split_words
from licenseid.textlocate import Budget, Fit, align, span_fit

BODY = " ".join(f"clause{i} says the licensee may copy item{i}" for i in range(8))
HOLDER = "copyright c year owner"
TEXT = f"{HOLDER} {BODY} by the copyright holders and contributors"
# The text's tokens: the copyright line, then BODY, then the disclaimer.
LINE = VarRegion(0, 4, ".{0,5000}")
TAIL = len(TEXT.split()) - 6
DISCLAIMER = VarRegion(TAIL, TAIL + 6, ".*")


def _fit(
    text: str, regions: tuple[VarRegion, ...], given: str, unbounded: bool = False
) -> Fit | None:
    """The masked fit of *text* (its *regions*) in the span of *given* that
    the alignment finds."""
    corpus = TextCorpus.build([TextRow("A", text, None, ("A",), regions)])
    coded = corpus.entries[0].text
    words = split_words(given)
    found = align(coded.codes, corpus.encode(words))
    assert found is not None
    chars = RunChars(given)
    first, last = chars.bounds(found.start, found.end)
    exempt = textmask.exempt_runs(
        coded, found.blocks, RunChars(text), given[first:last], unbounded
    )
    return textmask.masked_fit(coded, exempt, Budget())


def _plain(text: str, given: str) -> Fit | None:
    corpus = TextCorpus.build([TextRow("A", text, None, ("A",))])
    return span_fit(corpus.entries[0].text, given, Budget())


def test_without_regions_it_is_the_plain_fit() -> None:
    given = TEXT.replace("owner", "example project developers")
    assert _fit(TEXT, (), given) == _plain(TEXT, given)


def test_an_accepted_fill_costs_nothing() -> None:
    given = TEXT.replace("year owner", "2026 example project developers")
    fit = _fit(TEXT, (LINE,), given)
    assert fit is not None and fit.distance == 0
    plain = _plain(TEXT, given)
    assert plain is not None and plain.distance > 0


ITEM = VarRegion(38, 39, ".+")  # "item4", in the middle of the text


@pytest.mark.parametrize(
    ("fill", "key"),
    [
        ("item4", len(TEXT)),
        ("example developers " * 7, len(TEXT)),
        ("x", len(TEXT) - 4),
    ],
    ids=["own", "long", "short"],
)
def test_a_fill_is_found_up_to_the_length_of_its_words(fill: str, key: int) -> None:
    """An exact copy keys the text's length whatever the fill's length; a
    fill shorter than the List's words ("item4", 5 characters) misses what
    it lacks (4)."""
    given = TEXT.replace(" item4 ", f" {fill.strip()} ")
    fit = _fit(TEXT, (ITEM,), given)
    assert fit is not None and fit.distance == 0 and fit.masked
    assert fit.key == key
    assert fit.own is (fill == "item4")


def test_a_change_outside_the_fill_costs_the_key() -> None:
    """The key is that of the plain fit of the copy with its fill put
    back: found less missing."""
    given = TEXT.replace(" item4 ", " itemz ").replace("clause1 ", "")
    fit = _fit(TEXT, (ITEM,), given)
    plain = _plain(TEXT, TEXT.replace("clause1 ", ""))
    assert fit is not None and plain is not None
    assert (fit.key, fit.distance) == (plain.key, plain.distance)
    assert fit.key < len(TEXT)


def test_a_refused_fill_is_compared_as_today() -> None:
    region = VarRegion(TAIL, TAIL + 6, "by the copyright holders and contributors")
    given = TEXT.replace("copyright holders and", "regents and")
    assert _fit(TEXT, (region,), given) == _plain(TEXT, given)


def test_two_regions_each_left_out() -> None:
    given = TEXT.replace("year owner", "2026 example").replace(
        "copyright holders and contributors", "regents"
    )
    fit = _fit(TEXT, (LINE, DISCLAIMER), given)
    assert fit is not None and fit.distance == 0
    only_line = _fit(TEXT, (LINE,), given)
    assert only_line is not None and only_line.distance > 0


@pytest.mark.parametrize(("size", "exempt"), [(159, True), (160, False)])
def test_a_fill_150_characters_longer_than_its_words_is_left_out_not_151(
    size: int, exempt: bool
) -> None:
    """ "copyright" (9 characters) as a word of 159: left out; of 160: the
    var compared, as today (a clause written into an open var)."""
    region = VarRegion(TAIL + 2, TAIL + 3, ".+")  # "copyright"
    given = TEXT.replace("the copyright holders", "the " + "x" * size + " holders")
    fit = _fit(TEXT, (region,), given)
    assert (fit is not None and fit.distance == 0) is exempt


@pytest.mark.parametrize(
    "given",
    [
        TEXT.replace("the copyright holders", "the " + "x" * 400 + " holders"),
        TEXT.replace("year owner clause0", "2026 example clausezero"),
    ],
    ids=["past-the-slack", "next-word-replaced"],
)
def test_unbounded_a_var_takes_any_fill_its_pattern_accepts(given: str) -> None:
    """For a look-alike (``wholetexts._Search._doubts``) neither FILL_SLACK
    nor the matched neighbours hold a fill back."""
    regions = (LINE, VarRegion(TAIL + 2, TAIL + 3, ".+"))
    bounded = _fit(TEXT, regions, given)
    fit = _fit(TEXT, regions, given, unbounded=True)
    assert fit is not None and fit.masked
    assert bounded is None or fit.distance < bounded.distance


@pytest.mark.parametrize(
    ("given", "exempt"),
    [
        (TEXT.replace("year owner", "2026 example"), True),
        (TEXT.replace("year owner clause0", "2026 example clausezero"), False),
    ],
    ids=["neighbours-match", "next-word-replaced"],
)
def test_a_var_is_left_out_only_between_matched_words(given: str, exempt: bool) -> None:
    """A word replaced beside a var stays compared on both sides: else the
    new word, read as part of the fill, would cost nothing."""
    fit = _fit(TEXT, (LINE,), given)
    assert fit is not None
    assert fit.masked is exempt


CONTACT = "(To obtain permission, contact .*)?"


@pytest.mark.parametrize(
    ("inserted", "exempt"),
    [
        ("to obtain permission contact licensing example org", True),
        ("redistributions of any form must retain this", False),
    ],
)
def test_a_point_takes_only_what_its_pattern_accepts(
    inserted: str, exempt: bool
) -> None:
    point = VarRegion(20, 20, CONTACT)
    words = TEXT.split()
    given = " ".join([*words[:20], inserted, *words[20:]])
    fit = _fit(TEXT, (point,), given)
    assert fit is not None
    assert (fit.distance == 0) is exempt


def test_an_empty_point_leaves_nothing_out() -> None:
    fit = _fit(TEXT, (VarRegion(20, 20, CONTACT),), TEXT)
    assert fit == _plain(TEXT, TEXT)


KANA = "本ソフトウェアは無保証で提供されますが利用者は自由に複製できます"
HAN_TEXT = f"{KANA}著作権者{KANA}"


def test_a_han_fill_is_cut_by_token() -> None:
    """One token per character and no space between them: the fill is the
    characters of its tokens, not of words."""
    start = len(split_words(KANA))
    region = VarRegion(start, start + 4, ".+")
    given = HAN_TEXT.replace("著作権者", "例示株式会社")
    fit = _fit(HAN_TEXT, (region,), given)
    assert fit is not None and fit.distance == 0
    assert _plain(HAN_TEXT, given) is None  # under 0.93 character by character


BLOCKS = ((0, 0, 3), (5, 6, 2))  # text 0-3 at span 0, text 5-7 at span 6


@pytest.mark.parametrize(
    ("token", "before", "after", "matched"),
    [
        (0, 0, 0, True),
        (2, 2, 2, True),
        (3, 3, 6, False),
        (4, 3, 6, False),
        (5, 3, 6, True),
        (6, 7, 7, True),
        (7, 8, 9, False),
    ],
)
def test_a_fill_runs_between_the_matched_neighbours(
    token: int, before: int, after: int, matched: bool
) -> None:
    fills = textmask._Fills(BLOCKS, 8, 9)
    assert fills.before(token) == before
    assert fills.after(token) == after
    assert fills.matched(token) is matched


@pytest.mark.parametrize(
    ("start", "end", "touches"),
    [(0, 1, True), (3, 5, True), (4, 5, False), (3, 4, False), (6, 8, True)],
)
def test_a_var_touches_matched_words_or_an_end(
    start: int, end: int, touches: bool
) -> None:
    assert textmask._Fills(BLOCKS, 8, 9).touches(start, end) is touches


def test_runs_that_touch_are_one() -> None:
    assert textmask._merged([(5, 6), (0, 2), (2, 3), (5, 5)]) == [(0, 3), (5, 6)]


def test_an_empty_han_point_leaves_nothing_out() -> None:
    """No space is put between two Han tokens where an empty part with an
    empty fill sits: the fit is the plain one, total length included."""
    point = VarRegion(len(split_words(KANA)), len(split_words(KANA)), ".*")
    assert _fit(HAN_TEXT, (point,), HAN_TEXT) == _plain(HAN_TEXT, HAN_TEXT)


def _changed(count: int) -> str:
    """TEXT with its copyright line filled and *count* words from the 31st
    misspelt."""
    words = TEXT.split()
    spelt = [f"{w}zzzzzz" if 30 <= at < 30 + count else w for at, w in enumerate(words)]
    return " ".join(spelt).replace("year owner", "2026 example")


def test_a_masked_fit_under_093_is_none() -> None:
    """Under the look-alike floor there is no fit, masked or not."""
    near = _fit(TEXT, (LINE,), _changed(9))
    assert near is not None and near.reaches(0.93) and not near.reaches(0.95)
    assert _fit(TEXT, (LINE,), _changed(10)) is None


#: "item4" then "clause5": no matched word between them.
TWO = (VarRegion(38, 39, ".+"), VarRegion(39, 40, "clause5|section5"))


@pytest.mark.parametrize(
    ("fill", "masked"),
    [("item four section5", True), ("item four chapter5", False)],
    ids=["both-accepted", "second-refused"],
)
def test_vars_side_by_side_take_one_fill(fill: str, masked: bool) -> None:
    """Their one fill must fit both patterns in turn: alone, neither var
    has matched words on both sides."""
    fit = _fit(TEXT, TWO, TEXT.replace("item4 clause5", fill))
    assert fit is not None
    assert fit.masked is masked


@pytest.mark.parametrize(
    ("patterns", "joined"),
    [
        ([".+"], ".{1,}"),
        ([".+", ".+", ".+", "DISCLAIMS?"], "(.{3,}) (DISCLAIMS?)"),
        ([".{0,20}", ".{0,20}"], ".{0,41}"),
        ([".*", ".{0,20}", ".*?"], ".{0,}"),
        (["are|is", ".{0,5000}"], "(are|is) (.{0,5000})"),
        ([".{54,64}", "x"], "(.{54,64}) (x)"),
        (["a.b", ".+"], "(a.b) (.{1,})"),
    ],
)
def test_vars_of_any_characters_side_by_side_are_one(
    patterns: list[str], joined: str
) -> None:
    assert textmask.chain_pattern(patterns) == joined


def test_a_failing_fill_of_three_open_vars_is_quick() -> None:
    """Read as three, ``(.+) (.+) (.+) (DISCLAIMS?)`` took 0.19 s to refuse
    a fill of 252 characters."""
    pattern = textmask.chain_pattern([".+", ".+", ".+", "DISCLAIMS?"])
    fill_matches(pattern, "x")
    start = time.monotonic()
    for fill in ("x" + " " * 251, "a " * 126, "x" * 252):
        assert not fill_matches(pattern, fill)
    assert time.monotonic() - start < slack(0.01)


def _masked(key: int, distance: int, own: bool = False) -> Fit:
    return Fit(key, distance, 1000, masked=True, own=own)


@pytest.mark.parametrize(
    ("fit", "hit", "outkeys"),
    [
        (Fit(901, 9, 1000), Fit(900, 0, 1000), True),
        (Fit(900, 0, 1000), Fit(900, 0, 1000), False),
        (_masked(980, 0), _masked(1000, 0), True),
        (_masked(979, 0), _masked(1000, 0), False),
        (_masked(1000, 1), _masked(1000, 0), False),
        (_masked(1000, 0), Fit(1000, 0, 1000), False),
        (_masked(1000, 0), _masked(1000, 0, own=True), False),
        (_masked(1000, 0, own=True), _masked(1000, 0, own=True), True),
        (_masked(1000, 0, own=True), _masked(1000, 0), True),
    ],
    ids=[
        "higher-key",
        "plain-equal",
        "masked-tie-at-098",
        "masked-under-098",
        "masked-less-close",
        "hit-plain",
        "only-the-hit-own",
        "both-own",
        "only-the-look-alike-own",
    ],
)
def test_a_look_alike_outkeys_or_ties_a_hit(fit: Fit, hit: Fit, outkeys: bool) -> None:
    """Two masked fits tie within TIE_REACH (0.98) of the hit's key, as
    close or closer, unless only the hit's fills are its own words."""
    assert wholetexts._outkeys(fit, hit) is outkeys


HEAD, TAIL_WORDS = fake(5, 80), fake(6, 80)
#: Two texts that differ only in a var: P's holds three words, Q's one.
TIED = {
    "P": (f"{HEAD} alpha beta gamma {TAIL_WORDS}", VarRegion(80, 83, ".+")),
    "Q": (f"{HEAD} x {TAIL_WORDS}", VarRegion(80, 81, ".+")),
}


def _tied_rows(fill: str, answer: str) -> list[str] | None:
    corpus = TextCorpus.build(
        TextRow(key, text, None, (key,), (region,))
        for key, (text, region) in TIED.items()
    )
    return wholetexts.found_rows(f"{HEAD} {fill} {TAIL_WORDS}", corpus, answer)


@pytest.mark.parametrize(
    ("fill", "answer", "rows"),
    [
        ("example holder words here", "P", None),
        ("example holder words here", "Q", None),
        ("alpha beta gamma", "P", ["P"]),
        ("x", "Q", ["Q"]),
    ],
    ids=["third-words", "third-words-q", "p-own", "q-own"],
)
def test_texts_that_differ_only_in_a_var_tie(
    fill: str, answer: str, rows: list[str] | None
) -> None:
    """With a fill of neither, P keys its length and Q, shorter, keys 15
    less (0.98 of P's or more): neither is named, though Q's text is shorter
    than P's key. A fill of one's own words names it."""
    assert len(TIED["Q"][0]) < len(TIED["P"][0]) <= len(TIED["Q"][0]) / 0.98
    assert _tied_rows(fill, answer) == rows


def test_vars_side_by_side_fall_back_to_each_alone() -> None:
    """Their one fill fails (clause5 is no "section5": an original its own
    pattern refuses), but item4 alone has matched words on both sides."""
    two = (VarRegion(38, 39, ".+"), VarRegion(39, 40, "section5"))
    fit = _fit(TEXT, two, TEXT.replace("item4 clause5", "item four clause5"))
    assert fit is not None and fit.masked and fit.distance == 0


NEST_HEAD, NEST_MID, NEST_TAIL = fake(7, 40), fake(8, 80), fake(9, 80)
#: L holds S whole after a head of its own; each lets the word before S's
#: tail vary, L its holder too.
NESTED = (
    TextRow(
        "L",
        f"{NEST_HEAD} holder {NEST_MID} owner {NEST_TAIL}",
        None,
        ("L",),
        (VarRegion(40, 41, ".+"), VarRegion(122, 123, ".+")),
    ),
    TextRow(
        "S", f"{NEST_MID} owner {NEST_TAIL}", None, ("S",), (VarRegion(80, 81, ".+"),)
    ),
)
NEST_CLAUSE = " ".join(f"term{i} forbids selling" for i in range(8))
NEST_FILL = (
    "the example organisation of one two three and its many contributing "
    "developers here and there and everywhere else in this wide world"
)


@pytest.mark.parametrize("regions", [True, False], ids=["masked", "plain"])
def test_a_longer_text_whose_fill_no_bound_accepts_doubts_a_masked_hit(
    regions: bool,
) -> None:
    """A clause of 175 characters in L's holder: L fits only unbounded, S
    only masked (its fill of 132 characters is under FILL_SLACK). S inside L
    is no answer, as without the regions (the X11 copy holding MIT's
    words)."""
    rows = NESTED if regions else [dataclasses.replace(r, regions=()) for r in NESTED]
    given = f"{NEST_HEAD} holder {NEST_CLAUSE} {NEST_MID} {NEST_FILL} {NEST_TAIL}"
    assert len(NEST_CLAUSE) == 175 and len(NEST_FILL) == 132
    assert wholetexts.found_rows(given, TextCorpus.build(rows), "S") is None


def test_a_longer_text_under_095_doubts_no_masked_hit() -> None:
    """With 19 words of L's head replaced, L keys above S unbounded (1,126
    against 1,113) but fits at 0.947: S stands."""
    head = " ".join(["qwxzqwxz"] * 19 + NEST_HEAD.split()[19:])
    given = f"{head} holder {NEST_CLAUSE} {NEST_MID} {NEST_FILL} {NEST_TAIL}"
    assert wholetexts.found_rows(given, TextCorpus.build(NESTED), "S") == ["S"]

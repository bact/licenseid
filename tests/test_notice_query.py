# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A plain MIT text whose first 20 normalised words are a title and a long
copyright line still gets MIT as a Tier 1 candidate.

``ftsquery.match_query`` takes the first 20 words, so a title and a holder of
a dozen words left it no word of the licence's own. ``retrieval`` now runs a
second head query on the text without its copyright notices
(``normalize.strip_copyright_notices``) and adds what it finds.

The database is the long-text fixtures' (every licence of the List, so MIT,
MIT-advertising, Xnet, FSL-1.1-MIT and JSON are near neighbours with their
texts): a database of five rows returns all five whatever the query says, and
a test on it passes without the fix."""
# pylint: disable=missing-function-docstring,protected-access

import json
import time
from collections.abc import Callable

import pytest
from long_text_db import LONG_TEXTS, long_text_detector
from timing import slack

from licenseid import normalize, retrieval
from licenseid.database import LicenseDatabase
from licenseid.ftsquery import MAX_TERMS
from licenseid.normalize import (
    normalize_text,
    notice_free_head,
    strip_copyright_notices,
)
from licenseid.retrieval import get_candidates
from licenseid.types import CandidateMatch, DetectOptions

# Made up, and long: the notice alone fills the first 20 words.
HOLDER = "Marlowe-Quartermaine Brightwater Holdings International Incorporated"
TITLE = "The MIT License (MIT)\n\n"
ONE_LINE = (
    f"Copyright (c) 2025 {HOLDER} and the Northern Lights Collective,"
    " Contributors and Friends\n\n"
)
TWO_LINES = (
    f"Copyright (c) 2006-2024 {HOLDER}\nCopyright (c) 2025 {HOLDER} Foundation\n\n"
)
NEIGHBOURS = ("MIT", "MIT-advertising", "Xnet", "FSL-1.1-MIT", "JSON")


def _mit_body() -> str:
    """The grant and the disclaimer of the MIT fixture, with no title and no
    copyright line (its first two paragraphs)."""
    text = json.loads((LONG_TEXTS / "MIT.json").read_text(encoding="utf-8"))
    return str(text["license_text"]).split("\n\n", 2)[2]


MIT_TITLED = TITLE + ONE_LINE + _mit_body()
MIT_TWO_LINES = TWO_LINES + _mit_body()


def _ids(text: str) -> list[str]:
    db = long_text_detector().db
    options = DetectOptions()
    return [c["license_id"] for c in get_candidates(db, options, text)]


def test_the_fixture_rows_exist() -> None:
    for license_id in NEIGHBOURS:
        assert (LONG_TEXTS / f"{license_id}.json").exists(), license_id


@pytest.mark.parametrize("text", [MIT_TITLED, MIT_TWO_LINES], ids=["title", "two"])
def test_the_notice_does_not_fill_the_query(text: str) -> None:
    # The premise: the notice leaves no word of the licence in the first 20.
    head = normalize_text(text).split()[:MAX_TERMS]
    assert "permission" not in head
    assert "MIT" in _ids(text)


@pytest.mark.parametrize("text", [MIT_TITLED, MIT_TWO_LINES], ids=["title", "two"])
def test_detect_answers_mit(text: str) -> None:
    top = long_text_detector().detect(text=text)
    assert top[0]["expression"] == "MIT"


def test_a_plain_mit_text_answers_as_before() -> None:
    top = long_text_detector().detect(text=_mit_body())
    assert top[0]["expression"] == "MIT"


class _Counter:
    """Counts ``LicenseDatabase.search_candidates`` calls, keeping its work."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.queries: list[str] = []
        original: Callable[..., list[CandidateMatch]] = (
            LicenseDatabase.search_candidates
        )

        def counted(
            db: LicenseDatabase, text: str, *args: object, **kwargs: object
        ) -> list[CandidateMatch]:
            self.queries.append(text)
            return original(db, text, *args, **kwargs)

        monkeypatch.setattr(LicenseDatabase, "search_candidates", counted)


def test_one_extra_query_when_the_notice_fills_the_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _Counter(monkeypatch)
    _ids(MIT_TITLED)
    assert len(counter.queries) == 2
    # The second query is the text without its notice.
    assert counter.queries[1].startswith("the mit license mit permission")


@pytest.mark.parametrize(
    "text",
    [
        _mit_body(),  # no notice at all
        "The MIT License (MIT)\n\n" + _mit_body(),  # a title, no notice
        # A notice past the first 20 words: the head is the same.
        _mit_body() + "\n\n" + ONE_LINE,
    ],
    ids=["plain", "title-only", "notice-last"],
)
def test_no_second_query_when_stripping_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    counter = _Counter(monkeypatch)
    _ids(text)
    assert len(counter.queries) == 1


def test_the_notice_free_query_adds_what_the_first_lacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = long_text_detector().db
    first = [CandidateMatch(license_id=f"First-{i}", search_text="") for i in range(3)]
    found = [CandidateMatch(license_id=f"Found-{i}", search_text="") for i in range(50)]
    limits: list[object] = []

    def search(*_args: object, **kwargs: object) -> list[CandidateMatch]:
        limits.append(kwargs["limit"])
        return found[:10] + first[:1] + found[10:]

    monkeypatch.setattr(LicenseDatabase, "search_candidates", search)
    added = retrieval._notice_free_candidates(
        db, MIT_TITLED, normalize_text(MIT_TITLED), list(first)
    )
    # All of the 50 results, none of them twice, the first query's order kept.
    assert limits == [50]
    assert [c["license_id"] for c in added[:3]] == ["First-0", "First-1", "First-2"]
    assert len(added) == len(first) + len(found)


def _gated(monkeypatch: pytest.MonkeyPatch, new_at: int | None) -> list[str]:
    """What ``_notice_free_candidates`` adds to three first-query candidates
    when the notice-free query returns 50 results, all known to the first
    query but the one at 0-based *new_at*, then new ones from the 21st on."""
    db = long_text_detector().db
    first = [CandidateMatch(license_id=f"First-{i}", search_text="") for i in range(20)]
    found = [CandidateMatch(license_id=f"Late-{i}", search_text="") for i in range(30)]
    ranked = list(first) + found
    if new_at is not None:
        ranked[new_at] = CandidateMatch(license_id="New", search_text="")
    monkeypatch.setattr(
        LicenseDatabase, "search_candidates", lambda *_a, **_k: list(ranked)
    )
    added = retrieval._notice_free_candidates(
        db, MIT_TITLED, normalize_text(MIT_TITLED), list(first)
    )
    return [c["license_id"] for c in added[len(first) :]]


def test_no_result_added_when_its_top_10_adds_no_licence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert not _gated(monkeypatch, None)


@pytest.mark.parametrize("new_at", [0, 9])
def test_a_new_licence_in_its_top_10_adds_every_result(
    monkeypatch: pytest.MonkeyPatch, new_at: int
) -> None:
    added = _gated(monkeypatch, new_at)
    assert added[0] == "New"
    assert len(added) == 31


def test_a_new_licence_11th_adds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not _gated(monkeypatch, 10)


def test_a_template_copyright_line_adds_no_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # HPND's List text: "Copyright <year> <copyright holder>" changes the
    # first 20 words, so the second query runs, but its top 10 hold nothing
    # new, and Tier 2 gets the first query's candidates only (2.05x main).
    data = json.loads((LONG_TEXTS / "HPND.json").read_text(encoding="utf-8"))
    text = str(data["license_text"])
    counter = _Counter(monkeypatch)
    ids = _ids(text)
    assert len(counter.queries) == 2
    db = long_text_detector().db
    first = retrieval._search_candidates_by_length(db, normalize_text(text))
    assert ids == [c["license_id"] for c in first]


# The right licence ranks 26 to 50 in the notice-free query when two copyright
# lines head the text: a cap of 25 on what that query adds dropped it, and a
# neighbour answered instead. Each of these is such a licence in the
# fixtures' database.
BELOW_25 = ["0BSD", "ISC", "MIT-testregex", "NTP"]


def _fixture_body(name: str) -> str:
    """The text of a fixture without its title line."""
    data = json.loads((LONG_TEXTS / f"{name}.json").read_text(encoding="utf-8"))
    lines = str(data["license_text"]).strip().splitlines()
    return "\n".join(lines[1:])


@pytest.mark.parametrize("name", BELOW_25)
def test_two_copyright_lines_do_not_cost_the_licence_its_candidacy(name: str) -> None:
    text = TWO_LINES + _fixture_body(name)
    assert name in _ids(text)


@pytest.mark.parametrize("name", BELOW_25)
def test_the_notice_free_query_ranks_the_licence_beyond_25(name: str) -> None:
    # The premise of the cap test above: new candidates beyond the 25th.
    db = long_text_detector().db
    text = TWO_LINES + _fixture_body(name)
    query = " ".join(notice_free_head(text, MAX_TERMS))
    ranked = [
        c["license_id"]
        for c in db.search_candidates(query, limit=50, already_normalized=True)
    ]
    assert 25 < ranked.index(name) + 1 <= 50


@pytest.mark.parametrize("name", BELOW_25)
def test_detect_answers_the_licence_under_two_copyright_lines(name: str) -> None:
    top = long_text_detector().detect(text=TWO_LINES + _fixture_body(name))
    assert top[0]["expression"] == name


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Copyright (c) 2025 Ann\n\nPermission", "\n\nPermission"),
        ("(c) 2025 Ann Lee\nPermission", "\nPermission"),
        ("© 2025 Ann\nPermission", "\nPermission"),
        # Body text with the word "copyright" but no notice cue stays.
        ("the copyright holder grants", "the copyright holder grants"),
        ("", ""),
    ],
)
def test_strip_copyright_notices(text: str, expected: str) -> None:
    assert strip_copyright_notices(text) == expected


def test_the_index_still_keeps_notices() -> None:
    # normalize_text itself still keeps them: this change is Tier 1 only.
    assert "2025" in normalize_text("Copyright (c) 2025 Ann\nPermission")


# The head of the text without its notices is read from a prefix of the text
# (``normalize.notice_free_head``): same words as the whole text, at a time
# that does not grow with its length.


def _whole_head(text: str, words: int = MAX_TERMS) -> list[str]:
    return normalize_text(strip_copyright_notices(text)).split()[:words]


def _notice_in_filler() -> str:
    """Five filler words, then a notice of 25 words after its cue (the most a
    match takes: the year and 24 more), then the licence: a cut inside the
    notice leaves the match short of tokens."""
    holder = " ".join(f"holder{i}" for i in range(24))
    return "filler " * 5 + f"Copyright 2020 {holder} " + _mit_body()


@pytest.mark.parametrize("head_chars", [30, 45, 60, 100, 140, 200, 300, 4096], ids=str)
def test_the_head_is_read_from_a_prefix_as_from_the_whole(
    monkeypatch: pytest.MonkeyPatch, head_chars: int
) -> None:
    monkeypatch.setattr(normalize, "_HEAD_CHARS", head_chars)
    text = _notice_in_filler()
    assert notice_free_head(text, MAX_TERMS) == _whole_head(text)
    assert notice_free_head(text, MAX_TERMS)[:6] == ["filler"] * 5 + ["permission"]


@pytest.mark.parametrize("head_chars", [40, 90, 150, 600], ids=str)
@pytest.mark.parametrize("name", ["MIT", "ISC", "Apache-2.0", "0BSD"])
def test_a_prefix_reads_a_fixture_as_the_whole_does(
    monkeypatch: pytest.MonkeyPatch, head_chars: int, name: str
) -> None:
    monkeypatch.setattr(normalize, "_HEAD_CHARS", head_chars)
    body = json.loads((LONG_TEXTS / f"{name}.json").read_text(encoding="utf-8"))
    for text in (TWO_LINES + body["license_text"], body["license_text"]):
        assert notice_free_head(text, MAX_TERMS) == _whole_head(text)


def test_a_prefix_of_one_long_line_is_settled_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One line, no break: a notice cue 40 tokens in takes the next 25, and the
    # cut falls inside them for each size here.
    monkeypatch.setattr(normalize, "_HEAD_CHARS", 100)
    holder = " ".join(f"h{i}" for i in range(25))
    text = " ".join(f"w{i}" for i in range(40)) + f" (c) {holder} " + "x " * 100
    assert notice_free_head(text, MAX_TERMS) == _whole_head(text)
    assert notice_free_head(text, 45) == _whole_head(text, 45)


def test_a_text_of_notices_only_is_read_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every word is a notice: the prefixes never hold 21 words.
    monkeypatch.setattr(normalize, "_HEAD_CHARS", 50)
    text = "(c) 2020 Ann Lee\n" * 30 + "Permission"
    assert notice_free_head(text, MAX_TERMS) == ["permission"]


def test_a_text_with_html_is_read_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    # The closing tag is past the first 40 characters, and what it turns on
    # (plain text from HTML: "<b>" is no word) reaches the head.
    monkeypatch.setattr(normalize, "_HEAD_CHARS", 40)
    text = "Copyright 2020 Ann\n<b>Permission is hereby\n" + "word " * 30 + "</b>"
    head = notice_free_head(text, 3)
    assert head == _whole_head(text, 3) == ["permission", "is", "hereby"]


def test_the_last_word_of_the_settled_part_may_change_with_what_follows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The 24 last tokens of the cut start at "cent": "per" ends the settled
    # part, and "per cent" is one word, "percent", in the whole text.
    before = "a " * 25 + "per "
    after = "cent " + "z " * 22 + "z"
    monkeypatch.setattr(normalize, "_HEAD_CHARS", len(before + after))
    text = before + after + " tail words"
    assert notice_free_head(text, 26) == _whole_head(text, 26)
    assert notice_free_head(text, 26)[-1] == "percent"


def test_a_cut_anywhere_reads_the_whole_texts_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A year 11 tokens after "copyright" makes it a notice; a cut before the
    # year, inside a token, or just after the notice must not change the head.
    text = (
        "x(c)y x copyright "
        + "t " * 10
        + "2020 "
        + "u " * 14
        + "\nPermission is hereby granted, free of charge\nCopyright 2021 Ann "
        + "w " * 30
    )
    for end in range(1, len(text)):
        monkeypatch.setattr(normalize, "_HEAD_CHARS", end)
        for words in (2, 5, 12):
            assert notice_free_head(text, words) == _whole_head(text, words), end


def test_a_text_of_short_lines_is_settled_by_its_first_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The settled part of a prefix ending in a short line reaches that line.
    reads: list[int] = []
    original = normalize._settled_head

    def counted(text: str, end: int) -> str:
        reads.append(end)
        return original(text, end)

    monkeypatch.setattr(normalize, "_settled_head", counted)
    apache = json.loads((LONG_TEXTS / "Apache-2.0.json").read_text())["license_text"]
    text = TWO_LINES + (apache * 3).replace(" ", "\n")
    assert len(text) > 4 * 4096
    assert notice_free_head(text, MAX_TERMS) == _whole_head(text)
    assert reads == [4096]


@pytest.mark.parametrize("cue", ["copyright ", "(c) "], ids=["cue", "mark"])
def test_a_long_text_of_cues_is_read_in_bounded_time(cue: str) -> None:
    # "copyright " * 100000 took 1.4 s to strip whole; its first words are
    # settled from the first 4,096 characters.
    text = cue * 100000 + "Permission is hereby granted"
    start = time.monotonic()
    head = notice_free_head(text, MAX_TERMS)
    assert time.monotonic() - start < slack(0.4)
    assert head == (["copyright"] * MAX_TERMS if cue[0] == "c" else _whole_head(text))

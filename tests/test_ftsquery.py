# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The Tier 1 query (``licenseid.ftsquery``): the words kept, the cut of a
long word, and the cost of a very long word in a real-sized index."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import time
from collections.abc import Generator
from functools import lru_cache

import pytest
from conftest import make_memory_db_path
from long_text_db import LONG_TEXTS, long_text_detector
from timing import slack

from licenseid import database
from licenseid.detector import LicenseDetector
from licenseid.ftsquery import MAX_TERM_CHARS, MAX_TERMS, match_query
from licenseid.normalize import normalize_text

_FIXTURES = sorted(LONG_TEXTS.glob("*.json"), key=lambda p: p.name)


def _old_query(norm_text: str) -> str:
    """The builder before the cut (``database.search_candidates``)."""
    words = norm_text.split()[:20]
    return " OR ".join('"' + word.replace('"', '""') + '"' for word in words)


@lru_cache(maxsize=1)
def _texts() -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            path.name,
            normalize_text(
                json.loads(path.read_text(encoding="utf-8"))["license_text"]
            ),
        )
        for path in _FIXTURES
    )


def test_the_fixtures_are_there() -> None:
    assert len(_texts()) > 400


def test_head_and_tail_queries_equal_the_old_builder_for_every_fixture() -> None:
    """The head (first 100 words) and tail (last 20) windows of
    ``retrieval``: the cut changes none of them."""
    for name, text in _texts():
        words = text.split()
        for window in (words[:100], words[-MAX_TERMS:]):
            joined = " ".join(window)
            assert match_query(joined) == _old_query(joined), name


def test_no_word_of_the_long_text_fixtures_reaches_the_cut() -> None:
    """The index bound, for the 555 files of ``license-text-long`` (about 449
    IDs), not for all 708 rows of the List: a word below the cut matches what
    it matched before. Fails when a new fixture holds a longer word:
    re-decide ``MAX_TERM_CHARS``."""
    longest = max((len(word), name) for name, text in _texts() for word in text.split())
    assert longest[0] < MAX_TERM_CHARS, longest


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_no_words_is_an_empty_query(text: str) -> None:
    assert match_query(text) == ""


def test_the_first_twenty_words_are_kept() -> None:
    words = [f"w{i}" for i in range(MAX_TERMS + 1)]
    query = match_query(" ".join(words))
    assert query.count(" OR ") == MAX_TERMS - 1
    assert f'"w{MAX_TERMS - 1}"' in query
    assert f'"w{MAX_TERMS}"' not in query


def test_a_word_is_cut_to_the_limit() -> None:
    assert match_query("a" * (MAX_TERM_CHARS + 1)) == f'"{"a" * MAX_TERM_CHARS}"'
    assert match_query("a" * MAX_TERM_CHARS) == f'"{"a" * MAX_TERM_CHARS}"'


@pytest.mark.parametrize("char", ["語", "\U0001f600"], ids=["han", "non-bmp"])
def test_a_word_is_cut_by_code_point(char: str) -> None:
    assert match_query(char * 500) == f'"{char * MAX_TERM_CHARS}"'


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    path, keep_alive = make_memory_db_path("test_ftsquery")
    yield path
    keep_alive.close()


@pytest.mark.parametrize(
    "position", [MAX_TERM_CHARS - 1, MAX_TERM_CHARS, MAX_TERM_CHARS + 1]
)
def test_a_quote_at_the_cut_leaves_a_valid_query(db_path: str, position: int) -> None:
    """The cut comes before the quote is doubled: a ``"`` at either side of
    the limit never leaves a lone one (an FTS5 syntax error)."""
    word = "a" * (position - 1) + '"' + "b" * 10
    query = match_query(word)
    assert query.count('"') % 2 == 0
    db = database.LicenseDatabase(db_path, create=False)
    assert db.search_candidates(word, already_normalized=True) == []


def _spy_queries(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def spy(norm_text: str) -> str:
        query = match_query(norm_text)
        seen.append(query)
        return query

    monkeypatch.setattr(database, "match_query", spy)
    return seen


def _long_word_text(chars: int, word: str = "the") -> str:
    filler = "permission is hereby granted free of charge to any person"
    return filler + " " + (word * (chars // len(word) + 1))[:chars]


def test_no_match_phrase_of_a_detection_exceeds_the_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _spy_queries(monkeypatch)
    long_text_detector().detect(text=_long_word_text(20_000))
    assert seen
    for query in seen:
        for phrase in query.split(" OR "):
            assert len(phrase) <= MAX_TERM_CHARS + 2


def _timed_detect(detector: LicenseDetector, chars: int) -> float:
    start = time.monotonic()
    detector.detect(text=_long_word_text(chars))
    return time.monotonic() - start


def test_a_long_word_costs_no_seconds_in_tier_1() -> None:
    """On the real-sized index (about 450 texts) 60,000 characters of "the"
    took 14 to 20 s before the cut and takes 0.3 s now; the bound is
    10x of the Tier 1 cost, not of the Tier 2 cost, which grows with the text."""
    assert _timed_detect(long_text_detector(), 60_000) < slack(3.0)


@pytest.mark.benchmark
def test_two_million_characters_of_one_word_cost_no_seconds_in_tier_1() -> None:
    """Tier 1 alone: Tier 2 has its own gate (``similarity.build_probe``)
    and still scales with the text."""
    detector = long_text_detector()
    text = normalize_text(_long_word_text(2_000_000))
    start = time.monotonic()
    detector.db.search_candidates(text, already_normalized=True)
    assert time.monotonic() - start < slack(1.0)

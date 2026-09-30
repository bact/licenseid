# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""When Tier 2 probes a query and when it runs the full RapidFuzz alignment
scan. Both cost time in the query's characters, so a query of few words and
many characters (a blob, a long token) must not reach an expensive scan, and
a Japanese licence, whose words are long, must still be matched. Roadmap
item 16."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import base64
import json
import random
import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db
from rapidfuzz import fuzz

from licenseid import similarity
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text
from licenseid.types import CandidateMatch

# A candidate far longer than every query below, so the fragment branch
# (not the near-full-text branch) is the one in question.
CANDIDATE: CandidateMatch = {
    "license_id": "Long-1.0",
    "search_text": " ".join(["permission granted provided notice"] * 1000),
    "word_count": 4000,
}


def query(words: int, chars: int) -> str:
    """A normalised query of *words* words and *chars* characters: short
    words, then one word that takes up the rest."""
    short = ["word"] * (words - 1)
    rest = chars - len(" ".join(short)) - (1 if short else 0)
    return " ".join([*short, "x" * rest])


def even_query(words: int, per_word: int) -> str:
    """*words* words of *per_word* characters each."""
    return " ".join(["y" * per_word] * words)


LICENCE_WORDS = ["permission", "granted", "provided", "notice"]


def licence_query(words: int) -> str:
    """*words* words of the candidate's own text, so a probe passes."""
    return " ".join((LICENCE_WORDS * words)[:words])


def blob_around(words: int, blob_words: int) -> str:
    """*words* words of licence text with *blob_words* 60-character tokens
    on each side: the probe (the middle) passes, the whole is mostly blob."""
    blob = ["z" * 60] * blob_words
    return " ".join([*blob, licence_query(words), *blob])


# A candidate written without spaces, like Japanese: its "words" are long.
LONG_WORD_CANDIDATE: CandidateMatch = {
    "license_id": "Long-Words-1.0",
    "search_text": " ".join(["permissiongrantedprovidednotice"] * 1000),
    "word_count": 1000,
}


def scans(norm_input: str, cand: CandidateMatch | None = None) -> bool:
    """Whether scoring *norm_input* against *cand* (CANDIDATE by default) runs
    the alignment."""
    words = norm_input.split()
    with mock.patch.object(
        fuzz,
        "partial_ratio_alignment",
        autospec=True,
        wraps=fuzz.partial_ratio_alignment,
    ) as alignment:
        similarity.calculate_base_similarity(
            norm_input,
            len(words),
            set(words),
            cand or CANDIDATE,
            similarity.build_probe(words),
        )
    return alignment.called


@pytest.mark.parametrize(
    ("norm_input", "expected"),
    [
        (licence_query(100), True),  # an ordinary fragment
        (licence_query(300), True),  # probed, and the probe passes
        (even_query(300, 6), False),  # probed, and the probe fails
        (licence_query(500), False),  # 500 words: token_sort_ratio already
        # Few words, many characters: a probe by characters, which a blob
        # fails, not a scan that costs seconds to minutes.
        (query(27, 2150), False),
        (query(27, 40000), False),
        (even_query(30, 60), False),
        # Its probe (the middle) passes, but the whole is too long to scan.
        (blob_around(60, 70), False),
    ],
    ids=[
        "fragment",
        "probe-passes",
        "probe-fails",
        "500-words",
        "one-2000-token",
        "one-40000-token",
        "30x60",
        "blob-around-licence",
    ],
)
def test_which_queries_get_the_alignment_scan(norm_input: str, expected: bool) -> None:
    assert scans(norm_input) is expected


def test_long_words_that_match_get_the_alignment_scan() -> None:
    """100 words of 31 characters: long in characters for its words, as
    Japanese is, but its probe passes, so it is scanned."""
    norm_input = " ".join(["permissiongrantedprovidednotice"] * 100)
    assert scans(norm_input, LONG_WORD_CANDIDATE) is True


@pytest.mark.parametrize(
    ("words", "chars", "probe_len"),
    [
        (119, 1499, None),  # short enough to scan without a probe
        (119, 1500, 500),  # a probe by characters
        (1, 40000, 500),
        (120, 1000, 299),  # enough words for the word probe, however short
        (499, 3000, 299),  # the middle 60 words
        (500, 3000, None),  # never scanned, so never probed
    ],
)
def test_which_queries_get_a_probe(
    words: int, chars: int, probe_len: int | None
) -> None:
    norm_input = query(words, chars)
    assert (len(norm_input.split()), len(norm_input)) == (words, chars)
    probe = similarity.build_probe(norm_input.split())
    assert (None if probe is None else len(probe)) == probe_len


def test_the_word_probe_is_the_middle_60_words() -> None:
    words = [f"w{i}" for i in range(200)]
    assert similarity.build_probe(words) == " ".join(words[70:130])


def test_a_probe_is_cut_from_the_middle() -> None:
    by_chars = ["x" * 1000, "y" * 1000]  # too few words for the word probe
    assert similarity.build_probe(by_chars) == "x" * 250 + " " + "y" * 249
    long_words = [f"{i:03d}" + "z" * 36 for i in range(200)]  # 39 characters
    middle_60 = " ".join(long_words[70:130])  # too long for a probe
    start = (len(middle_60) - similarity.PROBE_MAX_CHARS) // 2
    expected = middle_60[start : start + similarity.PROBE_MAX_CHARS]
    assert similarity.build_probe(long_words) == expected


@pytest.mark.parametrize(
    ("words", "chars", "affordable"),
    [
        (499, 3000, True),
        (500, 3000, False),  # the long-query rule, unchanged
        (499, 6000, True),
        (499, 6001, False),
        (1, 6000, True),
        (1, 6001, False),
    ],
)
def test_alignment_affordable_boundaries(
    words: int, chars: int, affordable: bool
) -> None:
    norm_input = query(words, chars)
    assert (len(norm_input.split()), len(norm_input)) == (words, chars)
    assert similarity.alignment_affordable(norm_input, words) is affordable


LICENCE_TEXT = " ".join(
    f"clause {i} the licensor grants permission to use copy modify and "
    f"distribute the work provided that notice {i} is retained"
    for i in range(170)
)


@pytest.fixture
def long_licences_db() -> Generator[str, None, None]:
    """Five candidates of about 20,000 characters each (a long licence), all
    sharing the query's words, so each would get the full scan."""
    rows = [
        Lic(f"Long-{i}.0", f"Long {i}", search_text=f"{i} {LICENCE_TEXT}")
        for i in range(5)
    ]
    yield from seeded_db("test_similarity_long", rows)


def header_over(blob: str) -> str:
    return " ".join(LICENCE_TEXT.split()[:40]) + " " + blob


def licence_among_tokens() -> str:
    """200 words of licence text between 140 tokens of 22 characters on each
    side: the probe passes, and the words are short enough on average that
    only the scan's character limit stops it."""
    rnd = random.Random(2)
    tokens = [
        "".join(rnd.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=22))
        for _ in range(280)
    ]
    licence = LICENCE_TEXT.split()[:200]
    return " ".join([*tokens[:140], *licence, *tokens[140:]])


@pytest.mark.parametrize(
    "text",
    [
        header_over("a" * 4000),
        # Embedded base64: normalisation splits it into many medium tokens.
        header_over(base64.b64encode(random.Random(1).randbytes(3000)).decode()),
        licence_among_tokens(),
    ],
    ids=["one-token", "base64", "licence-among-tokens"],
)
def test_a_blob_is_matched_quickly(long_licences_db: str, text: str) -> None:
    """A licence over a blob used to run the full scan on every candidate:
    seconds to minutes per candidate at this length (item 16)."""
    matcher = AggregatedLicenseMatcher(long_licences_db)
    start = time.monotonic()
    matcher.match(text=text)
    assert time.monotonic() - start < 0.5  # 10x the time taken


FIXTURES = Path(__file__).parent / "fixtures" / "license-text-long"


def fixture_text(license_id: str) -> str:
    data = json.loads((FIXTURES / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


@pytest.fixture(scope="module")
def japanese_db() -> Generator[str, None, None]:
    """The Japanese licence among English ones."""
    rows = [
        Lic(lid, lid, search_text=normalize_text(fixture_text(lid)))
        for lid in ("CC-BY-SA-2.1-JP", "MIT", "Apache-2.0", "BSD-3-Clause")
    ]
    yield from seeded_db("test_similarity_japanese", rows)


@pytest.mark.parametrize("start, end", [(1500, 3200), (3000, 4500)])
def test_a_japanese_fragment_is_matched(japanese_db: str, start: int, end: int) -> None:
    """Japanese is written without spaces, so its words are long: a slice of
    it must not be taken for a blob (review of PR #62)."""
    text = fixture_text("CC-BY-SA-2.1-JP")[start:end]
    results = AggregatedLicenseMatcher(japanese_db).match(text=text)
    assert results[0]["license_id"] == "CC-BY-SA-2.1-JP"
    assert results[0]["score"] >= 0.85

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""When Tier 2 runs the full RapidFuzz alignment scan. Its cost follows the
query's length in characters, so a query that is few words but many
characters (a blob, a long token) must not reach it. Roadmap item 16."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import base64
import random
import time
from collections.abc import Generator
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db
from rapidfuzz import fuzz

from licenseid import similarity
from licenseid.matcher import AggregatedLicenseMatcher
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


def scans(norm_input: str) -> bool:
    """Whether scoring *norm_input* against CANDIDATE runs the alignment."""
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
            CANDIDATE,
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
        # Few words, many characters: token_sort_ratio, not a scan that
        # costs seconds to minutes.
        (query(27, 2150), False),
        (query(27, 40000), False),
        (even_query(30, 60), False),
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


@pytest.mark.parametrize(
    ("words", "chars", "affordable"),
    [
        (119, 1499, True),
        (119, 1500, False),  # no probe, and long: too dear
        (120, 1500, True),  # a probe spares the weak candidates
        (100, 1600, False),  # exactly 16 a word, but unprobed and long
        (150, 2400, True),  # exactly 16 characters a word
        (150, 2401, False),  # just over
        (499, 3000, True),
        (500, 3000, False),  # the long-query rule, unchanged
        (1, 16, True),
        (1, 17, False),
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
    for i in range(1000)
)


@pytest.fixture
def long_licences_db() -> Generator[str, None, None]:
    """Five candidates of about 110,000 characters each, all sharing the
    query's words, so each would get the full scan."""
    rows = [
        Lic(f"Long-{i}.0", f"Long {i}", search_text=f"{i} {LICENCE_TEXT}")
        for i in range(5)
    ]
    yield from seeded_db("test_similarity_long", rows)


@pytest.mark.parametrize(
    "blob",
    [
        "a" * 4000,
        # Embedded base64: normalisation splits it into many medium tokens.
        base64.b64encode(random.Random(1).randbytes(3000)).decode(),
    ],
    ids=["one-token", "base64"],
)
def test_a_blob_is_matched_quickly(long_licences_db: str, blob: str) -> None:
    """A licence header over a blob used to run the full scan on every
    candidate: seconds per candidate at this length (item 16)."""
    text = " ".join(LICENCE_TEXT.split()[:40]) + " " + blob
    matcher = AggregatedLicenseMatcher(long_licences_db)
    start = time.monotonic()
    matcher.match(text=text)
    assert time.monotonic() - start < 1.0

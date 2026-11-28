# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 2 on the word region (``licenseid.wordregion``), through
``detect()``: a fragment answers as the whole-text scan answers it; the
input is coded once a call; the character steps get the region; a candidate
without codes is scanned whole; a database whose stored codes fail their
check answers as an intact build; adversarial inputs stay cheap.

The database is the long-text fixtures' (every licence of the List with its
text: Apache-2.0 beside ECL-2.0, the BSD families as real near neighbours).
Rules on made-up texts: ``test_word_region``."""
# pylint: disable=missing-function-docstring

import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from types import MappingProxyType
from unittest import mock

import pytest
from db_variants import writer
from list_entries import lic_entry
from long_text_db import LONG_TEXTS, long_text_detector
from packaged_list import database_of
from rapidfuzz import fuzz
from timing import slack

from licenseid import similarity, wordregion
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.textcorpus import TextCorpus
from licenseid.textgrams import split_words
from licenseid.textstore import TEXT
from licenseid.types import CandidateMatch, DetectOptions


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


APACHE = _text("Apache-2.0")
PROSE = (
    "This project ships a command line tool and a small library. Read the"
    " guide for the options of each command and the examples below. "
)

FRAGMENTS = {
    "head": _text("BSD-3-Clause")[:700],
    "middle": APACHE[3000:6000],
    "tail": _text("MIT")[-500:],
    "in-prose": PROSE + APACHE[6000:7500] + " " + PROSE,
    "long-middle": _text("EPL-2.0")[6000:8500],
    "japanese": _text("CC-BY-SA-2.1-JP")[1500:3200],
    "chinese": _text("MulanPSL-2.0")[200:900],
}


def top(text: str) -> tuple[str, float]:
    results = long_text_detector().detect(text)
    return results[0]["expression"], results[0]["score"]


@pytest.fixture(name="before", scope="module")
def _before() -> dict[str, tuple[str, float]]:
    """The top answers with every candidate scanned whole."""
    with mock.patch.object(wordregion.WordRegions, "region", return_value=None):
        return {key: top(text) for key, text in FRAGMENTS.items()}


@pytest.mark.parametrize("key", list(FRAGMENTS))
def test_a_fragment_answers_as_the_whole_text_scan(
    key: str, before: dict[str, tuple[str, float]]
) -> None:
    expression, score = top(FRAGMENTS[key])
    assert expression == before[key][0]
    assert score >= 0.85
    assert score == pytest.approx(before[key][1], abs=0.005)


def _haystacks(text: str) -> dict[str, list[int]]:
    """The lengths of the texts the character alignment was given for each
    candidate of *text* (not those of the word alignment, which aligns
    codes)."""
    seen: dict[str, list[int]] = {}
    real = similarity.fragment_similarity

    def spy(query: similarity.Query, license_id: str, search_text: str) -> object:
        with mock.patch.object(
            fuzz,
            "partial_ratio_alignment",
            autospec=True,
            side_effect=fuzz.partial_ratio_alignment,
        ) as alignment:
            found = real(query, license_id, search_text)
        seen[license_id] = [
            len(call.args[1])
            for call in alignment.call_args_list
            if call.args[0] == query.text
        ]
        return found

    with mock.patch.object(similarity, "fragment_similarity", spy):
        long_text_detector().detect(text)
    return seen


def test_the_character_steps_get_the_region_not_the_text() -> None:
    norm = normalize_text(FRAGMENTS["middle"])
    seen = _haystacks(FRAGMENTS["middle"])
    # The region, padded, with a wall of the input's length on each side.
    assert len(seen["Apache-2.0"]) == 1
    assert 3 * len(norm) < seen["Apache-2.0"][0] < 3 * len(norm) + 200
    assert seen["Apache-2.0"][0] < len(normalize_text(APACHE))


def test_the_input_is_coded_once_a_call() -> None:
    detector = long_text_detector()
    detector.detect(FRAGMENTS["middle"])  # the lazy reads of a first call
    with mock.patch.object(
        wordregion, "split_words", autospec=True, wraps=split_words
    ) as split:
        detector.detect(FRAGMENTS["middle"])
        assert split.call_count == 1
        detector.detect(FRAGMENTS["head"])
        assert split.call_count == 2


# -- A candidate without codes: the whole text, as before ----------------------


def _ranked(candidate: CandidateMatch) -> list[tuple[str, float]]:
    detector = long_text_detector()
    with detector.db.reading():
        ranked = detector._rank_candidates(  # pylint: disable=protected-access
            [candidate], normalize_text(FRAGMENTS["middle"]), DetectOptions()
        )
    return [(r["license_id"], r["similarity"]) for r in ranked]


@pytest.mark.parametrize(
    "candidate",
    [
        # A marker's or hint's ID the corpus has no text of.
        CandidateMatch(license_id="LicenseRef-x", search_text=normalize_text(APACHE)),
        # A text other than the corpus's for its ID.
        CandidateMatch(
            license_id="Apache-2.0", search_text=normalize_text(APACHE) + " omega"
        ),
    ],
    ids=["unknown-id", "other-text"],
)
def test_a_candidate_without_codes_is_scanned_whole(candidate: CandidateMatch) -> None:
    with mock.patch.object(
        wordregion, "located", autospec=True, side_effect=wordregion.located
    ) as located:
        found = _ranked(candidate)
    located.assert_not_called()  # never aligned by words
    with mock.patch.object(wordregion.WordRegions, "region", return_value=None):
        assert found == _ranked(candidate)


def test_a_hinted_candidate_is_located() -> None:
    """A hint's candidate is a List text: it has codes like the others."""
    detector = long_text_detector()
    with mock.patch.object(
        wordregion, "located", autospec=True, side_effect=wordregion.located
    ) as located:
        detector.detect(FRAGMENTS["middle"], hint=["ECL-2.0"])
    ecl = normalize_text(_text("ECL-2.0"))
    assert any(call.args[2] == ecl for call in located.call_args_list)


# -- Stored codes that fail their check ----------------------------------------

DAMAGED_IDS = ("Apache-2.0", "ECL-2.0", "BSD-3-Clause", "BSD-2-Clause", "MIT", "X11")
RAW = to_bundle(
    SpdxData(
        "9.99",
        None,
        tuple(
            lic_entry(license_id, f"Name {license_id}") for license_id in DAMAGED_IDS
        ),
        (),
        MappingProxyType({lid: _text(lid) for lid in DAMAGED_IDS}),
        MappingProxyType({}),
    )
)


@pytest.fixture(name="built")
def _built(tmp_path: Path) -> Path:
    path = tmp_path / "licenses.db"
    database_of(RAW, path)
    return path


def _answers(path: Path) -> list[list[tuple[str, float]]]:
    detector = LicenseDetector(str(path))
    texts = [APACHE[3000:6000], APACHE[9000:10500], _text("BSD-3-Clause")[:700]]
    return [[(r["expression"], r["score"]) for r in detector.detect(t)] for t in texts]


def test_damaged_stored_codes_answer_as_an_intact_build(built: Path) -> None:
    intact = _answers(built)
    with writer(built) as conn:  # two texts' codes swapped: the check fails
        conn.execute(
            "UPDATE text_codes SET body = CASE owner_id WHEN 'Apache-2.0' THEN"
            f" (SELECT body FROM text_codes WHERE kind = '{TEXT}'"
            " AND owner_id = 'MIT')"
            f" ELSE (SELECT body FROM text_codes WHERE kind = '{TEXT}'"
            " AND owner_id = 'Apache-2.0') END"
            f" WHERE kind = '{TEXT}' AND owner_id IN ('Apache-2.0', 'MIT')"
        )
    with mock.patch.object(
        TextCorpus, "build", autospec=True, wraps=TextCorpus.build
    ) as build:
        assert _answers(built) == intact
    build.assert_called_once()  # coded again in memory, as update codes them


# -- Adversarial ---------------------------------------------------------------


def test_scattered_words_of_a_text_locate_nothing() -> None:
    """300 words of Apache-2.0, shuffled: no region (the words are there,
    not in order), and no answer."""
    shuffled = normalize_text(APACHE).split()[400:700]
    random.Random(3).shuffle(shuffled)
    found: list[object] = []
    real = wordregion.located

    def spy(
        codes: str, text_codes: str, text: str, counts: Counter[str] | None = None
    ) -> object:
        found.append(real(codes, text_codes, text, counts))
        return found[-1]

    with mock.patch.object(wordregion, "located", autospec=True, side_effect=spy):
        # The hint makes Apache-2.0 a candidate, which no gram would.
        results = long_text_detector().detect(" ".join(shuffled), hint=["Apache-2.0"])
    assert all(r["score"] < 0.85 for r in results)
    assert found
    assert found == [None] * len(found)


@pytest.mark.parametrize(
    ("repeat", "bound"),
    [
        pytest.param(25, 1.0, id="small"),
        pytest.param(400, 2.0, id="large", marks=pytest.mark.benchmark),
    ],
)
def test_one_phrase_repeated_is_cheap(repeat: int, bound: float) -> None:
    text = "permission is hereby granted free of charge " * repeat
    detector = long_text_detector()
    start = time.monotonic()
    with mock.patch.object(
        wordregion, "split_words", autospec=True, wraps=split_words
    ) as split:
        results = detector.detect(text)
    assert time.monotonic() - start < slack(bound)
    assert all(r["score"] < 0.85 for r in results)
    assert split.call_count <= 1


@pytest.mark.parametrize(
    ("prose_chars", "bound"),
    [
        pytest.param(20_000, 1.0, id="20kb"),
        pytest.param(1_000_000, 10.0, id="1mb", marks=pytest.mark.benchmark),
    ],
)
def test_a_text_after_much_prose_is_never_aligned_by_characters(
    prose_chars: int, bound: float
) -> None:
    """Too long to align (``similarity.alignment_affordable``): no word
    region either, whatever its size."""
    text = (PROSE * (prose_chars // len(PROSE) + 1))[:prose_chars] + APACHE[:3000]
    detector = long_text_detector()
    start = time.monotonic()
    with (
        mock.patch.object(
            fuzz,
            "partial_ratio_alignment",
            autospec=True,
            wraps=fuzz.partial_ratio_alignment,
        ) as alignment,
        mock.patch.object(
            wordregion, "split_words", autospec=True, wraps=split_words
        ) as split,
    ):
        detector.detect(text)
    assert time.monotonic() - start < slack(bound)
    assert not [c for c in alignment.call_args_list if len(c.args[0]) > 6000]
    split.assert_not_called()


SHORT_WORDS = "on an as an as is to do so of or in if it is by or is 5 6 7 1 2 5 "


@pytest.mark.parametrize(
    ("text", "bound"),
    [
        pytest.param((SHORT_WORDS * 2_000)[:100_000], 3.0, id="short-words-100kb"),
        pytest.param("a b c " * 17_000, 3.0, id="abc-100kb"),
        pytest.param(
            (SHORT_WORDS * 20_000)[:1_000_000],
            30.0,
            id="short-words-1mb",
            marks=pytest.mark.benchmark,
        ),
        pytest.param(
            "a b c " * 170_000, 15.0, id="abc-1mb", marks=pytest.mark.benchmark
        ),
    ],
)
def test_words_of_two_letters_or_fewer_are_never_aligned(
    text: str, bound: float
) -> None:
    """Gram candidates come from words of two letters too: such an input is
    too long to align (``similarity.alignment_affordable``), so each
    candidate costs one sorted-words comparison of the whole input, no word
    region and no alignment. That comparison is the cost: 3 s for 1 MB on
    the full List, against 0.8 s in 0.9.4, which found no candidate."""
    detector = long_text_detector()
    start = time.monotonic()
    with (
        mock.patch.object(
            fuzz,
            "token_sort_ratio",
            autospec=True,
            side_effect=fuzz.token_sort_ratio,
        ) as sorted_words,
        mock.patch.object(
            fuzz,
            "partial_ratio_alignment",
            autospec=True,
            side_effect=fuzz.partial_ratio_alignment,
        ) as alignment,
        mock.patch.object(
            wordregion, "split_words", autospec=True, side_effect=split_words
        ) as split,
    ):
        results = detector.detect(text)
    assert time.monotonic() - start < slack(bound)
    assert all(r["score"] < 0.85 for r in results)
    alignment.assert_not_called()
    split.assert_not_called()
    assert sorted_words.call_count <= 10
    norm = normalize_text(text)
    assert all(call.args[0] == norm for call in sorted_words.call_args_list)


def test_a_japanese_text_is_not_aligned_by_words_with_an_english_one() -> None:
    """One code a Han or kana character: a Japanese input has as many codes
    as characters, and aligning them with an English text's codes cost as
    much as the character steps. They share no code, so no word alignment
    is made (``wordregion.best_possible``)."""
    text = _text("CC-BY-SA-2.1-JP")
    norm = normalize_text(text)
    bounds: list[float] = []
    real = wordregion.best_possible

    def spy(counts: Counter[str], input_len: int, text_codes: str) -> float:
        bounds.append(real(counts, input_len, text_codes))
        return bounds[-1]

    with (
        mock.patch.object(wordregion, "best_possible", autospec=True, side_effect=spy),
        mock.patch.object(
            fuzz,
            "partial_ratio_alignment",
            autospec=True,
            side_effect=fuzz.partial_ratio_alignment,
        ) as alignment,
    ):
        results = long_text_detector().detect(text)
    assert results[0]["expression"] == "CC-BY-SA-2.1-JP"
    assert bounds
    assert all(bound < 20 for bound in bounds)
    assert all(call.args[0] == norm for call in alignment.call_args_list)


def test_the_diff_window_ends_on_whole_words() -> None:
    """--diff's window (``_diff_pair``) starts and ends on a word of the
    text, also where the fragment cuts one."""
    detector = long_text_detector()
    text = normalize_text(APACHE)
    # Cut three letters into a long word at both ends.
    long_words = [m.start() for m in re.finditer(r"\S{8,}", text)]
    first = next(at for at in long_words if at > 3000) + 3
    last = next(at for at in long_words if at > first + 2500) + 3
    norm, window = detector._diff_pair(  # pylint: disable=protected-access
        text[first:last], "Apache-2.0"
    )
    assert norm == text[first:last]
    assert window.split()[0].endswith(norm.split()[0])
    assert window.split()[0] != norm.split()[0]
    start = text.index(window)
    assert start == 0 or text[start - 1] == " "
    assert start + len(window) == len(text) or text[start + len(window)] == " "
    assert window.split()[0] in text.split()
    assert window.split()[-1] in text.split()

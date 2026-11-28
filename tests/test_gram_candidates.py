# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 1 from word grams, through ``detect()``: one lookup a call, the
filters before the selection, the markers and hints after it, ``TEXTS``
unfiltered, the bound on the grams read. Rules on made-up tables:
``test_gramselect``.

The database is the long-text fixtures' (every licence of the List with its
text, so MIT, JSON, MIT-0 and X11 are real near neighbours): on a database of
a few rows every row is a candidate whatever the rules say."""
# pylint: disable=missing-function-docstring

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from db_asserts import traced_statements
from long_text_db import LONG_TEXTS, long_text_detector
from matcher_db import PROSE
from timing import slack

from licenseid import database, retrieval
from licenseid.gramselect import GRAM_LIMIT
from licenseid.retrieval import gram_text
from licenseid.textgrams import input_grams
from licenseid.types import DetectOptions


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


MIT = _text("MIT")
APACHE = _text("Apache-2.0")


def rows(text: str, **options: Any) -> list[tuple[str, float]]:
    return [
        (r["expression"], r["score"])
        for r in long_text_detector().detect(text, **options)
    ]


def candidates(text: str, **options: Any) -> retrieval.Candidates:
    db = long_text_detector().db
    return retrieval.get_candidates(db, cast(DetectOptions, options), text)


def ids(text: str, **options: Any) -> list[str]:
    return [c["license_id"] for c in candidates(text, **options).found]


# -- One lookup a call ---------------------------------------------------------


def test_one_gram_lookup_and_one_connection(
    monkeypatch: pytest.MonkeyPatch, opened: list[sqlite3.Connection]
) -> None:
    detector = long_text_detector()
    detector.detect(MIT)  # the lazy reads of a first call
    looked = mock.Mock(wraps=database.gram_scores)
    monkeypatch.setattr("licenseid.retrieval.gram_scores", looked)
    opened.clear()

    assert detector.detect(MIT)[0]["expression"] == "MIT"

    looked.assert_called_once()
    assert len(opened) == 1


def test_no_full_text_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not beside ``opened``: monkeypatch would restore its patch after it
    ends, for every later test."""
    detector = long_text_detector()
    detector.detect(MIT)
    statements = traced_statements(monkeypatch)

    assert detector.detect(MIT)[0]["expression"] == "MIT"

    assert statements
    assert not [s for s in statements if "MATCH" in s.upper()]


@pytest.mark.parametrize("text", ["MIT", "MIT License", "ISC License"])
def test_an_input_of_no_gram_keeps_its_name_answer(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    assert not input_grams(gram_text(text))
    looked = mock.Mock(wraps=database.gram_scores)
    monkeypatch.setattr("licenseid.retrieval.gram_scores", looked)
    assert rows(text)[0][0] == text.split()[0]
    looked.assert_not_called()


# -- Markers and hints after the grams ---------------------------------------


def test_a_heading_answers_where_the_grams_give_none() -> None:
    text = "MIT License\n\n" + PROSE * 3
    assert not ids(text)
    assert rows(text)[0][0] == "MIT"


def test_a_hint_is_scored_where_the_grams_give_none() -> None:
    assert not ids(PROSE * 3)
    assert [i for i, _ in rows(PROSE * 3, hint=["ISC"])] == ["ISC"]


# -- Filters before the selection; TEXTS unfiltered ------------------------------


def test_the_best_text_excluded_the_next_answers() -> None:
    assert ids(MIT)[0] == "MIT"
    assert "MIT" not in ids(MIT, exclude=["MIT"])
    found = long_text_detector().detect(MIT, exclude=["MIT"])
    assert found[0]["expression"] == "JSON"
    assert "MIT" not in [r["expression"] for r in found]


def test_only_common_drops_a_rare_text_before_the_selection() -> None:
    body = _text("JSON").split("\n", 2)[2]  # no "JSON License" heading
    assert ids(body)[0] == "JSON"
    assert "JSON" not in ids(body, only_common=True)
    # As in 0.9.4: the closest licence the filter allows answers.
    assert rows(body, only_common=True)[0][0] == "MIT"


def test_only_spdx_off_adds_nothing_on_a_list_database() -> None:
    assert ids(MIT, only_spdx=False) == ids(MIT)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"exclude": ["MIT"]},
        {"exclude": ["MIT", "JSON", "MIT-0"]},
        {"only_common": True},
        {"only_spdx": False},
        {"hint": ["ISC"]},
        {"enable_popularity": True},
        {"variant": "as-written"},
    ],
    ids=repr,
)
def test_texts_ignore_every_option(options: dict[str, Any]) -> None:
    found = long_text_detector().detect(MIT, **options)
    assert found
    assert all(r["texts"] == ["MIT"] for r in found)


# -- The bound on the grams read ----------------------------------------------


def test_past_the_bound_rows_come_from_the_grams_read_and_texts_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "This project is licensed as follows.\n\n" + MIT  # not exact
    grams = len(input_grams(gram_text(text)))
    monkeypatch.setattr("licenseid.retrieval.GRAM_LIMIT", grams)
    assert not candidates(text).bounded
    found = long_text_detector().detect(text)
    assert (found[0]["expression"], found[0]["texts"]) == ("MIT", ["MIT"])

    monkeypatch.setattr("licenseid.retrieval.GRAM_LIMIT", grams - 1)
    assert candidates(text).bounded
    found = long_text_detector().detect(text)
    assert found[0]["expression"] == "MIT"
    assert all(r["texts"] is None for r in found)

    # The first 12 grams: the sentence, the title and the copyright line.
    monkeypatch.setattr("licenseid.retrieval.GRAM_LIMIT", 12)
    assert candidates(text).bounded
    assert "MIT" in ids(text)


def test_past_the_bound_texts_is_none_too() -> None:
    """An input past the bound has more tokens than the whole-text search
    reads, so ``texts()`` agrees with the record: no partial list."""
    text = MIT + "\n" + " ".join(f"w{i}" for i in range(50_000))
    assert candidates(text).bounded
    assert long_text_detector().texts(text) is None


def test_no_list_text_reaches_the_bound() -> None:
    longest = max(len(input_grams(gram_text(_text(p.stem)))) for p in _long_paths())
    assert longest < GRAM_LIMIT // 5


def _long_paths() -> list[Path]:
    return sorted(LONG_TEXTS.glob("*.json"))


@pytest.mark.parametrize(
    "words", [10_000, pytest.param(100_000, marks=pytest.mark.benchmark)]
)
def test_many_distinct_words_are_cheap(words: int) -> None:
    text = " ".join(f"w{i}" for i in range(words))
    long_text_detector().detect(MIT)
    start = time.monotonic()
    assert not long_text_detector().detect(text)
    elapsed = time.monotonic() - start
    assert candidates(text).bounded is (words > GRAM_LIMIT)
    assert elapsed < slack(0.4 * words / 10_000)


# -- Han and kana, wrapped at another width ------------------------------------


def _wrapped(license_id: str, start: int, end: int, width: int) -> str:
    chars = re.sub(r"\s+", "", _text(license_id))[start:end]
    return "\n".join(chars[at : at + width] for at in range(0, len(chars), width))


@pytest.mark.parametrize("width", [7, 17, 41])
@pytest.mark.parametrize(
    ("license_id", "start", "end"),
    [("CC-BY-SA-2.1-JP", 400, 1000), ("MulanPSL-2.0", 200, 700)],
    ids=["kana", "han"],
)
def test_han_and_kana_rewrapped_keep_their_text_first(
    license_id: str, start: int, end: int, width: int
) -> None:
    text = _wrapped(license_id, start, end, width)
    assert ids(text)[0] == license_id
    assert rows(text)[0][0] == license_id


# -- Adversarial -------------------------------------------------------------------


LEGAL_PROSE = (
    "This program is free software and it is provided as is. You can"
    " redistribute it under the terms of the license you choose. The software"
    " is provided without warranty of any kind, express or implied, including"
    " but not limited to the warranties of merchantability. In no event shall"
    " the authors be liable. See the documentation for the list of"
    " contributors and the copyright holders of this project. "
) * 3


def test_prose_of_common_licence_phrases_answers_nothing() -> None:
    assert ids(LEGAL_PROSE)  # it shares grams with many texts
    assert all(score < 0.85 for _, score in rows(LEGAL_PROSE))


def _replaced(text: str, every: int) -> str:
    words = text.split()
    return " ".join(
        "zzq" if at % every == every - 1 else w for at, w in enumerate(words)
    )


def test_every_third_word_replaced_leaves_no_gram() -> None:
    """A known limit of 3-grams: every gram holds a replaced word. 0.9.4
    listed Apache-2.0 at 0.78, no answer either way."""
    assert not ids(_replaced(APACHE, 3))
    assert rows(_replaced(APACHE, 3)) == []


def test_every_fourth_word_replaced_keeps_its_text_first() -> None:
    assert ids(_replaced(APACHE, 4))[0] == "Apache-2.0"
    assert rows(_replaced(APACHE, 4))[0][0] == "Apache-2.0"


def test_two_texts_joined_give_candidates_of_both() -> None:
    text = MIT + "\n\n" + APACHE
    assert {"MIT", "Apache-2.0"} <= set(ids(text))
    assert long_text_detector().texts(text) == ["MIT", "Apache-2.0"]


_ORDER_SCRIPT = """
import sys
from matcher_db import Lic, seeded_db
from licenseid.database import LicenseDatabase
from licenseid.retrieval import get_candidates
TEXT = "the quick brown fox jumps over the lazy dog again"
ROWS = [Lic(f"{c}-1.0", c, search_text=TEXT) for c in "QWERTYUIOPASDFGHJKLZXC"]
for path in seeded_db("order", ROWS):
    found = get_candidates(LicenseDatabase(path), {}, TEXT).found
    print(" ".join(c["license_id"] for c in found))
"""


def test_equal_scores_keep_row_order_under_any_hash_seed(tmp_path: Path) -> None:
    tests = str(Path(__file__).parent)
    runs = set()
    for seed in ("1", "2"):
        env = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": os.pathsep.join([tests, *sys.path]),
            "HOME": str(tmp_path),
        }
        runs.add(
            subprocess.run(
                [sys.executable, "-c", _ORDER_SCRIPT],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
    expected = " ".join(f"{c}-1.0" for c in "QWERTYUIOPASDFGHJKLZXC"[:20])
    assert runs == {expected + "\n"}

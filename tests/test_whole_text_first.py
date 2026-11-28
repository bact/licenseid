# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whole text first, through ``detect()``: the search of ``TEXTS`` runs on
one candidate set per input (``textcandidates``) before Tier 2, and a text
it finds alone narrows Tier 2 to that text's group and three runner-ups,
which rank under it. Rules on made-up tables: ``test_whole_text_rules``.

The database is the long-text fixtures' (every licence of the List with its
text, so MIT, JSON, SSH-short and SSH-OpenSSH are real near neighbours): on
a database of a few rows every row is a candidate whatever the rules say."""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Generator
from typing import Any, cast
from unittest import mock

import pytest
from conftest import GivenWarnings
from long_text_db import LONG_TEXTS, long_text_detector
from several_texts import several_text
from template_texts import template_texts_db

from licenseid import retrieval, textcandidates
from licenseid.database import LicenseDatabase, text_corpus
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.retrieval import Candidates, get_candidates, text_candidates
from licenseid.textnames import named_texts, text_groups
from licenseid.types import DetectOptions
from licenseid.wholetexts import found_texts


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


# A made-up project's licence file: a line naming the MIT licence, a rule,
# a title and a copyright line before the List's MIT text. Tier 2 alone
# ranks JSON (the MIT text and one sentence) over MIT on it: 0.9605 against
# 0.9594 before whole text first (``MIT_FAMILY``).
MIT_BODY = """Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
MIT_FILE = (
    "widgetlib is distributed under the terms of the MIT licence, which"
    " follows.\n\n- - - - -\n\nThe MIT License\n\n"
    "Copyright (c) 2024 Jane Doe and contributors\n\n" + MIT_BODY
)


# MIT with its template (the copyright line is a variable part), JSON and
# their near neighbours, built as ``update`` builds a database (the
# fingerprints, and so the scores, depend on the licences beside them).
MIT_FAMILY = (
    "MIT",
    "JSON",
    "0BSD",
    "FSL-1.1-MIT",
    "Fair",
    "HPND",
    "ICU",
    "ISC",
    "MIT-0",
    "MIT-CMU",
    "MIT-Click",
    "MIT-Festival",
    "MIT-Khronos-old",
    "MIT-Modern-Variant",
    "MIT-STK",
    "MIT-Wu",
    "MIT-advertising",
    "MIT-enna",
    "MIT-feh",
    "MIT-open-group",
    "MIT-testregex",
    "MITNFA",
    "X11-distribute-modifications-variant",
    "X11-no-permit-persons",
    "X11-swapped",
    "X11",
    "Xnet",
    "curl",
)


@pytest.fixture(scope="module", name="mit_detector")
def _mit_detector(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[LicenseDetector, None, None]:
    path = template_texts_db(tmp_path_factory.mktemp("mit_family"), MIT_FAMILY)
    yield LicenseDetector(path)


def _candidates(db: LicenseDatabase, text: str, **options: Any) -> Candidates:
    with db.reading():
        return get_candidates(db, cast(DetectOptions, options), text)


def _rows(results: list[Any]) -> list[tuple[str, float]]:
    return [(r["expression"], r["score"]) for r in results]


# -- JSON over MIT -------------------------------------------------------------


def test_the_mit_text_found_whole_answers_mit_not_json(
    mit_detector: LicenseDetector,
) -> None:
    results = mit_detector.detect(MIT_FILE)
    assert results[0]["expression"] == "MIT"
    assert results[0]["score"] == pytest.approx(0.9594)
    assert results[0]["texts"] == ["MIT"]
    # JSON scores 0.9605, above the text found: left out, not ranked under it
    # with a score of its own above the answer.
    assert "JSON" not in [r["expression"] for r in results]
    assert all(r["score"] < results[0]["score"] for r in results[1:])


def test_tier_2_scores_the_group_and_three_runner_ups(
    mit_detector: LicenseDetector,
) -> None:
    found = _candidates(mit_detector.db, MIT_FILE)
    assert found.narrowed is not None
    assert found.narrowed.group == {"MIT"}
    scored = [c["license_id"] for c in found.found]
    assert scored[0] == "MIT" and set(scored[1:]) == found.narrowed.runner_ups
    assert len(found.narrowed.runner_ups) == 3
    assert "JSON" in found.narrowed.runner_ups


def test_a_found_text_the_filters_take_out_does_not_narrow(
    mit_detector: LicenseDetector,
) -> None:
    """``exclude`` of the text found: today's selection among the rest, and
    the next text answers (JSON, as with every release)."""
    detector = mit_detector
    found = _candidates(detector.db, MIT_FILE, exclude=["MIT"])
    assert found.narrowed is None
    assert "MIT" not in [c["license_id"] for c in found.found]
    results = detector.detect(MIT_FILE, exclude=["MIT"])
    assert results[0]["expression"] == "JSON"
    assert results[0]["texts"] == ["MIT"]  # TEXTS reads no filter


def test_an_excluded_runner_up_makes_room_for_the_next(
    mit_detector: LicenseDetector,
) -> None:
    found = _candidates(mit_detector.db, MIT_FILE, exclude=["JSON"])
    assert found.narrowed is not None
    assert "JSON" not in found.narrowed.runner_ups
    assert len(found.narrowed.runner_ups) == 3


# -- Guard ---------------------------------------------------------------------


def test_a_short_text_inside_a_fragment_of_a_longer_one_does_not_narrow() -> None:
    """``SSH-short`` is found whole in the head of ``SSH-OpenSSH``, which
    shares more than 1.1 times its grams: the longer text answers."""
    head = _text("SSH-OpenSSH")[:1500]
    detector = long_text_detector()
    assert _candidates(detector.db, head).narrowed is None
    top = detector.detect(head)[0]
    assert (top["expression"], top["texts"]) == ("SSH-OpenSSH", ["SSH-short"])


def test_the_short_text_alone_narrows_to_itself() -> None:
    text = _text("SSH-short")
    detector = long_text_detector()
    narrow = _candidates(detector.db, text).narrowed
    assert narrow is not None and narrow.group == {"SSH-short"}
    top = detector.detect(text)[0]
    assert (top["expression"], top["exact"]) == ("SSH-short", True)


# -- Several texts, none, the bound ---------------------------------------------


def test_several_texts_found_keep_the_selection() -> None:
    text = several_text("mit-then-gpl3")
    detector = long_text_detector()
    assert _candidates(detector.db, text).narrowed is None
    assert not detector.detect(text)  # firsttext refuses the GPL answer


def test_several_texts_found_keep_the_selection_whatever_the_first() -> None:
    """The longer text first: no other text shares more of the input, so
    only the count of texts found keeps the selection."""
    text = _text("Apache-2.0") + "\n\n" + _text("MIT")
    detector = long_text_detector()
    with detector.db.reading():
        found = text_candidates(detector.db, text).found("")
    assert found is not None and found.rows == ["Apache-2.0", "MIT"]
    assert _candidates(detector.db, text).narrowed is None


def test_no_text_found_keeps_the_selection() -> None:
    text = " ".join(normalize_text(_text("Apache-2.0")).split()[100:160])
    detector = long_text_detector()
    found = _candidates(detector.db, text)
    assert found.narrowed is None and found.found
    assert detector.detect(text)[0]["texts"] is None


def test_past_the_bound_of_grams_there_is_no_search_and_no_narrowing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retrieval, "GRAM_LIMIT", 40)
    search = mock.Mock(wraps=found_texts)
    monkeypatch.setattr(textcandidates, "found_texts", search)
    detector = long_text_detector()
    text = _text("MIT")
    found = _candidates(detector.db, text)
    assert found.bounded and found.narrowed is None
    assert detector.detect(text)[0]["texts"] == ["MIT"]  # exact: its own text
    assert detector.texts(text) is None
    search.assert_not_called()


def test_under_the_none_bar_nothing_is_searched_for_tier_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One gram of MIT among forty unknown words: no candidate, so no
    search before Tier 2; ``texts()`` still searches (one text shares a
    gram)."""
    text = "permission is hereby " + " ".join(f"zq{n}xv" for n in range(40))
    search = mock.Mock(wraps=found_texts)
    monkeypatch.setattr(textcandidates, "found_texts", search)
    detector = long_text_detector()
    assert not detector.detect(text)
    search.assert_not_called()
    assert detector.texts(text) is None
    search.assert_called_once()


def test_an_input_that_shares_no_gram_is_never_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search = mock.Mock(wraps=found_texts)
    monkeypatch.setattr(textcandidates, "found_texts", search)
    text = " ".join(f"zq{n}xv" for n in range(60))
    assert long_text_detector().texts(text) is None
    search.assert_not_called()


# -- One candidate set an input ------------------------------------------------


def test_the_search_before_tier_2_stands_for_the_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MIT text and a line: the search with no answer finds MIT alone,
    so ``firsttext`` and ``TEXTS`` read it, not a second search."""
    search = mock.Mock(wraps=found_texts)
    monkeypatch.setattr(textcandidates, "found_texts", search)
    text = _text("MIT") + "\nAnd a line of our own after the licence text.\n"
    top = long_text_detector().detect(text)[0]
    assert (top["expression"], top["exact"], top["texts"]) == ("MIT", False, ["MIT"])
    assert [c.args[2] for c in search.call_args_list] == [""]


def test_several_texts_are_searched_again_with_the_answer(
    monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    search = mock.Mock(wraps=found_texts)
    monkeypatch.setattr(textcandidates, "found_texts", search)
    text = several_text("mit-then-gpl3")
    detector = long_text_detector()
    with mock.patch("licenseid.firsttext.first_stands", return_value=True):
        top = detector.detect(text)[0]
    assert top["texts"] == ["MIT", "GPL-3.0-only"]
    assert [c.args[2] for c in search.call_args_list] == ["", "GPL-3.0-only"]
    assert given.conditions() <= {"variant not stated"}


def test_the_set_holds_the_top_20_and_every_text_held() -> None:
    """Twenty-two texts joined: past the top 20 by score, each is held whole
    and searched, so ``TEXTS`` names all of them, as a search of every List
    text does."""
    ids = [
        "MIT",
        "ISC",
        "0BSD",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Zlib",
        "BSL-1.0",
        "PostgreSQL",
        "NCSA",
        "Unlicense",
        "WTFPL",
        "X11",
        "BSD-2-Clause-Patent",
        "Libpng",
        "AFL-3.0",
        "Artistic-2.0",
        "EPL-2.0",
        "CC0-1.0",
        "BSD-4-Clause",
        "OpenSSL",
        "Python-2.0",
    ]
    text = "\n\n".join(_text(i) for i in ids)
    detector = long_text_detector()
    with detector.db.reading():
        cut = text_candidates(detector.db, text).corpus()
    assert len(cut.entries) > 20
    texts = detector.texts(text)
    assert texts is not None and len(texts) == len(ids)
    assert texts == search_all(detector, text)


def search_all(detector: LicenseDetector, text: str) -> list[str] | None:
    """``texts()`` as a search of every List text gives it."""
    with detector.db.reading():
        found = found_texts(normalize_text(text), text_corpus(detector.db), "")
        if found is None:
            return None
        groups = text_groups(detector.db, found.rows)
    return named_texts(found.rows, "", "auto", groups)


# -- Han and kana ----------------------------------------------------------------


def test_a_japanese_text_narrows_with_no_runner_up_under_the_bar() -> None:
    text = _text("CC-BY-SA-2.1-JP")
    detector = long_text_detector()
    narrow = _candidates(detector.db, text).narrowed
    assert narrow is not None and narrow.group == {"CC-BY-SA-2.1-JP"}
    results = detector.detect(text)
    assert results[0]["expression"] == "CC-BY-SA-2.1-JP"
    assert [r["expression"] for r in results[1:]] == sorted(
        narrow.runner_ups, key=[r["expression"] for r in results].index
    )

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A filter of ``detect()`` does not make a near text the answer once it has
removed the text that fits best (``gramselect.beyond_bar``), through
``detect()`` on the long-text fixtures (every licence of the List with its
text, so the near neighbours are real). The rule on made-up tables:
``test_gramselect``; the text found whole: ``test_whole_text_first``."""
# pylint: disable=missing-function-docstring

import json
from typing import Any

import pytest
from long_text_db import LONG_TEXTS, long_text_detector

pytestmark = pytest.mark.filterwarnings("ignore::licenseid.LicenseIdWarning")


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


MIT = _text("MIT")
# The MIT text with no heading (a heading would name it) and four words of its
# condition changed, as a real file words it: MIT-0, which lacks the
# condition, now scores more than MIT (0.936 to 0.926) but shares fewer of
# the input's grams (132 to 151).
CONDITION = (
    "The above copyright notice and this permission notice shall be included"
    " in all copies or substantial\nportions"
)
REWORDED = MIT.split("\n", 2)[2].replace(
    CONDITION,
    "The above copyright statement and this permission statement must be kept"
    " in all copies or large\nportions",
)
# Forty words of the middle of GPL-2.0-only: AGPL-1.0-only holds them too.
GPL_PART = " ".join(_text("GPL-2.0-only").split()[300:340])


def answers(text: str, **options: Any) -> list[tuple[str, float]]:
    found = long_text_detector().detect(text, **options)
    return [(r["expression"], r["score"]) for r in found]


def test_no_option_is_the_unfiltered_answer() -> None:
    assert answers(MIT) == [
        ("MIT", 1.0),
        ("JSON", 0.9871),
        ("FSL-1.1-MIT", 0.9252),
        ("Xnet", 0.9017),
    ]


def test_excluding_the_text_the_input_is_gives_no_answer() -> None:
    assert not answers(MIT, exclude=["MIT"])


def test_excluding_a_neighbour_that_scores_less_keeps_the_answer() -> None:
    assert answers(MIT, exclude=["MIT-0"]) == answers(MIT)


def test_excluding_a_neighbour_drops_the_texts_that_score_less_than_it() -> None:
    # JSON shares more of MIT than FSL-1.1-MIT does.
    assert answers(MIT, exclude=["JSON"]) == [("MIT", 1.0), ("Xnet", 0.9017)]


def test_excluding_a_short_text_that_scores_more_keeps_the_answer() -> None:
    assert CONDITION in MIT
    assert answers(REWORDED)[0] == ("MIT", 1.0)
    # A bar on the score alone took MIT out with MIT-0: no answer.
    assert answers(REWORDED, exclude=["MIT-0"])[0] == ("MIT", 1.0)


def test_only_common_keeping_the_holder_drops_what_the_removed_one_beats() -> None:
    assert answers(MIT, only_common=True) == [("MIT", 1.0), ("Xnet", 0.9017)]


def test_only_common_removing_the_holder_gives_no_answer() -> None:
    body = _text("JSON").split("\n", 2)[2]
    assert answers(body)[0][0] == "JSON"
    assert not answers(body, only_common=True)


def test_a_tie_with_the_removed_text_stays() -> None:
    both = answers(GPL_PART)
    assert both[:2] == [("AGPL-1.0-only", 1.0), ("GPL-2.0-only", 1.0)]
    # The one excluded and the next score the same: the filter settled it.
    assert answers(GPL_PART, exclude=["AGPL-1.0-only"])[0] == ("GPL-2.0-only", 1.0)
    assert answers(GPL_PART, exclude=["GPL-2.0-only"])[0] == ("AGPL-1.0-only", 1.0)


def test_a_bare_deprecated_id_in_exclude_takes_out_both_twins() -> None:
    kept = answers(GPL_PART, exclude=["GPL-2.0"])
    assert kept == [("AGPL-1.0-only", 1.0), ("AGPL-1.0-or-later", 0.995)]
    twins = ["GPL-2.0-only", "GPL-2.0-or-later"]
    assert kept == answers(GPL_PART, exclude=twins)


def test_every_holder_excluded_gives_no_answer() -> None:
    holders = ["AGPL-1.0-only", "AGPL-1.0-or-later", "GPL-2.0-only", "GPL-2.0-or-later"]
    assert not answers(GPL_PART, exclude=holders)


@pytest.mark.parametrize(
    "options",
    [{}, {"exclude": ["MIT"]}, {"only_common": True}, {"exclude": ["JSON"]}],
    ids=repr,
)
def test_texts_read_no_filter(options: dict[str, Any]) -> None:
    detector = long_text_detector()
    assert detector.texts(MIT) == ["MIT"]
    for result in detector.detect(MIT, **options):
        assert result["texts"] == ["MIT"]

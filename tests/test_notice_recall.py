# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A licence text under a title and long copyright lines is still a Tier 1
candidate, and the answer.

The FTS5 query of 0.9 read the first 20 words, so a notice could fill it,
and a second query on the text without its notices was needed (roadmap item
61). Tier 1 now looks up every word 3-gram of the text
(``licenseid.retrieval``), so the notices are a few grams among many: these
cases, once lost, must stay found.

The database is the long-text fixtures' (every licence of the List, so MIT,
MIT-advertising, Xnet, FSL-1.1-MIT and JSON are near neighbours with their
texts): a database of five rows returns all five whatever the input says, and
a test on it passes without the fix."""
# pylint: disable=missing-function-docstring

import json

import pytest
from long_text_db import LONG_TEXTS, long_text_detector

from licenseid.normalize import normalize_text
from licenseid.retrieval import get_candidates
from licenseid.types import DetectOptions

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
    return [c["license_id"] for c in get_candidates(db, DetectOptions(), text).found]


def test_the_fixture_rows_exist() -> None:
    for license_id in NEIGHBOURS:
        assert (LONG_TEXTS / f"{license_id}.json").exists(), license_id


@pytest.mark.parametrize("text", [MIT_TITLED, MIT_TWO_LINES], ids=["title", "two"])
def test_a_notice_that_fills_the_head_leaves_mit_a_candidate(text: str) -> None:
    # The premise: the notice leaves no word of the licence in the first 20.
    assert "permission" not in normalize_text(text).split()[:20]
    assert _ids(text)[0] == "MIT"


@pytest.mark.parametrize(
    "text", [MIT_TITLED, MIT_TWO_LINES, _mit_body()], ids=["title", "two", "plain"]
)
def test_detect_answers_mit(text: str) -> None:
    top = long_text_detector().detect(text=text)
    assert top[0]["expression"] == "MIT"


# The right licence ranked 26 to 50 in the notice-free FTS5 query of 0.9 when
# two copyright lines head the text. Each of these is such a licence in the
# fixtures' database.
BELOW_25 = ["0BSD", "ISC", "MIT-testregex", "NTP"]


def _fixture_body(name: str) -> str:
    """The text of a fixture without its title line."""
    data = json.loads((LONG_TEXTS / f"{name}.json").read_text(encoding="utf-8"))
    lines = str(data["license_text"]).strip().splitlines()
    return "\n".join(lines[1:])


@pytest.mark.parametrize("name", BELOW_25)
def test_two_copyright_lines_do_not_cost_the_licence_its_candidacy(name: str) -> None:
    assert name in _ids(TWO_LINES + _fixture_body(name))


@pytest.mark.parametrize("name", BELOW_25)
def test_detect_answers_the_licence_under_two_copyright_lines(name: str) -> None:
    top = long_text_detector().detect(text=TWO_LINES + _fixture_body(name))
    assert top[0]["expression"] == name


def test_the_index_still_keeps_notices() -> None:
    assert "2025" in normalize_text("Copyright (c) 2025 Ann\nPermission")

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Each number the user docs state is the one the code keeps (roadmap item
57)."""
# pylint: disable=missing-function-docstring

import pytest
from docs_blocks import DOCS, folded, text_of

from licenseid import candidates as candidates_module
from licenseid import spdx_source
from licenseid.cli import cli
from licenseid.gramselect import GRAM_LIMIT, MARGIN, MOST, NONE_BAR, TOP
from licenseid.identifiers import MAX_PARSE_DEPTH, MAX_PARSE_OPERATORS
from licenseid.markerfloor import MAX_WHOLE_COVERAGE
from licenseid.resolvefirst import MIN_TEXT_WORDS
from licenseid.resolver import MAX_EXPRESSION_CHARS
from licenseid.resolveslash import MAX_JOINED, MAX_OPERANDS
from licenseid.retrieval import MAX_HINTS_WITH_TEXT
from licenseid.textlocate import (
    MAX_GAP_CHARS,
    MIN_SIMILARITY,
    NEAR_SIMILARITY,
    SURE_SIMILARITY,
)
from licenseid.variants import ANSWER_SCORE
from licenseid.wholetexts import MIN_INPUT_WORDS, MIN_WORDS


def _default(command: str, option: str) -> object:
    return next(p.default for p in cli.commands[command].params if p.name == option)


#: A number the prose states, and where the code keeps it: ``(page, phrase
#: with {} for the number, the number)``. A phrase that moves fails here.
NUMBERS = [
    ("how-it-works.md", "A best score under {} gives", NONE_BAR),
    ("how-it-works.md", "scores the first {} texts by score", TOP),
    ("how-it-works.md", "every text within {} of the", MARGIN),
    ("how-it-works.md", "best, at most {} (equal scores", MOST),
    ("how-it-works.md", "Only the first {:,} distinct grams", GRAM_LIMIT),
    (
        "how-it-works.md",
        "similarity of the text and its trimmed span must be {} or more",
        MIN_SIMILARITY,
    ),
    ("how-it-works.md", "misses {} characters", MAX_GAP_CHARS),
    ("how-it-works.md", "(character fit {} or more)", NEAR_SIMILARITY),
    ("how-it-works.md", "at a fit of {} or more", SURE_SIMILARITY),
    ("how-it-works.md", "(coverage up to {})", MAX_WHOLE_COVERAGE),
    ("how-it-works.md", "the first {} of them", candidates_module.FIELD_VALUES_READ),
    (
        "how-it-works.md",
        "the first {} licences that resolve",
        candidates_module.FIELD_LICENSES_KEPT,
    ),
    ("output.md", "(a coverage above {} before the cap)", MAX_WHOLE_COVERAGE),
    ("output.md", "A List text under {} words", MIN_WORDS),
    ("output.md", "when the input has under {} words", MIN_INPUT_WORDS),
    ("cli.md", "matched as text from {} words on", MIN_TEXT_WORDS),
    ("cli.md", "from 0 to 1 (default {})", _default("detect", "threshold")),
    (
        "cli.md",
        "Keep at most this many results (default {})",
        _default("detect", "top"),
    ),
    ("cli.md", "Cached for {} days each", spdx_source.EXPIRY_LICENSES_JSON),
    ("cli.md", "Cached for {} days each", spdx_source.EXPIRY_LATEST_JSON),
    (
        "cli.md",
        "`popularity.csv`: Cached for {} days",
        spdx_source.EXPIRY_POPULARITY_CSV,
    ),
    ("cli.md", "one over {:,} characters", MAX_EXPRESSION_CHARS),
    ("resolve.md", "`too long: <N> characters` (over {:,})", MAX_EXPRESSION_CHARS),
    ("resolve.md", "there are at most {}", MAX_OPERANDS),
    ("resolve.md", "its `OR` form is over {:,} characters", MAX_JOINED),
    ("resolve.md", "`too many operators` (over {})", MAX_PARSE_OPERATORS),
    ("resolve.md", "`too deeply nested` (over {})", MAX_PARSE_DEPTH),
    ("resolve.md", "Under {} words it warns", MIN_TEXT_WORDS),
    ("python-api.md", "The API warns for results scoring {} or more", ANSWER_SCORE),
    ("python-api.md", "for the first {} entries of `hint`", MAX_HINTS_WITH_TEXT),
]


@pytest.mark.parametrize(("page", "phrase", "number"), NUMBERS)
def test_each_number_the_prose_states_is_the_code(
    page: str, phrase: str, number: object
) -> None:
    text = folded(text_of(DOCS / page))
    assert phrase.format(number) in text, (
        f"docs/{page}: {phrase.format('N')!r} with N = {number} not found"
    )

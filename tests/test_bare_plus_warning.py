# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A bare value that is an expression but for a "+" that is no operator
(``MIT++``, ``MIT +``, ``GPL-2.0-only+``, ``(MIT)+``) gets no answer and
says why, as its quoted form (``"MIT++"``) does: ``input: too few words for
text: <reason>``. It had no answer and no warning (tech-debt roadmap,
item 58).

A database of the whole List (``corpus_db``): a negative test on a seeded
database with no text passes whatever the code does."""
# pylint: disable=missing-function-docstring

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.types import DetectOptions

TOO_FEW = "too few words for text"

# Value and the reason resolve() gives for it, which the warning repeats.
BARE = [
    ("MIT++", "qualifier stated twice: MIT++"),
    ("MIT +", "plus after a space: MIT +"),
    ("GPL-2.0-only+", "qualifier stated twice: GPL-2.0-only+"),
    ("(MIT)+", "plus after a bracket: (MIT)+"),
    ("MIT + +", "qualifier stated twice: MIT + +"),
    ("C++", "not found: C++"),  # no licence either: the same statement is true
    ("g++", "not found: g++"),
    ("Notepad++", "not found: Notepad++"),
]
VALUES = [value for value, _ in BARE]

# Thirteen words, the last an "-only" licence with a "+": it is no text to
# match, whatever the count (without the check, Tier 1 answers by text).
LONG = "MIT OR ISC OR Apache-2.0 OR BSD-3-Clause OR 0BSD OR Zlib OR GPL-2.0-only+"


@pytest.mark.parametrize(("value", "reason"), BARE)
def test_a_bare_value_with_a_plus_says_why_it_has_no_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str, reason: str
) -> None:
    assert resolve(value, corpus_db)["reason"] == reason  # the premise
    assert LicenseDetector(corpus_db.location).detect(text=value) == []
    assert given.lines() == f"WARNING: input: {TOO_FEW}: {reason}\n"


def test_a_value_of_ten_words_or_more_gets_no_answer_and_no_warning(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    assert len(LONG.split()) >= 10
    assert LicenseDetector(corpus_db.location).detect(text=LONG) == []
    assert not given.conditions()


# A "+" that is no operator after a long dashed reference: ten words or more
# once normalised, so too_short() lets it through; Tier 1 answered Apache-2.0
# (0.80), TTYP0 and AGPL-1.0-only for them, where resolve() refuses.
LONG_DASHED = [
    "LicenseRef-apache-license-version-2-0-january-2004-http-www-apache-org-licenses +",
    "LicenseRef-the-mit-license-permission-is-hereby-granted-free-of-charge++",
    "MIT WITH AdditionRef-the-gnu-general-public-license-version-two-or-later +",
]


@pytest.mark.parametrize("value", LONG_DASHED, ids=lambda v: v[:30])
def test_a_long_value_with_a_stray_plus_is_no_text_to_match(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    assert len(value.replace("-", " ").split()) >= 10
    assert resolve(value, corpus_db)["expression"] is None
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=value) == []
    assert not given.conditions()  # ten words or more: no warning, as before


def test_the_cli_says_no_to_a_long_value_with_a_stray_plus(
    corpus_db: LicenseDatabase,
) -> None:
    """``--threshold 0.5`` let the 0.80 answer through, exit 0."""
    result = CliRunner().invoke(
        cli,
        ["--db", corpus_db.location, "detect", "--threshold", "0.5", "--text"]
        + [LONG_DASHED[0]],
    )
    assert result.exit_code == 1
    assert result.stdout.split("\t")[0] == "EXPRESSION="


@pytest.mark.parametrize("value", ["MIT", "GPL-2.0-only", "MIT OR ISC", "(MIT)"])
def test_a_value_with_no_stray_plus_is_unchanged(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    assert LicenseDetector(corpus_db.location).detect(text=value)
    assert not given.conditions()


@pytest.mark.parametrize(
    "options",
    [
        DetectOptions(exclude=["MIT"]),
        DetectOptions(hint=["MIT"]),
        DetectOptions(exclude=["MIT"], hint=["MIT"]),
        DetectOptions(variant="as-written"),
        DetectOptions(variant="only"),
        DetectOptions(variant="or-later"),
    ],
    ids=["exclude", "hint", "both", "as-written", "only", "or-later"],
)
@pytest.mark.parametrize("value", ["MIT++", "GPL-2.0-only+", "(MIT)+"])
def test_the_options_change_neither_the_answer_nor_the_warning(
    corpus_db: LicenseDatabase,
    given: GivenWarnings,
    value: str,
    options: DetectOptions,
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=value, **options) == []
    assert TOO_FEW in given.conditions()


@pytest.mark.parametrize(
    "value",
    [
        "SPDX-License-Identifier: MIT++",
        "SPDX-License-Identifier: Foo\nGPL-2.0-only+",
        "SPDX-License-Identifier: Foo\nMIT++",
    ],
)
def test_a_tag_that_was_taken_out_gets_no_warning(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    """What the tag's reader judged is not the input's to explain."""
    assert LicenseDetector(corpus_db.location).detect(text=value) == []
    assert TOO_FEW not in given.conditions()


@pytest.mark.parametrize("command", ["detect", "is-spdx", "is-osi"])
@pytest.mark.parametrize("value", ["MIT++", "GPL-2.0-only+", "(MIT)+"])
def test_the_cli_prints_the_warning_and_no_answer(
    corpus_db: LicenseDatabase, command: str, value: str
) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, command, "--text", value]
    )
    assert result.exit_code == 1
    assert result.stderr.startswith(f"WARNING: input: {TOO_FEW}: ")
    assert result.stdout.split("\t")[0] == "EXPRESSION="  # no licence named

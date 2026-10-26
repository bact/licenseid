# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The readers of the "+" ("or any later version") agree.

One reader, identifiers._RE_PLUS_OPERATOR, decides which "+" is the
operator; strip_plus_operator and Tier 0's version key use it. Two others
read the same grammar in their own way and must agree with it: the
expression tokenizer (is_simple_expression, normalize_identifier), and the
prose shorthand of classify (has_or_later_language, "GPLv2+" in a source
file), which also takes a comma or a full stop after the "+".
"""

import itertools
import time

import pytest

from licenseid.classify import has_or_later_language
from licenseid.identifiers import (
    is_simple_expression,
    normalize_identifier,
    strip_plus_operator,
)
from licenseid.looseid import version_key

FAMILIES = ("GPL", "LGPL", "AGPL", "gpl")
OTHERS = ("Apache", "MIT", "C", "LicenseRef-x")
SPELLINGS = ("-2.0", "2", "v2", "-v2", " v2", " 2", "_2.0", "-2.0.0", "-2.1")
# The text after the version: (suffix, an operator, a prose grant).
SUFFIXES = (
    ("+", True, True),
    ("+)", True, True),  # before a closing bracket (opened before the ID)
    (" +", False, False),  # apart from its version
    ("++", False, False),  # doubled
    ("+x", False, False),  # inside a word
    ("+2", False, False),
    ("+,", False, True),  # prose punctuation: a grant, no operator
    ("+.", False, True),
    ("", False, False),
)


def _operator(text: str) -> bool:
    return strip_plus_operator(text) != text


def _cases() -> list[tuple[str, bool, bool]]:
    cases = []
    for name, spelling, (suffix, operator, prose) in itertools.product(
        FAMILIES + OTHERS, SPELLINGS, SUFFIXES
    ):
        text = name + spelling + suffix
        if suffix == "+)":
            text = "(" + text
        if name.startswith("LicenseRef-") and " " not in spelling:
            operator = False  # a LicenseRef takes no "+"; "v2" after it does
        cases.append((text, operator, prose and name in FAMILIES))
    return cases


@pytest.mark.parametrize(("text", "operator", "grant"), _cases())
def test_the_plus_readers_agree(text: str, operator: bool, grant: bool) -> None:
    """Every family and other ID, in every spelling the version key takes,
    with each kind of "+" after it."""
    assert _operator(text) is operator, "identifiers._RE_PLUS_OPERATOR"
    # Tier 0 spells out exactly the operator, nothing else.
    assert ("or later" in version_key(text)) is operator, "version_key"
    # The prose shorthand reads the GPL family's operator, and prose.
    assert has_or_later_language(text) is grant, "classify shorthand"
    # The tokenizer: one license with a "+" has the operator, and keeps it.
    if is_simple_expression(text):
        assert ("+" in text) is operator, "is_simple_expression"
        normalized = normalize_identifier(text.strip("()"))
        assert ("+" in normalized or "-or-later" in normalized) is operator


@pytest.mark.parametrize(
    ("text", "operator"),
    [
        ("GPL-2.0+ OR MIT", True),
        ("MIT OR GPL-2.0+", True),
        ("(GPL-2.0+ AND MIT)", True),
        ("Apache-2.0+ WITH LLVM-exception", True),
        ("Apache-2.0 WITH LLVM-exception+", False),  # an exception takes none
        ("MIT or+ Apache-2.0", False),  # nor an operator word
        ("C++", False),
        ("+GPL-2.0", False),
        ("+", False),
        ("", False),
    ],
)
def test_the_operator_in_an_expression(text: str, operator: bool) -> None:
    """What strip_plus_operator drops is what the version key spells out."""
    assert _operator(text) is operator
    assert ("or later" in version_key(text)) is operator


@pytest.mark.parametrize(
    "text",
    ["gpl" * 30_000, "gpl v" * 20_000, "gpl 2" * 20_000, "gpl-2.0" * 15_000]
    + ["gpl2+" * 20_000, "gpl 2.0.0.0" * 10_000],
    ids=["family", "family-v", "family-version", "dashed"]
    + ["operators", "long-versions"],
)
def test_the_shorthand_does_not_backtrack(text: str) -> None:
    """The widened shorthand stays linear on long runs of its parts."""
    start = time.monotonic()
    has_or_later_language(text)
    assert time.monotonic() - start < 2.0

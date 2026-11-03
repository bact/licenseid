# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, third round: the judges behind
``tests/test_readers_round3.py``, one by one, and the readers they must
agree with."""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, match
from licenseid.classify import (
    OR_LATER_PHRASE,
    grant_end,
    grant_follows,
    has_or_later_language,
)
from licenseid.identifiers import (
    disambiguate_deprecated_id,
    is_stray_plus,
    leading_expression,
    normalize_identifier,
)
from licenseid.looseid import (
    declared_grant_id_text,
    disambiguate_whole,
    granted_id_text,
)
from licenseid.plusoperator import plus_apart


@pytest.mark.parametrize(
    ("text", "apart"),
    [
        ("MIT+", None),
        ("MIT++", None),  # a second "+" states the qualifier twice
        ("MIT +", "space"),
        ("MIT\t+", "space"),
        ("MIT\u3000+", "space"),  # any white space
        ("(MIT)+", "bracket"),
        ("(MIT) +", "bracket"),
        ("+", None),
        (" +", "space"),
    ],
)
def test_plus_apart(text: str, apart: str | None) -> None:
    assert plus_apart(text, len(text) - 1) == apart


# One judge, three readers: the leaf of match(), the tag and the whole value.
@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("MIT +", "plus after a space: MIT +"),
        ("GPL-2.0-only +", "plus after a space: GPL-2.0-only +"),
        ("(MIT)+", "plus after a bracket: (MIT)+"),
        ("(MIT) +", "plus after a bracket: (MIT) +"),
        ("MIT ++", "qualifier stated twice: MIT ++"),
        ("MIT + +", "qualifier stated twice: MIT + +"),
        ("MIT+", None),
    ],
)
def test_the_plus_readers_agree(
    corpus_db: LicenseDatabase, value: str, reason: str | None
) -> None:
    got = match(value, corpus_db)
    assert got["reason"] == reason
    assert (leading_expression(value) == "") is (reason is not None)
    assert is_stray_plus(value) is (reason is not None)


@pytest.mark.parametrize(
    ("value", "stray"),
    [
        ("MIT +,", True),  # one end mark after it aside
        (" MIT + ", True),
        ("MIT WITH Classpath-exception-2.0 +", True),
        ("LicenseRef-a +", True),
        ("MIT", False),
        ("MIT+", False),
        ("MIT+,", False),
        ("MIT OR Apache-2.0 +", False),  # no simple expression
        ("MIT +, see LICENSE", False),  # prose: matched as text
        ("+", False),
        ("", False),
    ],
)
def test_is_stray_plus(value: str, stray: bool) -> None:
    assert is_stray_plus(value) is stray


def test_is_stray_plus_is_linear() -> None:
    """The tail is scanned once: ``[\\s+]+\\Z`` searched every offset of a
    run of spaces (10 s at 40,000 in a padded first line)."""
    start = time.monotonic()
    assert not is_stray_plus("x" + " " * 40_000 + "x")
    assert not is_stray_plus("x" + " +" * 20_000 + " x")
    assert time.monotonic() - start < 1.0


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("GPL-2.0 only", "GPL-2.0-only"),
        ("GPL-2.0", None),  # no phrase: the caller's fallback
        ("MIT", None),  # no bare deprecated ID
        ("GPL-2.0 or later (GPL-2.0-or-later)", "GPL-2.0-or-later"),
        ("GPL-2.0+, GPL-2.0 or later", "GPL-2.0-or-later"),  # its own
        ("GPL-2.0; or later", ""),  # match() refuses the mark
        ("GPL-2.0: or later", ""),  # which no phrase reads, but the ID
        ("GPL-2.0 // or later", ""),
        ("GPL-3.0, LGPL-2.1 or later", ""),  # another licence before it
        ("LGPL-2.1 or later, GPL-3.0", ""),  # or after it
        ("LGPL-2.1 or later, GPL-3.0+", ""),
        ("LGPL-2.1 or later. GPL-3.0.", ""),
        ("GPL-2.0 or later, see the COPYING file", "GPL-2.0-or-later"),
    ],
)
def test_disambiguate_whole(
    corpus_db: LicenseDatabase, text: str, answer: str | None
) -> None:
    assert disambiguate_whole(text, corpus_db) == answer


@pytest.mark.parametrize(
    ("tail", "rest", "granted"),
    [
        ("GPL-2.0", "; or later", None),
        ("GPL-2.0", ". or later", True),
        ("GPL-2.0", " (or later)", True),
        ("GPL-2.0", ", version 3 or later", False),  # version 3's
        ("GPL-2.0", " (at your option) any later version", True),
        ("MIT", " ora later", False),
        ("MIT", " orany later", False),
    ],
)
def test_grant_follows_judges_the_gap(
    tail: str, rest: str, granted: bool | None
) -> None:
    assert grant_follows(tail, rest) is granted


@pytest.mark.parametrize(
    ("identifier", "normalized"),
    [
        ("StandardML-NJ+", "SMLNJ+"),
        ("standardml-nj+", "SMLNJ+"),
        ("StandardML-NJ", "SMLNJ"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
        ("eCos-2.0+", "eCos-2.0+"),  # deprecated, no successor: as written
    ],
)
def test_a_plus_follows_the_rename(
    corpus_db: LicenseDatabase, identifier: str, normalized: str
) -> None:
    assert normalize_identifier(identifier, corpus_db) == normalized


# "or" is a word: every reader of the phrase, held to one answer.
OR_WORD = {
    "or later": True,
    "or any later version": True,
    "or a later version": True,
    "or (at your option) any later version": True,
    "ora later": False,
    "orany later": False,
    "orany later version": False,
    "or-a later version": True,  # a dash is a gap, as a comma is
}


@pytest.mark.parametrize("phrase", sorted(OR_WORD))
def test_every_or_later_reader_reads_or_as_a_word(phrase: str) -> None:
    reads = OR_WORD[phrase]
    text = f"GPL-2.0 {phrase}"
    assert (OR_LATER_PHRASE.search(text) is not None) is reads
    assert (grant_end(text, len("GPL-2.0 ")) is not None) is reads
    assert has_or_later_language(text) is reads
    assert (disambiguate_deprecated_id(text) == "GPL-2.0-or-later") is reads
    assert (granted_id_text(text) is not None) is reads
    assert (declared_grant_id_text(f"GPL-2.0-only {phrase}") is not None) is reads

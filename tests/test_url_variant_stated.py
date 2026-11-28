# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A licence URL states the variant its path holds, however the path is
written: ``licenses.nuget.org/GPL-2.0%2B`` states ``GPL-2.0+`` as the literal
"+" does, in ``detect()`` (``exact``, ``variant_stated``) as in a tag.

``resolvefirst.is_exact`` said yes for the encoded URL and ``detect()`` said no,
because the evidence of the variant was the URL as written, in which ``%2B``
holds no "+". ``resolveurl.urls_as_ids`` is the one reader that maps a URL to
the ID it names, for a tag's value and for a whole input.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

from typing import Any

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.resolveurl import urls_as_ids
from licenseid.types import Variant

NUGET = "https://licenses.nuget.org/"
ENCODED = NUGET + "GPL-2.0%2B"
VARIANTS: tuple[Variant, ...] = ("auto", "as-written", "only", "or-later")


def _first(db: LicenseDatabase, text: str, variant: Variant = "auto") -> dict[str, Any]:
    found = LicenseDetector(db.location).detect(text, variant=variant)
    assert found, text
    return dict(found[0])


def _cell(
    db: LicenseDatabase, given: GivenWarnings, text: str, variant: Variant
) -> tuple[Any, ...]:
    """The answer, its flags and the warnings it gave; none for no answer (a
    compound URL inside a compound is refused, and is too short for text)."""
    found = LicenseDetector(db.location).detect(text, variant=variant)
    if not found:
        return (None, given.conditions())
    first = found[0]
    return (
        first["expression"],
        first["exact"],
        first["variant_stated"],
        given.conditions(),
    )


@pytest.mark.parametrize("variant", VARIANTS)
def test_an_encoded_plus_is_exact_and_stated(
    corpus_db: LicenseDatabase, given: GivenWarnings, variant: Variant
) -> None:
    first = _first(corpus_db, ENCODED, variant)
    assert first["expression"] == "GPL-2.0-or-later"
    assert first["exact"] is True
    assert first["variant_stated"] is True
    if variant == "only":  # the input states "or later": the option yields
        assert given.conditions() == {"overridden by input"}
    else:
        assert not given.conditions()


@pytest.mark.parametrize(
    "path",
    [
        "GPL-2.0%2B",
        "GPL-2.0%2b",
        "LGPL-2.1%2B",
        "GPL-2.0%2B%20OR%20MIT",
        "(MIT%20OR%20GPL-2.0%2B)",
    ],
)
@pytest.mark.parametrize(
    "wrap",
    [
        "{}",
        "<{}>",
        "MIT OR {}",
        "{} AND MIT",
        # no marker reader takes a WITH of an AdditionRef: the fallback of
        # detector._answer_of reads the value
        "MIT WITH AdditionRef-x AND {}",
        "{} AND MIT WITH AdditionRef-x",
    ],
)
def test_an_encoded_plus_answers_as_the_literal_one(
    corpus_db: LicenseDatabase, given: GivenWarnings, path: str, wrap: str
) -> None:
    encoded = wrap.format(NUGET + path)
    literal = wrap.format(NUGET + path.replace("%2B", "+").replace("%2b", "+"))
    for variant in VARIANTS:
        assert _cell(corpus_db, given, encoded, variant) == _cell(
            corpus_db, given, literal, variant
        ), (encoded, variant)


@pytest.mark.parametrize(
    "value",
    [
        NUGET + "GPL-2.0 OR " + ENCODED,
        ENCODED + " OR " + NUGET + "GPL-2.0",
    ],
)
def test_two_urls_in_either_order_read_the_same(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    """One URL is no prefix of the other's evidence: the order does not
    matter (a text replace of each URL in turn did)."""
    first = _first(corpus_db, value)
    assert first["expression"] == "GPL-2.0 OR GPL-2.0-or-later"
    assert first["exact"] is True  # a bare ID kept is the declaration itself
    assert first["variant_stated"] is False  # the bare GPL-2.0 states none
    assert not given.conditions()


def test_an_end_mark_after_the_url_is_still_a_cut(
    corpus_db: LicenseDatabase,
) -> None:
    """Guard: the variant is stated now, but the value was cut."""
    first = _first(corpus_db, ENCODED + ".")
    assert (first["exact"], first["variant_stated"]) == (False, True)


def test_a_plain_nuget_url_is_unchanged(corpus_db: LicenseDatabase) -> None:
    """Guard: no "+" in the path, nothing stated (as before)."""
    first = _first(corpus_db, NUGET + "GPL-2.0")
    assert first["expression"] == "GPL-2.0"
    assert first["variant_stated"] is False


@pytest.mark.parametrize(
    ("text", "ids"),
    [
        (ENCODED, "GPL-2.0-or-later"),
        ("  " + ENCODED + "  ", "GPL-2.0-or-later"),
        ("MIT OR " + ENCODED, "MIT OR GPL-2.0-or-later"),
        (NUGET + "GPL-2.0 OR " + ENCODED, "GPL-2.0 OR GPL-2.0-or-later"),
        (ENCODED + " OR " + NUGET + "GPL-2.0", "GPL-2.0-or-later OR GPL-2.0"),
        ("  MIT OR ISC  ", "MIT OR ISC"),
        ("MIT   OR   ISC", "MIT   OR   ISC"),  # no URL: only the ends are trimmed
    ],
)
def test_urls_as_ids(corpus_db: LicenseDatabase, text: str, ids: str) -> None:
    assert urls_as_ids(corpus_db, text) == ids

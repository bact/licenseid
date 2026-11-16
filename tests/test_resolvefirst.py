# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect()`` reads a whole input with ``resolve()`` first, and matches no
short refused input as text (``licenseid.resolvefirst``)."""
# pylint: disable=missing-function-docstring

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.resolvefirst import MIN_TEXT_WORDS, as_resolved, too_short
from licenseid.types import RawMatch


def _match(exact: bool = True) -> RawMatch:
    return RawMatch(
        license_id="GPL-2.0-only",
        method="id",
        exact=exact,
        score=1.0,
        similarity=None,
        coverage=None,
        is_spdx=True,
        is_osi_approved=True,
        is_fsf_libre=True,
    )


@pytest.mark.parametrize(
    ("value", "method", "exact"),
    [
        ("MIT", "id", True),
        ("Apache2", "id", False),  # re-spelt by a rule, no list
        ("Apache License, Version 2.0", "name", False),  # prose_form,
        ("Apache License 2.0.", "name", True),  # a name step before the ending
        ("GPL-2.0", "id", True),  # assumed_only: kept, the declaration
    ],
)
def test_the_resolution_decides_method_and_exact(
    corpus_db: LicenseDatabase, value: str, method: str, exact: bool
) -> None:
    (match,) = as_resolved(resolve(value, corpus_db), [_match()])
    assert (match["method"], match["exact"]) == (method, exact)


@pytest.mark.parametrize(
    ("value", "exact"),
    [
        ("MIT OR Apache-2.0", True),
        ("GPL-2.0 AND MIT", True),  # a kept bare ID is the declaration
        ("MIT AND Apache License, Version 2.0", False),  # one operand by a rule
        ("GPL-2.0 AND Apache License, Version 2.0", False),  # not the weakest
        ("GPL2", False),  # a bare ID by a re-spelling rule
        ("gpl-2.0", True),  # only the case differs
        ("GPL-2.0/MIT", True),  # a slash pair of IDs
    ],
)
def test_a_compound_is_exact_when_every_operand_is(
    corpus_db: LicenseDatabase, value: str, exact: bool
) -> None:
    (match,) = as_resolved(resolve(value, corpus_db), [_match()])
    assert match["exact"] is exact


def test_a_decided_match_stays_inexact(corpus_db: LicenseDatabase) -> None:
    (match,) = as_resolved(resolve("MIT", corpus_db), [_match(exact=False)])
    assert match["exact"] is False


_NINE = " ".join(["word"] * (MIN_TEXT_WORDS - 1))


@pytest.mark.parametrize(
    ("text", "whole", "outcome"),
    [
        (_NINE, True, (True, True)),  # (cut, warned)
        (_NINE + " word", True, (False, False)),
        (_NINE, False, (True, False)),  # a tag was taken out
        ("", True, (True, False)),  # nothing left to say it of
    ],
    ids=["short", "long-enough", "tag-taken-out", "empty"],
)
def test_the_cut_and_its_warning(
    corpus_db: LicenseDatabase,
    given: GivenWarnings,
    text: str,
    whole: bool,
    outcome: tuple[bool, bool],
) -> None:
    resolution = resolve("GNU GPL v2", corpus_db)
    assert too_short(resolution, text, whole=whole) is outcome[0]
    expected = "WARNING: input: too few words for text: not found: GNU GPL v2\n"
    assert given.lines() == (expected if outcome[1] else "")


def test_a_resolved_value_is_never_cut(corpus_db: LicenseDatabase) -> None:
    assert too_short(resolve("MIT", corpus_db), "mit", whole=True) is False


@pytest.mark.parametrize(
    ("text", "cut"),
    [
        ("版权所有", False),  # Han: no spaces between its words
        ("クリエイティブ・コモンズ", False),  # katakana alone
        ("すべての権利は 留保される", False),  # kana and Han
        ("を行使する 第7条bに定める期間", False),  # a clause letter among them
        ("木兰宽松许可证 第2版", False),  # a digit is no letter
        ("gpl 第三版", True),  # half Latin: counted by its words
        ("gnu 通用公共许可证 v3", True),
        ("专有 许可证 v2", True),  # 5 in 6: below nine in ten
        ("저작권 보호", True),  # Korean is written with spaces
        ("１２３", True),  # no letter at all
    ],
)
def test_a_text_written_without_spaces_is_not_cut(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str, cut: bool
) -> None:
    resolution = resolve("GNU GPL v2", corpus_db)
    assert too_short(resolution, text, whole=False) is cut
    assert given.lines() == ""


@pytest.mark.parametrize(
    "text",
    [
        "GNU GPL v2",  # was LiLiQ-R-1.1
        "Proprietary",  # was AGPL-1.0-only
        "UNKNOWN",  # was CC0-1.0
    ],
)
def test_a_short_refused_value_has_no_text_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str
) -> None:
    assert LicenseDetector(corpus_db.location).detect(text) == []
    assert (
        given.lines() == f"WARNING: input: too few words for text: not found: {text}\n"
    )


def test_a_short_rest_after_a_tag_is_cut_silently(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    """The tag's reader judged it; what is left is no value of its own."""
    text = "SPDX-License-Identifier: Proprietary\nGNU GPL v2\n"
    assert LicenseDetector(corpus_db.location).detect(text) == []
    assert given.lines() == ""


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        ("MIT OR Apache-2.0", "Apache-2.0 OR MIT"),  # was ECL-2.0, by text
        ("Apache 2+", "Apache-2.0+"),  # was Apache-2.0, the "+" lost
        ("MirOS OR MIT", "MirOS OR MIT"),  # resolve()'s order, not the tag's
        ("MIT WITH AdditionRef-x", "MIT WITH AdditionRef-x"),  # was CC0-1.0
        ("MIT WITH AdditionRef-x OR ISC", "ISC OR MIT WITH AdditionRef-x"),
    ],
)
def test_detect_and_resolve_give_one_expression(
    corpus_db: LicenseDatabase, text: str, expression: str
) -> None:
    assert resolve(text, corpus_db)["expression"] == expression
    found = LicenseDetector(corpus_db.location).detect(text)
    assert [r["expression"] for r in found] == [expression]


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("MIT; Apache 2", "operator not stated: semicolon"),
        ("MIT; Foo", "not an SPDX operator: semicolon"),
        ("Copyright Foo; all rights", "not found: Copyright Foo, all rights"),
    ],
)
def test_a_semicolon_in_the_reason_starts_no_action(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str, detail: str
) -> None:
    """A ";" in the DETAIL would start the ACTION of the warning."""
    assert LicenseDetector(corpus_db.location).detect(text) == []
    assert given.lines() == f"WARNING: input: too few words for text: {detail}\n"


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        ("GPL-3.0 WITH AdditionRef-x", "GPL-3.0-only WITH AdditionRef-x"),
        ("LGPL-2.1 WITH AdditionRef-a", "LGPL-2.1-only WITH AdditionRef-a"),
        (
            "GPL-2.0 WITH AdditionRef-x OR MIT",
            "MIT OR GPL-2.0-only WITH AdditionRef-x",
        ),
    ],
)
def test_a_split_id_before_an_addition_ref_is_decided(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str, expression: str
) -> None:
    """No marker reader takes a ``WITH AdditionRef-*``: the -only guess is
    still made, said and not exact, as for a tag (was the ID as written,
    exact=false and no warning)."""
    (found,) = LicenseDetector(corpus_db.location).detect(text, variant="only")
    assert (found["expression"], found["exact"]) == (expression, False)
    family = text.split("-")[0] + "-" + text.split("-")[1].split()[0]
    assert given.lines() == (
        f"WARNING: input: variant not stated: {family}; using {expression}\n"
    )


@pytest.mark.parametrize(
    "text", ["GPL-2.0+ WITH AdditionRef-x", "GPL-2.0-only WITH AdditionRef-x"]
)
def test_a_stated_grant_before_an_addition_ref_is_kept(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str
) -> None:
    (found,) = LicenseDetector(corpus_db.location).detect(text)
    assert found["exact"] is True
    assert given.lines() == ""


def test_the_decided_warning_of_a_long_value_names_the_family(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    """The DETAIL is the licence family, not the long value."""
    text = "GPL-2.0 OR " + " OR ".join(["MIT"] * 40)
    (found,) = LicenseDetector(corpus_db.location).detect(text, variant="only")
    assert found["expression"] == "GPL-2.0-only OR MIT"
    assert given.lines() == (
        "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only OR MIT\n"
    )

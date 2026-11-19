# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag that lists another licence after an "or later" grant gets no answer
(roadmap item 46); one that goes on with an operator is read as ``resolve()``
reads it.

``SPDX-License-Identifier: GPL-2.0 or later, ISC`` answered ``GPL-2.0-or-later``,
exact, and dropped ISC; ``resolve()`` (so the argument and a field) refuses
it. The tag reader ends its expression at the grant and judged the words
after it only for "or later" itself. A licence of the List listed after the
grant (a reference, an ID by ``looseid.lists_another``) is refused now;
prose after it keeps the reading (``, see COPYING``, ``, the same as Ruby``).
An operator word after the grant (``MIT (or later) AND Apache-2.0``) dropped
the licence or the exception the same way (0.8.4 answered ``MIT+``); the tag
now reads the operator chain as ``resolve()``, the argument and a field do
(``Apache-2.0 AND MIT+``), up to a comment closer or prose
(``grantchain.operator_chain``). An operator in brackets (``GPL-2.0 or later
(AND MIT)``), a mark glued to the end and a second grant then an operator
still get no answer.
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import CHANNELS, answers

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.grantchain import operator_chain
from licenseid.identifiers import leading_expression, qualify_trailing_grant
from licenseid.looseid import lists_after_grant

#: Tags that list another licence after a grant: no answer.
REFUSED = [
    "GPL-2.0 or later, ISC",
    "GPL-2.0 or later; MIT",
    "GPL-2.0 or later / Apache-2.0",
    "GPL-2.0 or later, LicenseRef-x",
    "GPL-2.0 or later, Zlib",
    "GPL-2.0 or later version, ISC",
    "GPL-2.0 or any later version, ISC",
    "(GPL-2.0 or later), ISC",
    "MIT OR GPL-2.0 or later, ISC",
    "GPL-2.0 or later & MIT",
    "LGPLv2 or later, ISC",
    "((GPL-2.0 or later)), ISC",  # the brackets the reader closes are no offset
    # a licence listed after a grant that another grant ends
    "GPL-2.0 or later, GPL-3.0 or later",
    "GPL-2.0 or later, ISC or later",
    "GPL-2.0 or later; LGPL-2.1 or any later version",
]

#: ``value: expression`` of ``resolve()``, the argument and a field, which keep
#: the licence or the exception after the grant: a tag reads it so too.
OPERATOR_AFTER = {
    "MIT (or later) AND Apache-2.0": "Apache-2.0 AND MIT+",
    "GPL-2.0 (or later) OR ISC": "GPL-2.0-or-later OR ISC",
    "GPL-2.0 (or later) AND ISC": "GPL-2.0-or-later AND ISC",
    "GPL-2.0 or any later version OR ISC": "GPL-2.0-or-later OR ISC",
    "GPL-2.0 or-later OR ISC": "GPL-2.0-or-later OR ISC",
    "GPL-2.0 or later version AND ISC": "GPL-2.0-or-later AND ISC",
    "Zlib or any later version OR Apache-2.0": "Apache-2.0 OR Zlib+",
    "GPL-2.0 (or later) WITH Classpath-exception-2.0": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0"
    ),
    "GPL-2.0 or later WITH Classpath-exception-2.0": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0"
    ),
    "MIT or later OR Apache-2.0": "Apache-2.0 OR MIT+",
    "MIT (or later). AND Apache-2.0": "Apache-2.0 AND MIT+",
    "(GPL-2.0 or later) AND MIT": "GPL-2.0-or-later AND MIT",
    "MIT (or later) AND (ISC OR Zlib)": "MIT+ AND (ISC OR Zlib)",
    "MIT (or later) AND GPL-2.0 or later": "GPL-2.0-or-later AND MIT+",
    # a rule re-spells the ID: not exact, as the argument is not
    "GPLv2 (or later) AND MIT": "GPL-2.0-or-later AND MIT",
    # written in resolve()'s order, not the tag reader's ("ISC AND MIT OR ...")
    "LGPL-2.1 or-later OR MIT AND ISC": "LGPL-2.1-or-later OR ISC AND MIT",
}

#: How a tag stands in a file: comment marks and closers round its line.
COMMENTS = [("// ", ""), ("# ", ""), ("/* ", " */"), ("<!-- ", " -->"), ("{# ", " #}")]

#: ``value: expression`` of a tag whose operator chain prose follows: the
#: chain is read, as a tag reads ``MIT OR ISC see COPYING``.
CHAIN_THEN_PROSE = {
    "GPL-2.0 or later OR MIT see COPYING": "GPL-2.0-or-later OR MIT",
    "MIT (or later) AND Apache-2.0 (see NOTICE)": "Apache-2.0 AND MIT+",
}

#: An operator after a grant that the tag refuses: ``resolve()`` refuses the
#: chain (a glued mark, a listing), or it holds a second grant then an
#: operator, which the tag reader does not follow.
CHAIN_REFUSED = [
    "MIT (or later) AND Apache-2.0?",
    "MIT (or later) AND MIT/ISC",
    "MIT (or later) AND Apache-2.0, ISC",
    "MIT (or later) AND",
    "MIT (or later) AND Apache-2.0-",
    "MIT; or later AND Apache-2.0",
    "GPL-2.0-only or later AND MIT",
    "MIT (or later) AND GPL-2.0 or later?",
    "MIT (or later) AND GPL-3.0 or later OR ISC",
    # an "only" after the chain that no reading keeps
    "MIT (or later) AND GPLv2 only",
    "MIT (or later) AND GPL-2.0 only",
    # a grant in brackets the chain is in: "OR ISC" would be dropped
    "(GPL-2.0 or later AND MIT) OR ISC",
]

#: An operator in brackets after a grant: no answer, as the bare operator.
BRACKETED_OPERATOR = [
    "GPL-2.0 or later (AND MIT)",
    "GPL-2.0 or later (WITH Linux-syscall-note)",
    "GPL-2.0 or later [OR MIT]",
    "GPL-2.0 or later (and MIT)",
    "GPL-2.0 or later ( OR ISC)",
    "GPL-2.0 or any later version (AND MIT)",
    "(GPL-2.0 or later) (AND MIT)",
]

#: ``value: expression`` read after a grant: prose, a number, a comment closer.
KEPT = {
    "GPL-2.0 or later, the same as Ruby": "GPL-2.0-or-later",
    "GPL-2.0 or later, see COPYING": "GPL-2.0-or-later",
    "GPL-2.0 or later (see COPYING)": "GPL-2.0-or-later",
    "GPL-2.0 or later (MIT)": "GPL-2.0-or-later",
    "GPL-2.0 or later (Andrew)": "GPL-2.0-or-later",  # a word that starts "and"
    "GPL-2.0 or later (ORACLE)": "GPL-2.0-or-later",  # ... or "or"
    "GPL-2.0 or later, 2009": "GPL-2.0-or-later",
    "GPL-2.0 or later, Intel Corporation": "GPL-2.0-or-later",
    "MIT OR GPL-2.0 or later, see COPYING": "GPL-2.0-or-later OR MIT",
    "MIT AND GPL-2.0 or later, see LICENSE": "GPL-2.0-or-later AND MIT",
    "GPL-2.0 or later -->": "GPL-2.0-or-later",
    "GPL-2.0 or later */": "GPL-2.0-or-later",
    "MIT or later": "MIT+",
    "GPL-2.0 or later": "GPL-2.0-or-later",
    "GPL-2.0 or later version.": "GPL-2.0-or-later",
    "LGPL-2.1 or later */": "LGPL-2.1-or-later",
    "GPL-2.0+ OR MIT": "GPL-2.0-or-later OR MIT",
    "MIT OR GPL-2.0 or later": "GPL-2.0-or-later OR MIT",
    "GPL-2.0 or later.": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", REFUSED, ids=lambda v: v[:34])
def test_a_tag_that_lists_a_licence_after_a_grant_gets_no_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


@pytest.mark.parametrize("value", sorted(KEPT), ids=lambda v: v[:34])
def test_prose_after_a_grant_keeps_the_reading_of_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    top = answers(corpus_db, value)["tag"]
    assert top is not None
    assert top[0] == KEPT[value]


@pytest.mark.parametrize("value", sorted(OPERATOR_AFTER), ids=lambda v: v[:34])
def test_a_tag_reads_an_operator_after_a_grant_as_resolve_does(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The tag read the first licence and dropped the rest (0.8.4), then gave
    no answer; every channel now reads the whole expression, alike."""
    got = answers(corpus_db, value)
    assert resolve(value, corpus_db)["expression"] == OPERATOR_AFTER[value]
    assert got["argument"] is not None
    assert got["argument"][0] == OPERATOR_AFTER[value]
    assert got["tag"] == got["argument"]
    assert got["field"] == got["argument"]


@pytest.mark.parametrize("comment", COMMENTS, ids=lambda c: c[0].strip())
@pytest.mark.parametrize("value", sorted(OPERATOR_AFTER)[:4], ids=lambda v: v[:34])
def test_a_comment_round_the_tag_leaves_the_reading_of_its_chain(
    corpus_db: LicenseDatabase, value: str, comment: tuple[str, str]
) -> None:
    text = f"{comment[0]}SPDX-License-Identifier: {value}{comment[1]}\nint x;\n"
    found = LicenseDetector(corpus_db.location).detect(text=text)[:1]
    assert [(d["expression"], d["method"]) for d in found] == [
        (OPERATOR_AFTER[value], "tag")
    ]


@pytest.mark.parametrize("value", sorted(CHAIN_THEN_PROSE), ids=lambda v: v[:34])
def test_prose_after_the_chain_of_a_tag_keeps_its_reading(
    corpus_db: LicenseDatabase, value: str
) -> None:
    top = answers(corpus_db, value)["tag"]
    assert top is not None
    assert top[0] == CHAIN_THEN_PROSE[value]


@pytest.mark.parametrize("value", CHAIN_REFUSED, ids=lambda v: v[:34])
def test_a_tag_refuses_a_chain_after_a_grant_that_it_cannot_read_whole(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


@pytest.mark.parametrize(
    ("value", "head"),
    [
        ("MIT (or later) AND Apache-2.0 */", "MIT (or later) AND Apache-2.0"),
        ("MIT or later OR ISC see COPYING", "MIT or later OR ISC"),
        (
            "MIT (or later) AND GPL-2.0 or later -->",
            "MIT (or later) AND GPL-2.0 or later",
        ),
        ("MIT (or later) AND Apache-2.0? */", "MIT (or later) AND Apache-2.0?"),
        ("MIT (or later). AND ISC", "MIT (or later). AND ISC"),
        ("MIT (or later) (AND ISC)", None),
        ("MIT (or later) AND GPLv2 only */", None),
        ("GPL-2.0+ or later AND MIT", None),  # no grant was applied
        ("MIT (or later) AND GPL-2.0 or later OR ISC", None),
        ("MIT (or later), ISC", None),
        ("MIT or later", None),
        ("MIT AND ISC", None),
    ],
)
def test_operator_chain_is_the_head_resolve_reads(
    corpus_db: LicenseDatabase, value: str, head: str | None
) -> None:
    leading = leading_expression(value)
    granted = qualify_trailing_grant(leading, value)
    assert operator_chain(corpus_db, leading, granted, value) == head


@pytest.mark.parametrize("value", BRACKETED_OPERATOR, ids=lambda v: v[:34])
def test_a_tag_gets_no_answer_for_an_operator_in_brackets_after_a_grant(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


def test_every_channel_refuses_a_licence_listed_after_a_grant(
    corpus_db: LicenseDatabase,
) -> None:
    """The argument refused it already; a field and a tag refuse it now."""
    got = answers(corpus_db, "GPL-2.0 or later, ISC")
    assert got == {"argument": None, "tag": None, "field": None}


def test_a_field_refuses_a_grant_listed_after_a_grant(
    corpus_db: LicenseDatabase,
) -> None:
    """The argument has no name hit: its best match is a text match under the
    bar of 0.85 (``MPL-1.1`` at 0.45 on this fixture database, ``BUSL-1.1`` at
    0.475 on the full List), so no answer; ``resolve()`` refuses it."""
    got = answers(corpus_db, "GPL-2.0 or later, GPL-3.0 or later")
    assert got["tag"] is None
    assert got["field"] is None


def test_a_tag_after_a_listing_does_not_hide_the_next_tag(
    corpus_db: LicenseDatabase,
) -> None:
    text = CHANNELS["tag"]("GPL-2.0 or later, ISC") + CHANNELS["tag"]("MIT")
    found = LicenseDetector(corpus_db.location).detect(text=text)
    assert [(d["expression"], d["method"]) for d in found][:1] == [("MIT", "tag")]


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        ("GPL-2.0 or later, ISC", ("GPL-2.0", "GPL-2.0-or-later"), True),
        ("GPL-2.0 or later, see COPYING", ("GPL-2.0", "GPL-2.0-or-later"), False),
        ("GPL-2.0 or later, ISC", ("GPL-2.0", "GPL-2.0"), False),  # no grant applied
        ("(GPL-2.0 or later), ISC", ("(GPL-2.0)", "(GPL-2.0-or-later)"), True),
        ("((GPL-2.0 or later)), ISC", ("((GPL-2.0))", "((GPL-2.0-or-later))"), True),
        ("GPL-2.0 or later (AND ISC)", ("GPL-2.0", "GPL-2.0-or-later"), True),
        ("GPL-2.0 or later [ OR ISC]", ("GPL-2.0", "GPL-2.0-or-later"), True),
        ("GPL-2.0 or later (see ISC)", ("GPL-2.0", "GPL-2.0-or-later"), False),
        # An opening bracket moves the operator test only, not the listing's.
        ("GPL-2.0 or later (, ISC)", ("GPL-2.0", "GPL-2.0-or-later"), False),
        ("GPL-2.0 or later [; ISC ]", ("GPL-2.0", "GPL-2.0-or-later"), False),
        ("GPL-2.0 or later (, ISC and more)", ("GPL-2.0", "GPL-2.0-or-later"), False),
        ("GPL-2.0 or later (ISC)", ("GPL-2.0", "GPL-2.0-or-later"), False),
    ],
)
def test_lists_after_grant_starts_at_the_end_of_the_grant(
    corpus_db: LicenseDatabase,
    value: str,
    read: tuple[str, str],
    expected: bool,
) -> None:
    assert lists_after_grant(corpus_db, read[0], read[1], value) is expected

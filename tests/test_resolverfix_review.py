# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The review of task ``resolverfix``: what its first fix left (the
information separators before an end mark, a grant after a qualifier that
does not start at an operator, an ID cut before a script written without
spaces, case folding outside ASCII, operand and value reasons, one end mark
after a bracket or a name, quote marks around nothing before a mark, a
grant after a reference).

The tables were pinned first (with ``# BUG:`` marks) and flipped by the fix;
an entry marked "Recorded, not moved" is a known gap left as it is."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import re
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from spdx_tag_helpers import Answers, answers, tag_db

from licenseid import (
    LicenseDatabase,
    LicenseDetector,
    exprcanon,
    exprtokens,
    plusoperator,
    resolve,
    resolveprose,
)
from licenseid.dropguard import ends_in_mark, ends_in_ref, marks_at_end, trim_end_mark
from licenseid.identifiers import is_qualified_plus, leading_expression
from licenseid.resolvertypes import Resolution

Answer = tuple[str | None, str, list[str], str | None]
NOTHING = Answers(None, None, None, False)


def answer(got: Resolution) -> Answer:
    steps = [s["kind"] + ("" if s["applied"] else "!") for s in got["steps"]]
    return got["expression"], got["category"], steps, got["reason"]


def named(expression: str, spdx: bool = True) -> Answers:
    return Answers(expression, spdx, expression, spdx)


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_resolverfix_review")


def ref(text: str, reason: str) -> Answer:
    return None, "malformed", [], f"{reason}: {text}"


MATCHED: dict[str, Answer] = {
    # 1: an information separator before the end mark after quote marks is
    # refused as it is anywhere else
    '"MIT"\x1c.': (None, "unresolved", [], "control or format character: U+001C"),
    '"MIT" \x1d ;': (None, "unresolved", [], "control or format character: U+001D"),
    '"MIT"\x1f,': (None, "unresolved", [], "control or format character: U+001F"),
    '"MIT"\x1c\x1c.': (None, "unresolved", [], "control or format character: U+001C"),
    # at the end it is left off (`hiddenchars`, 0.8.1), then the quotes
    '"MIT"\x1e': ("MIT", "separator", ["trim", "unquote"], None),
    # 4: case folded in ASCII only: no letter outside it is an "i", "s", "k"
    "LicenseRef-\u017f": (None, "unresolved", [], "not found: LicenseRef-\u017f"),
    "LicenseRef-\u0131": (None, "unresolved", [], "not found: LicenseRef-\u0131"),
    "L\u0130CENSEREF-a": (None, "unresolved", [], "not found: L\u0130CENSEREF-a"),
    "licen\u017feref-a": (None, "unresolved", [], "not found: licen\u017feref-a"),
    "LICENSEREF-a": ("LicenseRef-a", "lexical", ["id_case"], None),
    # 5: the value says what its operand says
    "LicenseRef-a+- AND MIT": ref("LicenseRef-a+", "qualifier on a reference"),
    "MIT++- AND MIT": ref("MIT++", "qualifier stated twice"),
    "LicenseRef-a+ AND MIT": ref("LicenseRef-a+", "qualifier on a reference"),
    "LicenseRef-a+. AND MIT": ref("LicenseRef-a+", "qualifier on a reference"),
    "LicenseRef-a+; AND MIT": ref("LicenseRef-a+", "qualifier on a reference"),
    "MIT++. AND ISC": ref("MIT++", "qualifier stated twice"),
    "LicenseRef-a+.": ref("LicenseRef-a+", "qualifier on a reference"),
    # 6: one end mark after a bracket, a trove name or path, a name
    "(MIT).": ("MIT", "separator", ["separator", "brackets"], None),
    "[MIT].": ("MIT", "separator", ["separator", "brackets"], None),
    "(MIT),": ("MIT", "separator", ["separator", "brackets"], None),
    "(MIT) .": ("MIT", "separator", ["separator", "brackets"], None),
    "((MIT)).": ("MIT", "separator", ["separator", "brackets"], None),
    "(GPLv3).": (
        "GPL-3.0",
        "assumed_only",
        ["separator", "brackets", "separator", "version_spelling"],
        None,
    ),
    "Apache License 2.0.": (
        "Apache-2.0",
        "separator",
        ["separator", "listed_name"],
        None,
    ),
    "Apache License 2.0;": (
        "Apache-2.0",
        "separator",
        ["separator", "listed_name"],
        None,
    ),
    "MIT License (MIT).": (
        "MIT",
        "separator",
        ["separator", "trailing_name", "listed_name"],
        None,
    ),
    "ISC License (ISCL).": ("ISC", "trove_name", ["separator", "trove_name"], None),
    "The Unlicense.": ("Unlicense", "separator", ["separator", "listed_name"], None),
    "(MIT);": ("MIT", "separator", ["separator", "brackets"], None),
    "License :: OSI Approved :: MIT License.": (
        "MIT",
        "separator",
        ["separator", "trove_path", "listed_name"],
        None,
    ),
    "(MIT AND ISC).": (
        "ISC AND MIT",
        "separator",
        ["separator", "brackets", "reorder"],
        None,
    ),
    " (MIT).": ("MIT", "separator", ["trim", "separator", "brackets"], None),
    "(LicenseRef-a.).": ("LicenseRef-a.", "separator", ["separator", "brackets"], None),
    # two marks, or a mark inside the brackets too: no ending
    "(MIT)..": (None, "unresolved", ["drop!"], "character dropped: U+002E"),
    "(MIT.).": (None, "unresolved", ["drop!"], "character dropped: U+002E"),
    '("MIT.").': (None, "unresolved", ["drop!"], "character dropped: U+002E"),
    "(MIT:).": (None, "unresolved", ["drop!"], "character dropped: U+003A U+002E"),
    "(MIT)?": (None, "unresolved", ["drop!"], "character dropped: U+003F"),
    "(MIT foo).": (None, "unresolved", [], "not found: (MIT foo)."),
    "MIT, ISC.": (None, "unresolved", [], "not found: MIT, ISC."),
    # 9: a reference takes no grant, whatever it ends in
    "LicenseRef-x-only or later": (
        None,
        "malformed",  # fixr item 5
        [],
        "qualifier on a reference: LicenseRef-x-only or later",
    ),
    "LicenseRef-x-or-later or any later version": (
        None,
        "malformed",  # fixr item 5
        [],
        "qualifier on a reference: LicenseRef-x-or-later or any later version",
    ),
    "LicenseRef-a or later": (
        None,
        "malformed",  # fixr item 5
        [],
        "qualifier on a reference: LicenseRef-a or later",
    ),
    # Only a malformed core is the value's reason; another refusal of it
    # is not (the "-" would go unnamed): the general reason
    "MIT;;+-": (None, "unresolved", [], "not found: MIT;;+-"),
    "MIT++-": ref("MIT++", "qualifier stated twice"),
    # Task readers: the comma is an ending, so the grant is the
    # reference's (was the general reason, "not found")
    "LicenseRef-a, or any later version": (
        None,
        "malformed",  # fixr item 5
        [],
        "qualifier on a reference: LicenseRef-a, or any later version",
    ),
    # 11: quote marks around nothing, then a mark
    '"".': (None, "unresolved", [], "empty"),
    '"";': (None, "unresolved", [], "empty"),
    '""+': (None, "unresolved", [], "empty"),
    '"" .': (None, "unresolved", [], "empty"),
    '"".;': (None, "unresolved", [], 'not found: "".;'),
    '""++': (None, "unresolved", [], 'not found: ""++'),
    '"+"': (None, "unresolved", [], "not found: +"),
    # Task readers: the marks around an operator alone are the operands'
    # (they paired as two layers around "OR": "not found: OR")
    '"" OR ""': (None, "unresolved", [], 'operand not resolved: ""'),
}


@pytest.mark.parametrize("value", list(MATCHED), ids=ascii)
def test_resolve(corpus_db: LicenseDatabase, value: str) -> None:
    assert answer(resolve(value, corpus_db)) == MATCHED[value]


TAGS: dict[str, Answers] = {
    # 2: a grant after a stated qualifier, not at an operator
    "GPL-2.0-only, or any later version": NOTHING,
    "GPL-2.0-only (or later)": NOTHING,
    "GPL-2.0-only or-later": NOTHING,
    "GPL-2.0-only. Or any later version": NOTHING,
    "GPL-2.0-only; or any later version": NOTHING,
    "GPL-2.0-or-later, or any later version": NOTHING,
    "GPL-2.0-only, see COPYING for any later version": NOTHING,
    "GPL-2.0-only WITH Classpath-exception-2.0, or any later version": NOTHING,
    "GPL-2.0, see COPYING for any later version": named("GPL-2.0-or-later"),
    "GPL-2.0-only, see COPYING": named("GPL-2.0-only"),
    # Task readers: the grant is MIT's, its "+" (P35), as resolve() reads it;
    # it was dropped in silence
    "GPL-2.0-only OR MIT, or any later version": named("GPL-2.0-only OR MIT+"),
    # 3: a script written without spaces after the ID starts a word
    "MIT\u8bb8\u53ef\u8bc1": named("MIT"),
    "Apache-2.0\u30e9\u30a4\u30bb\u30f3\u30b9": named("Apache-2.0"),
    "GPL-2.0-or-later\u3067\u3059": named("GPL-2.0-or-later"),
    "MIT\ub77c\uc774\uc120\uc2a4": named("MIT"),
    "MIT\u0e44\u0e17\u0e22": named("MIT"),
    "MIT\u00e9": NOTHING,
    "MIT\u0430": NOTHING,  # a Cyrillic letter, which looks like "a"
    # 8: a grant past the window of the probe
    "GPL-2.0-only or" + " " * 195 + "later": NOTHING,
    "GPL-2.0-only or" + " " * 1000 + "later": NOTHING,
    # 9: a reference takes no grant
    "LicenseRef-a or later": NOTHING,
    "LicenseRef-1 or later": NOTHING,
    "(LicenseRef-1) or later": NOTHING,
    "MIT OR LicenseRef-a or later": NOTHING,
    "LicenseRef-a, or any later version": NOTHING,
    "LicenseRef-x-only or later": NOTHING,
    "(GPL-2.0-only) or-later": NOTHING,  # read on the ID before the ")"
    "(LicenseRef-1) or-later": NOTHING,
    "LicenseRef-a OR MIT, or any later version": named("LicenseRef-a OR MIT+", False),
    # 13: a "+" after a qualifier, then a grant
    "GPL-2.0-only+ or later": NOTHING,
}


@pytest.mark.parametrize("tag", list(TAGS), ids=lambda t: ascii(t)[:40])
def test_tag(db: str, tag: str, tmp_path: Path) -> None:
    assert answers(db, tag, tmp_path) == TAGS[tag]


def test_a_plus_after_a_qualifier_then_a_grant_names_nothing(db: str) -> None:
    """The "+" is read before the grant (``identifiers._qualified``): the
    value is one qualified "+", refused whole, never a candidate."""
    value = "GPL-2.0-only+ or later"
    assert leading_expression(value) == value
    assert is_qualified_plus(value)
    found = LicenseDetector(db).detect(text=value)
    assert [r["expression"] for r in found] == []


@pytest.mark.parametrize(
    "value",
    [
        "LicenseRef-a+- AND MIT AND MIT++-",
        "MIT AND LicenseRef-a+. AND ISC",
        "(MIT++; OR ISC) AND LicenseRef-a+-",
    ],
)
def test_each_operand_says_what_it_says_alone(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A refused operand gives the reason the same text gives alone, and the
    value gives its first refused operand's."""
    got = resolve(value, corpus_db)
    refused = [o for o in got["operands"] if o["expression"] is None]
    assert refused
    for operand in refused:
        alone = resolve(operand["text"], corpus_db)
        assert (operand["category"], operand["reason"]) == (
            alone["category"],
            alone["reason"],
        )
    assert got["reason"] == refused[0]["reason"]


@pytest.mark.parametrize(
    ("text", "trimmed"),
    [
        ('"MIT"\x1c.', '"MIT"\x1c'),
        ('"MIT".\x1c', None),
        ("MIT\x1d ;", "MIT\x1d"),
        ("MIT \u3000;\u2028", "MIT"),
        ("LicenseRef-a\x1c.;", None),
        ("LicenseRef-a.;", "LicenseRef-a."),
    ],
    ids=ascii,
)
def test_an_end_mark_is_trimmed_at_white_space_only(
    text: str, trimmed: str | None
) -> None:
    """``trim_end_mark`` runs before ``resolve()``'s gate: an information
    separator (U+001C to U+001F) is no white space to it, so it stays for
    the gate to refuse."""
    assert trim_end_mark(text) == trimmed


@pytest.mark.parametrize(
    ("text", "ref", "mark"),
    [
        ("x\x1cLicenseRef-a.", False, True),
        ("x LicenseRef-a.", True, False),
        ("x\u3000LicenseRef-a.", True, False),
        ("LicenseRef-a.\x1c", False, False),
        ("MIT;\x1c", False, False),
        ("MIT; \u2029)", False, True),
    ],
    ids=ascii,
)
def test_a_word_ends_at_white_space_only(text: str, ref: bool, mark: bool) -> None:
    assert (ends_in_ref(text), ends_in_mark(text)) == (ref, mark)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"LicenseRef-a.;".', ('"LicenseRef-a."', ";.")),
        ("(LicenseRef-a.-;", ("(LicenseRef-a.-", ";")),
        ("x (LicenseRef-a.-;", ("x (LicenseRef-a.-", ";")),
        ("LicenseRef-a. .;", ("LicenseRef-a. ", ".;")),
        ("LicenseRef-a .;", ("LicenseRef-a ", ".;")),
        ("LicenseRef-;", ("LicenseRef", "-;")),
        ("LicenseRef--;", ("LicenseRef--", ";")),
        ("AdditionRef-x-;", ("AdditionRef-x-", ";")),
        ("DocumentRef-a.-;", ("DocumentRef-a", ".-;")),
        ("DocumentRef-a.:LicenseRef-b.;", ("DocumentRef-a.:LicenseRef-b.", ";")),
        ("MIT-.", ("MIT", "-.")),
    ],
    ids=ascii,
)
def test_the_marks_at_the_end(text: str, expected: tuple[str, str]) -> None:
    assert marks_at_end(text) == expected


@pytest.mark.parametrize(
    "text",
    ["MIT" + "-" * 50000, "LicenseRef-a" + "-" * 50000 + ";", "x " + "- " * 25000],
    ids=["dashes", "ref-dashes", "spaced"],
)
def test_the_marks_at_the_end_are_read_in_linear_time(text: str) -> None:
    """Each word is read for a reference once, not once per dash (1.2 s at
    50,000 before)."""
    start = time.monotonic()
    marks_at_end(text)
    assert time.monotonic() - start < 0.5


@pytest.mark.parametrize(
    ("value", "spans"),
    [
        ("(MIT).", [[1, 4]]),
        (" (MIT).", [[2, 5]]),
        ("((MIT AND ISC)).", [[2, 5], [10, 13]]),
    ],
)
def test_an_ending_keeps_the_spans(
    corpus_db: LicenseDatabase, value: str, spans: list[list[int]]
) -> None:
    got = resolve(value, corpus_db)
    assert [operand["span"] for operand in got["operands"]] == spans
    for operand in got["operands"]:
        start, end = operand["span"]
        assert value[start:end] == operand["text"]


@pytest.mark.parametrize(
    "pattern",
    [
        exprtokens.RE_OPERATOR,
        exprtokens.RE_TOKEN,
        exprtokens._RE_WHOLE_LICENSE_REF,  # pylint: disable=protected-access
        exprtokens._RE_WHOLE_ADDITION_REF,  # pylint: disable=protected-access
        plusoperator.LICENSE_REF_PREFIX,
        exprcanon._RE_PART,  # pylint: disable=protected-access
        resolveprose._RE_VERSION_TAIL,  # pylint: disable=protected-access
    ],
    ids=lambda pattern: pattern.pattern[:30],
)
def test_case_is_ignored_in_ascii_only(pattern: re.Pattern[str]) -> None:
    """An ID, an operator and a reference prefix are ASCII: with IGNORECASE
    alone, "\u0130", "\u0131", "\u017f" and the Kelvin sign would read as
    "i", "s" and "k"."""
    assert pattern.flags & re.IGNORECASE
    assert pattern.flags & re.ASCII


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("MIT W\u0130TH X", ["MIT", "W", "TH", "X"]),
        ("MIT w\u0131th X", ["MIT", "w", "th", "X"]),
        ("\u017f-1", ["1"]),
        ("MIT WITH X", ["MIT", "WITH", "X"]),
    ],
    ids=ascii,
)
def test_a_token_is_ascii(text: str, tokens: list[str]) -> None:
    assert [m[0] for m in exprtokens.RE_TOKEN.finditer(text)] == tokens

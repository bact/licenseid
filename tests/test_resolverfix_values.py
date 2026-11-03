# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Edge values of ``resolve()`` the 0.7.0 review found (task ``resolverfix``,
items 1 to 7): quote marks around nothing, a ``;`` in a reason, an end mark
after a prose form, the case of a ``LicenseRef-`` prefix, the information
separators U+001C to U+001F, a lone surrogate in the result, and marks after
a bracket or a name.

Each table holds the answer as ``(expression, category, steps, reason)``, a
step not applied marked ``!``; an entry marked ``was:`` gave that answer
before the fix (the characterisation pins of the first commit)."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.resolvertypes import Resolution
from licenseid.result import json_line

DASH = "character dropped: U+002D"

Answer = tuple[str | None, str, list[str], str | None]


def answer(got: Resolution) -> Answer:
    """What a test here compares."""
    steps = [s["kind"] + ("" if s["applied"] else "!") for s in got["steps"]]
    return got["expression"], got["category"], steps, got["reason"]


#: Item 1: quote marks around nothing are an empty value (was: not found).
EMPTY_QUOTES: dict[str, Answer] = {
    '""': (None, "unresolved", [], "empty"),
    "''": (None, "unresolved", [], "empty"),
    '" "': (None, "unresolved", [], "empty"),
    '""""': (None, "unresolved", [], "empty"),
    "\u201c\u201d": (None, "unresolved", [], "empty"),
    '("")': (None, "unresolved", [], "empty"),
    "'\"\"'": (None, "unresolved", [], "empty"),
    "  ": (None, "unresolved", [], "empty"),
    # A lone mark pairs with nothing; two kinds pair with each other neither.
    '"': (None, "unresolved", [], 'not found: "'),
    "\"'": (None, "unresolved", [], "not found: \"'"),
}

#: Item 2: a reason keeps the ``;`` the input holds (was: made ``,``).
SEMICOLON_REASONS: dict[str, Answer] = {
    "Foo;Bar baz": (None, "unresolved", [], "not found: Foo;Bar baz"),
    "MIT WITH Foo;x": (None, "unresolved", [], "exception not found: Foo;x"),
    "Foo;Bar baz OR MIT": (
        None,
        "unresolved",
        [],
        "operand not resolved: Foo;Bar baz",
    ),
    "GPL-2.0-only+ ;x": (None, "unresolved", [], "not found: GPL-2.0-only+ ;x"),
    # An end mark after brackets is an ending (review item 6).
    "(MIT);": ("MIT", "separator", ["separator", "brackets"], None),
    # Still one line: white space folded.
    "Foo;\nBar baz": (None, "unresolved", [], "not found: Foo; Bar baz"),
}

#: Item 3: the end mark of a prose form is a ``separator`` step, as for a
#: leaf (was: no step).
PROSE_ENDED: dict[str, Answer] = {
    "MIT License :": ("MIT", "prose_form", ["separator", "prose_form"], None),
    "MIT License;": ("MIT", "prose_form", ["separator", "prose_form"], None),
    "MIT License.": ("MIT", "prose_form", ["separator", "prose_form"], None),
    "MIT License,": ("MIT", "prose_form", ["separator", "prose_form"], None),
    "The MIT License;": (
        "MIT",
        "prose_form",
        ["separator", "prose_form", "listed_name"],
        None,
    ),
    "Apache License, Version 2.0.": (
        "Apache-2.0",
        "prose_form",
        ["separator", "prose_form", "separator"],
        None,
    ),
    "GPL-2.0+ License;": (
        "GPL-2.0-or-later",
        "prose_form",
        ["separator", "prose_form"],
        None,
    ),
    "MIT License": ("MIT", "listed_name", ["listed_name"], None),
    "MIT License;;": (None, "unresolved", ["drop!"], "character dropped: U+003B"),
}

#: Item 4: the prefix of a reference in SPDX's case, an ``id_case`` step
#: (was: as written, ``exact``); the idstring as written.
REF_CASE: dict[str, Answer] = {
    "licenseref-foo": ("LicenseRef-foo", "lexical", ["id_case"], None),
    "LICENSEREF-foo": ("LicenseRef-foo", "lexical", ["id_case"], None),
    "MIT OR licenseref-foo": ("MIT OR LicenseRef-foo", "lexical", ["id_case"], None),
    "MIT WITH additionref-x": (
        "MIT WITH AdditionRef-x",
        "lexical",
        ["id_case"],
        None,
    ),
    "documentref-a:licenseref-b": (
        "DocumentRef-a:LicenseRef-b",
        "lexical",
        ["id_case"],
        None,
    ),
    "DocumentRef-a:licenseref-b": (
        "DocumentRef-a:LicenseRef-b",
        "lexical",
        ["id_case"],
        None,
    ),
    "licenseref-foo;": (
        "LicenseRef-foo",
        "separator",
        ["separator", "id_case"],
        None,
    ),
    "(licenseref-foo)": ("LicenseRef-foo", "lexical", ["brackets", "id_case"], None),
    "licenseref-b OR MIT OR LicenseRef-a": (
        "MIT OR LicenseRef-a OR LicenseRef-b",
        "lexical",
        ["id_case", "reorder"],
        None,
    ),
    "licenseref-foo-": ("LicenseRef-foo-", "lexical", ["id_case"], None),
    # The reason quotes the value as written.
    "licenseref-foo+": (
        None,
        "malformed",
        [],
        "qualifier on a reference: licenseref-foo+",
    ),
    "LicenseRef-foo": ("LicenseRef-foo", "exact", [], None),
    "LicenseRef-FOO": ("LicenseRef-FOO", "exact", [], None),
    "DocumentRef-a:LicenseRef-b": ("DocumentRef-a:LicenseRef-b", "exact", [], None),
    "MIT WITH AdditionRef-x": ("MIT WITH AdditionRef-x", "exact", [], None),
}

#: Item 5: the information separators are control characters, refused
#: (was: white space, read through).
SEPARATORS: dict[str, Answer] = {
    "MIT\x1cAND\x1fApache-2.0": (
        None,
        "unresolved",
        [],
        "control or format character: U+001C",
    ),
    "MIT\x1c": (None, "unresolved", [], "control or format character: U+001C"),
    "\x1dMIT": (None, "unresolved", [], "control or format character: U+001D"),
    "MIT\x1e": (None, "unresolved", [], "control or format character: U+001E"),
    "MIT\x1f": (None, "unresolved", [], "control or format character: U+001F"),
    '"MIT"\x1c': (None, "unresolved", [], "control or format character: U+001C"),
    "MIT \x1c OR ISC": (
        None,
        "unresolved",
        [],
        "control or format character: U+001C",
    ),
    "\x1c": (None, "unresolved", [], "control or format character: U+001C"),
    "(\x1c)": (None, "unresolved", [], "control or format character: U+001C"),
    '"\x1f"': (None, "unresolved", [], "control or format character: U+001F"),
    # White space as Unicode has it stays white space.
    "MIT\x85": ("MIT", "lexical", ["trim"], None),
    "MIT\xa0": ("MIT", "lexical", ["trim"], None),
    "MIT\t": ("MIT", "lexical", ["trim"], None),
    "MIT\x0b": ("MIT", "lexical", ["trim"], None),
    "MIT\u2028": ("MIT", "lexical", ["trim"], None),
    "MIT\u3000OR\u3000ISC": ("ISC OR MIT", "lexical", ["whitespace", "reorder"], None),
}

#: Item 7: marks after a bracket, a trove name or path, or a malformed core
#: (was: ``not found: <value>``).
MARKS_AFTER: dict[str, Answer] = {
    "(MIT)-": (None, "unresolved", ["drop!"], DASH),
    "(MIT+)-": (None, "unresolved", ["drop!"], DASH),
    "GNU General Public License v3 (GPLv3)-": (None, "unresolved", ["drop!"], DASH),
    "License :: OSI Approved :: MIT License-": (None, "unresolved", ["drop!"], DASH),
    "MIT License (MIT)-": (None, "unresolved", ["drop!"], DASH),
    "The MIT License (MIT)-": (None, "unresolved", ["drop!"], DASH),
    "LicenseRef-a+-": (
        None,
        "malformed",
        [],
        "qualifier on a reference: LicenseRef-a+",
    ),
    '"(MIT;)".': (
        None,
        "unresolved",
        ["drop!"],
        "character dropped: U+003B U+002E",
    ),
    '"LicenseRef-a.;".': (
        None,
        "unresolved",
        ["drop!"],
        "character dropped: U+003B U+002E",
    ),
    "(MIT)?": (None, "unresolved", ["drop!"], "character dropped: U+003F"),
    "(MIT)--": (None, "unresolved", ["drop!"], DASH),
    "(MIT)-?": (None, "unresolved", ["drop!"], "character dropped: U+002D U+003F"),
    "[MIT]-": (None, "unresolved", ["drop!"], DASH),
    "(MIT OR ISC)-": (None, "unresolved", ["drop!"], DASH),
    '"LicenseRef-a-"-': (None, "unresolved", ["drop!"], DASH),
    "MIT++-": (None, "malformed", [], "qualifier stated twice: MIT++"),
    "GPL-2.0-only+;": (None, "malformed", [], "qualifier stated twice: GPL-2.0-only+"),
    # One end mark after a bracket is an ending (review item 6); a value
    # whose marks off name nothing still names nothing.
    "(MIT).": ("MIT", "separator", ["separator", "brackets"], None),
    "(Foo)-": (None, "unresolved", [], "not found: (Foo)-"),
    "Foo-": (None, "unresolved", [], "not found: Foo-"),
    "MIT+-": (None, "unresolved", ["drop!"], DASH),
    "LicenseRef-a.-": ("LicenseRef-a.-", "exact", [], None),
}

TABLES = {
    **EMPTY_QUOTES,
    **SEMICOLON_REASONS,
    **PROSE_ENDED,
    **REF_CASE,
    **SEPARATORS,
    **MARKS_AFTER,
}


@pytest.mark.parametrize("value", list(TABLES), ids=ascii)
def test_answer(corpus_db: LicenseDatabase, value: str) -> None:
    assert answer(resolve(value, corpus_db)) == TABLES[value]


@pytest.mark.parametrize("value", list(MARKS_AFTER), ids=ascii)
def test_an_operand_says_what_the_value_says(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The one operand of a refused value carries the value's reason."""
    got = resolve(value, corpus_db)
    if got["reason"] is not None and len(got["operands"]) == 1:
        assert got["operands"][0]["reason"] == got["reason"]
        assert got["operands"][0]["category"] == got["category"]


@pytest.mark.parametrize(
    "value", ["(MIT)-", '"(MIT;)".', "GNU General Public License v3 (GPLv3)-"]
)
def test_a_dropped_mark_names_what_it_stopped(
    corpus_db: LicenseDatabase, value: str
) -> None:
    (drop,) = resolve(value, corpus_db)["steps"]
    assert (drop["kind"], drop["applied"], drop["from"]) == ("drop", False, value)
    assert drop["to"] in ("MIT", "GPL-3.0")


def test_an_empty_operand(corpus_db: LicenseDatabase) -> None:
    operands = resolve('"" OR MIT', corpus_db)["operands"]
    assert [o["reason"] for o in operands] == ["empty", None]


def test_a_long_detail_keeps_its_semicolons_and_is_cut(
    corpus_db: LicenseDatabase,
) -> None:
    reason = resolve("Foo;Bar " + "x" * 80, corpus_db)["reason"]
    assert reason == "not found: Foo;Bar " + "x" * 52 + "..."


#: Item 6: values whose result carried a lone surrogate.
SURROGATES = [
    "\udc80MIT",
    "MIT\ud800",
    '"\udc80"',
    "MIT OR \udc80",
    "\udc80 OR MIT",
    "Foo\udc80;Bar",
    chr(0xD83D) + chr(0xDE00),  # a pair, as two code points of a str
    "MIT WITH \udfff",
    "(\udc80)-",
    "\udc80" * 3000,
    "MIT\x1c\udc80",
]


@pytest.mark.parametrize("value", SURROGATES, ids=lambda v: ascii(v)[:30])
def test_a_lone_surrogate_in_the_result(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] in ("lone surrogate", "too long: 3000 characters")
    shown = "".join("\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else c for c in value)
    assert got["input"] == shown  # was: the raw value, which JCS cannot write
    assert json_line(got)  # was: rfc8785.CanonicalizationError


@pytest.mark.parametrize(
    "value",
    ["MIT", "MIT\ufffd", "(MIT)-", "\U0001f600", "MIT OR Apache-2.0", "\ufffd"],
    ids=ascii,
)
def test_input_is_the_raw_value_without_a_surrogate(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["input"] == value

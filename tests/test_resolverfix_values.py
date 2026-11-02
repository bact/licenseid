# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Edge values of ``match()`` the 0.7.0 review found (task ``resolverfix``,
items 1 to 7): quote marks around nothing, a ``;`` in a reason, an end mark
after a prose form, the case of a ``LicenseRef-`` prefix, the information
separators U+001C to U+001F, a lone surrogate in the result, and marks after
a bracket or a name.

Characterisation first: each table pins today's answer as
``(expression, category, steps, reason)``, a step not applied marked ``!``;
an entry marked ``# BUG:`` is what the fix moves."""
# pylint: disable=missing-function-docstring

import pytest
import rfc8785
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, match
from licenseid.resolvertypes import Resolution
from licenseid.result import json_line

Answer = tuple[str | None, str, list[str], str | None]


def answer(got: Resolution) -> Answer:
    """What a test here compares."""
    steps = [s["kind"] + ("" if s["applied"] else "!") for s in got["steps"]]
    return got["expression"], got["category"], steps, got["reason"]


#: Item 1: quote marks around nothing.
EMPTY_QUOTES: dict[str, Answer] = {
    '""': (None, "unresolved", [], 'not found: ""'),  # BUG: empty
    "''": (None, "unresolved", [], "not found: ''"),  # BUG: empty
    '" "': (None, "unresolved", [], 'not found: " "'),  # BUG: empty
    '""""': (None, "unresolved", [], 'not found: """"'),  # BUG: empty
    "\u201c\u201d": (None, "unresolved", [], "not found: \u201c\u201d"),  # BUG
    '("")': (None, "unresolved", [], 'not found: ""'),  # BUG: empty
    "'\"\"'": (None, "unresolved", [], "not found: '\"\"'"),  # BUG: empty
    '"': (None, "unresolved", [], 'not found: "'),  # one mark: not a pair
}

#: Item 2: a ``;`` the input holds, in a reason.
SEMICOLON_REASONS: dict[str, Answer] = {
    "Foo;Bar baz": (None, "unresolved", [], "not found: Foo,Bar baz"),  # BUG
    "MIT WITH Foo;x": (None, "unresolved", [], "exception not found: Foo,x"),  # BUG
    "Foo;Bar baz OR MIT": (
        None,
        "unresolved",
        [],
        "operand not resolved: Foo,Bar baz",  # BUG
    ),
    "GPL-2.0-only+ ;x": (None, "unresolved", [], "not found: GPL-2.0-only+ ,x"),  # BUG
}

#: Item 3: one end mark after a prose form.
PROSE_ENDED: dict[str, Answer] = {
    "MIT License :": ("MIT", "prose_form", ["prose_form"], None),  # BUG
    "MIT License;": ("MIT", "prose_form", ["prose_form"], None),  # BUG
    "MIT License.": ("MIT", "prose_form", ["prose_form"], None),  # BUG
    "MIT License,": ("MIT", "prose_form", ["prose_form"], None),  # BUG
    "The MIT License;": (
        "MIT",
        "prose_form",
        ["prose_form", "listed_name"],  # BUG: no separator
        None,
    ),
    "Apache License, Version 2.0.": (
        "Apache-2.0",
        "prose_form",
        ["prose_form", "separator"],  # BUG: no separator first
        None,
    ),
    "MIT License": ("MIT", "listed_name", ["listed_name"], None),
}

#: Item 4: the prefix of a reference in other case.
REF_CASE: dict[str, Answer] = {
    "licenseref-foo": ("licenseref-foo", "exact", [], None),  # BUG
    "LICENSEREF-foo": ("LICENSEREF-foo", "exact", [], None),  # BUG
    "MIT OR licenseref-foo": ("MIT OR licenseref-foo", "exact", [], None),  # BUG
    "MIT WITH additionref-x": ("MIT WITH additionref-x", "exact", [], None),  # BUG
    "documentref-a:licenseref-b": (
        "documentref-a:licenseref-b",  # BUG
        "exact",
        [],
        None,
    ),
    "licenseref-foo;": ("licenseref-foo", "separator", ["separator"], None),  # BUG
    "(licenseref-foo)": ("licenseref-foo", "lexical", ["brackets"], None),  # BUG
    "LicenseRef-foo": ("LicenseRef-foo", "exact", [], None),
    "LicenseRef-FOO": ("LicenseRef-FOO", "exact", [], None),  # the idstring as written
    "DocumentRef-a:LicenseRef-b": ("DocumentRef-a:LicenseRef-b", "exact", [], None),
}

#: Item 5: the information separators are control characters.
SEPARATORS: dict[str, Answer] = {
    "MIT\x1cAND\x1fApache-2.0": (
        "Apache-2.0 AND MIT",  # BUG
        "lexical",
        ["whitespace", "reorder"],
        None,
    ),
    "MIT\x1c": ("MIT", "lexical", ["trim"], None),  # BUG
    "\x1dMIT": ("MIT", "lexical", ["trim"], None),  # BUG
    "MIT\x1e": ("MIT", "lexical", ["trim"], None),  # BUG
    "MIT\x1f": ("MIT", "lexical", ["trim"], None),  # BUG
    '"MIT"\x1c': ("MIT", "lexical", ["trim", "unquote"], None),  # BUG
    "MIT \x1c OR ISC": (
        "ISC OR MIT",
        "lexical",
        ["whitespace", "reorder"],
        None,
    ),  # BUG
    "\x1c": (None, "unresolved", [], "empty"),  # BUG
    # White space as Unicode has it stays white space.
    "MIT\x85": ("MIT", "lexical", ["trim"], None),
    "MIT\xa0": ("MIT", "lexical", ["trim"], None),
    "MIT\t": ("MIT", "lexical", ["trim"], None),
    "MIT\x0b": ("MIT", "lexical", ["trim"], None),
    "MIT\u2028": ("MIT", "lexical", ["trim"], None),
}

#: Item 7: marks after a bracket, a trove name or path, or a malformed core.
MARKS_AFTER: dict[str, Answer] = {
    "(MIT)-": (None, "unresolved", [], "not found: (MIT)-"),  # BUG
    "(MIT+)-": (None, "unresolved", [], "not found: (MIT+)-"),  # BUG
    "GNU General Public License v3 (GPLv3)-": (
        None,
        "unresolved",
        [],
        "not found: GNU General Public License v3 (GPLv3)-",  # BUG
    ),
    "License :: OSI Approved :: MIT License-": (
        None,
        "unresolved",
        [],
        "not found: License :: OSI Approved :: MIT License-",  # BUG
    ),
    "MIT License (MIT)-": (None, "unresolved", [], "not found: MIT License (MIT)-"),
    "The MIT License (MIT)-": (
        None,
        "unresolved",
        [],
        "not found: The MIT License (MIT)-",  # BUG
    ),
    "LicenseRef-a+-": (None, "unresolved", [], "not found: LicenseRef-a+-"),  # BUG
    '"(MIT;)".': (None, "unresolved", [], 'not found: "(MIT,)".'),  # BUG
    '"LicenseRef-a.;".': (None, "unresolved", [], 'not found: "LicenseRef-a.,".'),
    "(MIT)?": (None, "unresolved", [], "not found: (MIT)?"),  # BUG
    "MIT++-": (None, "unresolved", [], "not found: MIT++-"),  # BUG
    "GPL-2.0-only+;": (None, "unresolved", [], "not found: GPL-2.0-only+,"),  # BUG
    # Not moved: one end mark after a bracket is not read, and a value whose
    # marks off name nothing still names nothing.
    "(MIT).": (None, "unresolved", [], "not found: (MIT)."),
    "(MIT);": (None, "unresolved", [], "not found: (MIT),"),  # BUG: the ;
    "(Foo)-": (None, "unresolved", [], "not found: (Foo)-"),
    "MIT+-": (None, "unresolved", ["drop!"], "character dropped: U+002D"),
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
    assert answer(match(value, corpus_db)) == TABLES[value]


#: Item 6: values whose result carries a lone surrogate.
SURROGATES = [
    "\udc80MIT",
    "MIT\ud800",
    '"\udc80"',
    "MIT OR \udc80",
    "\udc80 OR MIT",
    "Foo\udc80;Bar",
    chr(0xD83D) + chr(0xDE00),  # a pair, as two code points of a str
    "MIT WITH \udfff",
]


@pytest.mark.parametrize("value", SURROGATES, ids=ascii)
def test_a_lone_surrogate_in_the_result(corpus_db: LicenseDatabase, value: str) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, "lone surrogate")
    assert got["input"] == value  # BUG: raw, so JCS cannot write it
    with pytest.raises(rfc8785.CanonicalizationError):  # BUG
        json_line(got)

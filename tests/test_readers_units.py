# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, second round: the helpers behind the tag answers of
``tests/test_readers_tags.py``, one by one."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.classify import grant_follows
from licenseid.errors import invalid_id_error
from licenseid.exprtokens import continues_word
from licenseid.identifiers import names_only_listed
from licenseid.manifest import toml_license_values


@pytest.mark.parametrize(
    ("expression", "listed"),
    [
        ("MIT", True),
        ("mit OR apache-2.0", True),  # the List folds case
        ("GPL-2.0-or-later WITH Classpath-exception-2.0", True),
        ("LicenseRef-x AND DocumentRef-a:LicenseRef-b", True),
        ("MIT+", True),
        ("(MIT OR ISC) AND Apache-2.0", True),
        ("MIT OR later", False),
        ("MIT OR Apache", False),
        ("Foo-1.0 AND MIT", False),  # any operand, not only the last
        ("MIT WITH Foo-exception", False),
        ("Classpath-exception-2.0", True),  # an exception row is listed too
    ],
)
def test_names_only_listed(
    corpus_db: LicenseDatabase, expression: str, listed: bool
) -> None:
    assert names_only_listed(expression, corpus_db) is listed


@pytest.mark.parametrize(
    ("text", "end", "goes_on"),
    [
        ("or later", 8, False),  # the end of the text
        ("or later version", 8, False),  # a space ends a word
        ("or later-1.0", 8, True),
        ("or laterX", 8, True),
        ("or later)", 8, False),
        ("or lateré", 8, True),  # a letter in any script
        ("or later2", 8, True),
    ],
)
def test_continues_word(text: str, end: int, goes_on: bool) -> None:
    assert continues_word(text, end) is goes_on


@pytest.mark.parametrize(
    ("tail", "rest", "granted"),
    [
        ("MIT", " or later", True),
        ("MIT", " OR LATER", True),
        ("MIT", ", or later", True),
        ("MIT", ") or later", True),
        ("MIT", " or latex", False),
        ("MIT", "or later", False),  # "MITor later": no space, no "or"
        ("MIT", " OR Apache-2.0", False),
        ("GPL-2.0", ", 3 or later", False),  # a number: version 3's grant
        ("GPL-2.0", " or any later version", True),
    ],
)
def test_grant_follows_a_bare_or(tail: str, rest: str, granted: bool) -> None:
    assert grant_follows(tail, rest) is granted


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ("a b", "a b"),
        ("\x1f", "U+001F"),
        ("\x1c\x1d\x1c", "U+001C U+001D"),  # each code point once, in order
        ("", '""'),
    ],
    ids=["shown", "one", "several", "empty"],
)
def test_invalid_id_error_never_has_an_empty_detail(value: str, detail: str) -> None:
    assert str(invalid_id_error("--id", value)) == (
        f"option: invalid: --id: {detail}; pass one license ID"
    )


def test_invalid_id_error_cuts_a_long_list_of_code_points() -> None:
    value = "".join(chr(code) for code in range(0x1C, 0x20)) * 20
    detail = str(invalid_id_error("--id", value)).split(": ", 3)[3]
    assert detail == "U+001C U+001D U+001E U+001F; pass one license ID"
    many = "".join(chr(0x2000 + code) for code in range(11))  # white space
    detail = str(invalid_id_error("--id", many)).split(": ", 3)[3]
    assert detail.split(";")[0] == (
        "U+2000 U+2001 U+2002 U+2003 U+2004 U+2005 U+2006 U+2007 U+20..."
    )


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ('license = {text = "MIT"}', ["MIT"]),
        ('LICENSE = {text = "MIT"}', ["MIT"]),
        # U+0130 folds to "i" only under Unicode case rules: no key of TOML's.
        ('lİcense = {text = "MIT"}', []),
        ('licenſe = {text = "MIT"}', []),  # U+017F, long s
    ],
)
def test_a_toml_license_table_key_folds_ascii_only(
    text: str, values: list[str]
) -> None:
    assert toml_license_values(text) == values

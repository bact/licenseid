# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

r"""A TOML basic string is decoded before it is read (``licenseid.manifest``).

The TOML reader skipped every basic string with a backslash in it, and an
inline table's text stopped at its first quote of either kind: a manifest with
``license = "\"MIT\""`` gave no value at all. A basic string now has the
escapes of TOML 1.0 (``\b \t \n \f \r \" \\ \uXXXX \UXXXXXXXX``) undone; any
other escape (``\x41`` and ``\e`` are TOML 1.1), a short ``\u12`` and a code
point that is no scalar value make the string no value, as a TOML parser
refuses the file. A literal string (``'...'``) is never decoded. What the
string decodes to is then read by ``resolve()``.

These tests read text, not a file: a ``tmp_path`` is not needed.
"""
# pylint: disable=missing-function-docstring

import time

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from timing import slack

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.manifest import license_value_groups, toml_license_values

PROJECT = '[project]\nname = "x"\n{line}\n'
POETRY = '[tool.poetry]\nname = "x"\n{line}\n'
CARGO = '[package]\nname = "x"\nedition = "2021"\n{line}\n'

#: ``(line, decoded value)`` of a ``[project]`` table.
DECODED = [
    (r'license = "\"MIT\""', '"MIT"'),
    (r'license = {text = "\"MIT\""}', '"MIT"'),
    (r'license.text = "\"MIT\""', '"MIT"'),
    (r'license = "MIT\u0020"', "MIT "),
    (r'license = "MIT\U00000020"', "MIT "),
    (r'license = "MIT\t"', "MIT\t"),
    (r'license = "MIT\\u0041"', "MIT\\u0041"),  # an escaped backslash, then letters
    (r'license = "MI\u0054"', "MIT"),
    (r'license = "Apache-2.0 \u004fR MIT"', "Apache-2.0 OR MIT"),
    (r'license = "a\b\f\r\n"', "a\b\f\r\n"),
    (r'license = {text = "Apache-2.0 OR \"MIT\""}', 'Apache-2.0 OR "MIT"'),
    (r"license = 'MIT\t'", "MIT\\t"),  # a literal string keeps its backslash
    (r"license = {text = 'MIT\t'}", "MIT\\t"),
    (r'license = "MIT" # a "comment"', "MIT"),
    ('license = "MIT\\u00e9"  # \\"', "MIT\u00e9"),
    ('license = "MIT\\U0001F600"', "MIT\U0001f600"),
]

#: Escapes TOML 1.0 does not have, or a bad code point: no value.
NO_VALUE = [
    r'license = "\x41"',
    r'license = "MIT\e"',
    r'license = "MIT\u12"',
    r'license = "MIT\u12G4"',
    r'license = "MIT\U0000004"',
    r'license = "\ud800MIT"',
    r'license = "MIT\udfff"',
    r'license = "\U00110000"',
    r'license = "MIT\ "',
    r'license = "MIT\z"',
    r'license = {text = "\x41"}',
    r'license = {text = "MIT\u12"}',
]


def _values(template: str, line: str) -> list[str] | None:
    return toml_license_values(template.format(line=line))


@pytest.mark.parametrize(("line", "value"), DECODED, ids=lambda v: ascii(v)[:30])
def test_a_basic_string_is_decoded(line: str, value: str) -> None:
    assert _values(PROJECT, line) == [value]


@pytest.mark.parametrize("template", [POETRY, CARGO], ids=["poetry", "cargo"])
def test_poetry_and_cargo_strings_are_decoded_too(template: str) -> None:
    assert _values(template, r'license = "Apache-2.0 OR \"MIT\""') == [
        'Apache-2.0 OR "MIT"'
    ]


@pytest.mark.parametrize("line", NO_VALUE, ids=lambda v: ascii(v)[:30])
def test_an_escape_toml_1_0_lacks_is_no_value(line: str) -> None:
    assert _values(PROJECT, line) == []


def test_a_later_table_still_gives_a_value_after_a_bad_string() -> None:
    text = '[project]\nname = "x"\nlicense = "\\x41"\n[tool.poetry]\nlicense = "MIT"\n'
    assert toml_license_values(text) == ["MIT"]


def test_the_license_key_only_is_read() -> None:
    assert _values(PROJECT, r'description = "\"MIT\""') == []


@pytest.mark.parametrize(
    ("line", "expression"),
    [
        (r'license = "\"MIT\""', "MIT"),
        (r'license = {text = "\"MIT\""}', "MIT"),
        (r'license = "MIT\u0020"', "MIT"),
        (r'license = "MIT\t"', "MIT"),
        (r'license = "Apache-2.0 OR \"MIT\""', "Apache-2.0 OR MIT"),
        (r"license = 'MIT'", "MIT"),
        (r'license = "MIT"', "MIT"),
    ],
    ids=lambda v: ascii(v)[:30],
)
def test_the_decoded_value_is_read_as_a_field(
    corpus_db: LicenseDatabase, line: str, expression: str
) -> None:
    found = LicenseDetector(corpus_db.location).detect(text=PROJECT.format(line=line))
    assert [(d["expression"], d["method"], d["exact"]) for d in found[:1]] == [
        (expression, "field", True)
    ]


@pytest.mark.parametrize(
    "line",
    [
        r'license = "MIT\\u0041"',  # decodes to a value with a backslash in it
        r"license = 'MIT\t'",  # a literal string: backslash and t
        r'license = "\u0000MIT"',  # decodes to NUL, then MIT
        r'license = "\x41"',
        r'license = "MIT\u12"',
    ],
    ids=lambda v: ascii(v)[:30],
)
def test_a_decoded_value_that_resolve_refuses_gives_no_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings, line: str
) -> None:
    found = LicenseDetector(corpus_db.location).detect(text=PROJECT.format(line=line))
    assert found == []
    assert given.conditions() <= {"too few words for text"}


def test_a_manifest_with_an_escape_is_still_a_manifest() -> None:
    text = PROJECT.format(line=r'license = "\x41"')
    assert license_value_groups(text, ".toml") == [[]]  # a manifest, no value


@pytest.mark.parametrize(
    "line",
    [
        'license = "' + '\\"' * 100_000 + '"',  # an escaped quote, 100,000 times
        'license = "' + "\\\\" * 100_000 + '"',
        'license = "' + "\\" * 200_001,  # an odd run, never closed
        'license = "' + "\\u00" * 50_000 + '"',
        'license = {text = "' + '\\"' * 100_000,  # unclosed table text
        "license = {" + "text = " * 20_000 + '"x"',
    ],
    ids=["quotes", "backslashes", "odd-run", "short-u", "table-open", "many-text"],
)
def test_a_long_string_is_read_in_linear_time(line: str) -> None:
    start = time.monotonic()
    _values(PROJECT, line)
    assert time.monotonic() - start < slack(1.0)

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The ``reason`` of a refused compound (R7 review, S1 and S2): a leaf of
several words that resolves alone is not "not resolved", and a reason holds
one short line whatever the input held.
"""
# pylint: disable=missing-function-docstring

import py_spdx_license
import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, exprcanon, resolve

#: A leaf of several words that ``resolve`` reads alone (S1).
SEVERAL_WORDS = [
    ("BSD 3-Clause OR Apache-2.0", "BSD 3-Clause"),
    ("MIT OR Apache 2.0", "Apache 2.0"),
    ("GPL v2 OR MIT", "GPL v2"),
    ("MIT OR Apache 2.0 or later", "Apache 2.0 or later"),
    ("Apache License 2.0 OR MIT", "Apache License 2.0"),
]


@pytest.mark.parametrize(
    ("value", "leaf"), SEVERAL_WORDS, ids=[v for v, _ in SEVERAL_WORDS]
)
def test_a_leaf_of_several_words_that_resolves_alone(
    corpus_db: LicenseDatabase, value: str, leaf: str
) -> None:
    got = resolve(value, corpus_db)
    assert resolve(leaf, corpus_db)["expression"] is not None
    assert got["expression"] is None
    assert got["reason"] == f"operand of several words: {leaf}"


@pytest.mark.parametrize(
    "value",
    ["Foo\nBar OR MIT", "Foo Bar OR MIT", "Foo\r\nBar OR MIT", "Foo\x85Bar OR MIT"],
    ids=["LF", "U+2028", "CRLF", "NEL"],
)
def test_a_line_break_in_a_leaf_reaches_the_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    reason = resolve(value, corpus_db)["reason"]
    assert reason is not None
    assert reason == "operand not resolved: Foo Bar"


def test_a_long_leaf_reaches_the_reason_whole(corpus_db: LicenseDatabase) -> None:
    got = resolve("x\t" * 800 + "y z AND MIT", corpus_db)
    assert got["reason"] is not None
    assert len(got["reason"]) == len("operand not resolved: ") + 60 + 3
    assert got["reason"].endswith("...")


@pytest.mark.parametrize("size", [61, 1900], ids=["just over", "1900"])
def test_a_reason_is_cut_to_sixty_characters(
    corpus_db: LicenseDatabase, size: int
) -> None:
    """(A value over 2,000 characters is no compound: 1,900 is the long case.)"""
    leaf = "Foo" * (size // 3 + 1)
    reason = resolve(f"{leaf[:size]} OR MIT", corpus_db)["reason"]
    assert reason == f"operand not resolved: {leaf[:60]}..."


def test_a_leaf_of_sixty_characters_is_not_cut(corpus_db: LicenseDatabase) -> None:
    leaf = "Foo" * 20
    reason = resolve(f"{leaf} OR MIT", corpus_db)["reason"]
    assert reason == f"operand not resolved: {leaf}"


def test_a_semicolon_in_a_reason_is_a_comma(corpus_db: LicenseDatabase) -> None:
    """A reason may reach a diagnostic line, where ``;`` starts the ACTION."""
    reason = resolve("Foo bar;baz OR MIT", corpus_db)["reason"]
    assert reason == "operand not resolved: Foo bar,baz"


def test_the_long_several_word_leaf_is_cut_too(corpus_db: LicenseDatabase) -> None:
    value = "Apache License 2.0" + " " * 200 + "OR MIT"
    assert resolve(value, corpus_db)["reason"] == (
        "operand of several words: Apache License 2.0"
    )


def test_the_leaf_in_a_parse_message_is_one_short_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parser's message names a leaf by its placeholder; the text put
    back in its place is folded and cut."""
    placeholder = f"{exprcanon._PLACEHOLDER}0"  # pylint: disable=protected-access

    def refuse(_expression: str, **_options: object) -> None:
        raise ValueError(f"Unexpected '{placeholder}'")

    monkeypatch.setattr(exprcanon, "parse_expression", lambda _text: None)
    monkeypatch.setattr(py_spdx_license, "parse", refuse)
    leaf = "a\u2028b\r\n" + "c" * 200
    tokens = [exprcanon.Token("leaf", 0, len(leaf))]
    got = exprcanon.parse(tokens, [leaf])
    assert got == f"parse failed: Unexpected 'a b {'c' * 56}...'"

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The ``reason`` of a refused compound (R7 review, S1 and S2): a leaf of
several words that resolves alone is not "not resolved", and a reason holds
one short line whatever the input held.
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

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
    # BUG: the leaf resolves alone, so "not resolved" is false
    assert got["reason"] == f"operand not resolved: {leaf}"


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
    # BUG: the reason is one line, whatever the input held
    assert len(reason.splitlines()) == 2


def test_a_long_leaf_reaches_the_reason_whole(corpus_db: LicenseDatabase) -> None:
    got = resolve("x\t" * 800 + "y z AND MIT", corpus_db)
    assert got["reason"] is not None
    # BUG: the reason is cut
    assert len(got["reason"]) > 1000

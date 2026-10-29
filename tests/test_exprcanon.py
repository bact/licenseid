# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.exprcanon``: the cut of a value into leaves, the limits kept
from the parser, and the canonical form, on resolved leaf texts."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.exprcanon import (
    Group,
    canonical,
    leaf_key,
    leaves,
    missing_operator,
    oversize,
    parse,
    split,
    unbracketed,
    written_upper,
)


def _leaves(text: str) -> list[str]:
    return [text[t.start : t.end] for t in leaves(split(text))]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", ["MIT"]),
        ("MIT OR ISC", ["MIT", "ISC"]),
        ("(MIT)OR(ISC)", ["MIT", "ISC"]),
        ("GPL-2.0-or-later OR MIT", ["GPL-2.0-or-later", "MIT"]),
        ("GPL-2.0 or later OR MIT", ["GPL-2.0 or later", "MIT"]),
        ("GPL-2.0 (or later) AND MIT", ["GPL-2.0 (or later)", "MIT"]),
        (
            "MIT OR GPL-2.0 or any later version",
            ["MIT", "GPL-2.0 or any later version"],
        ),
        ("MIT WITH LLVM-exception OR ISC", ["MIT WITH LLVM-exception", "ISC"]),
        ('MIT"OR"ISC', ['MIT"OR"ISC']),
        ("and_mask OR MIT", ["and_mask", "MIT"]),
        ("[MIT OR {ISC}]", ["MIT", "ISC"]),
        ("or later OR MIT", ["later", "MIT"]),  # an "or" after no leaf: an operator
    ],
)
def test_split_cuts_at_operators_and_brackets_only(
    text: str, expected: list[str]
) -> None:
    """An "or" that starts a grant after a leaf is part of the leaf; an
    operator inside a word is no operator."""
    assert _leaves(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(MIT)", "MIT"),
        ("[MIT]", "MIT"),
        ("{[(MIT)]}", "MIT"),
        ("(MIT) OR (ISC)", "(MIT) OR (ISC)"),
        ("[MIT] OR [ISC]", "[MIT] OR [ISC]"),
        ("[MIT)", "[MIT)"),
        ("([MIT)]", "([MIT)]"),
        ("((MIT) OR ISC)", "(MIT) OR ISC"),
        ("( MIT )", " MIT "),
        ("MIT", "MIT"),
        ("", ""),
    ],
)
def test_unbracketed_takes_off_only_pairs_around_the_whole(
    text: str, expected: str
) -> None:
    assert unbracketed(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT OR ISC", None),
        ("[MIT)", "mismatched brackets"),
        ("(MIT OR [ISC)]", "mismatched brackets"),
        ("(" * 151 + "MIT" + ")" * 151, "too deeply nested"),
        ("(" * 150 + "MIT" + ")" * 150, None),
        (" OR ".join(["MIT"] * 152), "too many operators"),
        (" OR ".join(["MIT"] * 151), None),
    ],
    ids=[
        "plain",
        "mismatched",
        "nested-mismatch",
        "deep",
        "at-depth",
        "long",
        "at-cap",
    ],
)
def test_oversize_names_what_the_parser_is_not_given(
    text: str, expected: str | None
) -> None:
    assert oversize(split(text)) == expected


@pytest.mark.parametrize(
    ("text", "upper"),
    [("MIT OR ISC", True), ("MIT or ISC", False), ("MIT AND ISC Or 0BSD", False)],
)
def test_written_upper_reads_the_operators_as_written(text: str, upper: bool) -> None:
    assert written_upper(text, split(text)) is upper


@pytest.mark.parametrize(
    ("text", "missing"),
    [("BSD (3-clause)", True), ("(MIT) (ISC)", True), ("MIT OR (ISC)", False)],
)
def test_missing_operator_finds_two_operands_side_by_side(
    text: str, missing: bool
) -> None:
    assert missing_operator(split(text)) is missing


def test_parse_gives_the_tree_or_the_parser_message() -> None:
    tokens = split("MIT OR (ISC AND 0BSD)")
    assert parse(tokens, ["MIT", "ISC", "0BSD"]) == Group(
        "OR", (0, Group("AND", (1, 2)))
    )
    assert parse(split("MIT AND"), ["MIT"]) == "parse failed: Unexpected 'AND'"


def test_leaves_sort_ids_then_references_then_with() -> None:
    texts = ["MIT WITH X", "LicenseRef-a", "isc", "DocumentRef-d:LicenseRef-b", "0BSD"]
    assert sorted(texts, key=leaf_key) == [
        "0BSD",
        "isc",
        "DocumentRef-d:LicenseRef-b",
        "LicenseRef-a",
        "MIT WITH X",
    ]


def _canonical(text: str, texts: list[str]) -> tuple[str, list[str]]:
    tokens = split(text)
    tree = parse(tokens, texts)
    assert not isinstance(tree, str)
    expression, steps = canonical(text, tokens, tree, texts)
    return expression, [s["kind"] for s in steps]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ISC OR MIT", ("ISC OR MIT", [])),
        ("MIT or ISC", ("ISC OR MIT", ["operator_case", "reorder"])),
        ("MIT  OR ISC", ("ISC OR MIT", ["whitespace", "reorder"])),
        ("(ISC OR MIT)", ("ISC OR MIT", ["brackets"])),
        ("ISC OR (MIT OR 0BSD)", ("0BSD OR ISC OR MIT", ["brackets", "reorder"])),
        ("MIT AND (ISC OR 0BSD)", ("MIT AND (0BSD OR ISC)", ["reorder"])),
        ("(MIT AND ISC) OR 0BSD", ("0BSD OR ISC AND MIT", ["brackets", "reorder"])),
        ("MIT OR MIT", ("MIT", ["dedupe"])),
        ("(MIT OR ISC) AND (ISC OR MIT)", ("ISC OR MIT", ["reorder", "dedupe"])),
        (  # groups by case-folded text: "miros" before "mit"
            "(MIT OR Zlib) AND (MirOS OR Zlib)",
            ("(MirOS OR Zlib) AND (MIT OR Zlib)", ["reorder"]),
        ),
    ],
)
def test_canonical_form_and_its_steps(
    text: str, expected: tuple[str, list[str]]
) -> None:
    """Operators in upper case, single spaces, a chain flattened, operands
    sorted with groups last, duplicates dropped, brackets only for an OR
    inside an AND; one step for each change, in that order."""
    texts = [text[t.start : t.end] for t in leaves(split(text))]
    assert _canonical(text, texts) == expected

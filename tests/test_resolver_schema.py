# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The schema-2 result of ``resolve()`` (task T7): ``schema``, ``operands``,
``components`` and ``Step.by``, for a value that names one licence."""

import json

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.resolvertypes import Resolution


def _keys(result: Resolution) -> list[str]:
    return list(result)


def test_the_result_names_its_schema_and_keeps_its_key_order(
    corpus_db: LicenseDatabase,
) -> None:
    """Schema 2; the keys in a fixed order, which JSON output keeps."""
    got = resolve("MIT", corpus_db)
    assert got["schema"] == 2
    assert _keys(got) == [
        "schema",
        "input",
        "expression",
        "category",
        "trust",
        "steps",
        "expansions",
        "candidates",
        "operands",
        "resolver",
        "components",
        "lists",
        "reason",
    ]
    assert json.loads(json.dumps(got)) == got  # plain JSON: lists, not tuples


@pytest.mark.parametrize(
    ("value", "text", "span"),
    [
        ("MIT", "MIT", [0, 3]),
        ("  MIT ", "MIT", [2, 5]),
        ("(MIT)", "MIT", [1, 4]),
        ('"MIT"', "MIT", [1, 4]),
        ('  " MIT "', "MIT", [4, 7]),
        ('("MIT")', "MIT", [2, 5]),
        ('"(MIT)"', "MIT", [2, 5]),
        ('"MIT', "MIT", [1, 4]),
        ("GPLv2 or later", "GPLv2 or later", [0, 14]),
        ("GPL-2.0-only WITH Classpath-exception-2.0", None, [0, 41]),
        ("GPL-2.0-only+", "GPL-2.0-only+", [0, 13]),
        ("( ( MIT ) )", "MIT", [4, 7]),
        ("[MIT]", "MIT", [1, 4]),
        ("{[ MIT ]}", "MIT", [3, 6]),
        (' "[MIT]" ', "MIT", [3, 6]),
        ("Proprietary", "Proprietary", [0, 11]),
    ],
)
def test_a_single_value_is_one_operand_with_its_span_in_the_input(
    corpus_db: LicenseDatabase, value: str, text: str | None, span: list[int]
) -> None:
    """The span is ``[start, end)`` of the raw input, after the trim, the
    quotes and the brackets around the whole; the text is that slice."""
    (operand,) = resolve(value, corpus_db)["operands"]
    assert operand["span"] == span
    assert operand["text"] == value[span[0] : span[1]]
    if text is not None:
        assert operand["text"] == text


def test_an_operand_repeats_the_leaf_and_the_whole_adds_its_own_steps(
    corpus_db: LicenseDatabase,
) -> None:
    """The trim and the brackets are steps of the whole value; the operand
    holds the steps of the leaf alone, so its category can be stronger."""
    got = resolve(" (mit) ", corpus_db)
    (operand,) = got["operands"]
    assert [s["kind"] for s in got["steps"]] == ["trim", "brackets", "id_case"]
    assert [s["kind"] for s in operand["steps"]] == ["id_case"]
    assert (got["category"], operand["category"]) == ("lexical", "lexical")
    quoted = resolve('"MIT', corpus_db)
    assert (quoted["category"], quoted["operands"][0]["category"]) == (
        "separator",
        "exact",
    )


@pytest.mark.parametrize(
    "value",
    ["", "   ", "MIT\x00", "MIT\udcff", "M" * 2001],
    ids=["empty", "blank", "control", "surrogate", "too-long"],
)
def test_a_value_refused_before_it_is_read_has_no_operand(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Empty, a control character, a lone surrogate, over 2,000 characters."""
    assert not resolve(value, corpus_db)["operands"]


@pytest.mark.parametrize(
    "value",
    ["MIT", "Apache2", "GPL-2.0+", "GPL-3.0", "Apache 2.0?", "MIT WITH LLVM-exception"],
)
def test_every_step_says_licenseid_did_it(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """``by`` is ``""`` on every step and expansion, of the whole and of each
    operand: no step of 0.7.0 is another tool's."""
    got = resolve(value, corpus_db)
    steps = got["steps"] + got["expansions"]
    for operand in got["operands"]:
        steps += operand["steps"] + operand["expansions"]
    assert all(s["by"] == "" for s in steps)


@pytest.mark.parametrize(
    "value", ["GPL-2.0-only WITH Classpath-exception-2.0", "[MIT]", "Proprietary"]
)
def test_a_single_value_names_no_component(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The expression parser did not run for one licence."""
    assert not resolve(value, corpus_db)["components"]

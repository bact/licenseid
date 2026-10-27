# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A "+" after an ID that is written short or states its qualifier
(tech-debt roadmap, item 39), and the largest expression the parser is
given (item 19): the same answer from every entry point and every Python."""
# pylint: disable=missing-function-docstring

import sys
from collections.abc import Generator
from unittest import mock

import pytest
from click.testing import CliRunner
from matcher_db import Lic, seeded_db
from resolver_helpers import GPL2, GPL2_PLUS

from licenseid import resolve
from licenseid.cli import cli
from licenseid.identifiers import (
    is_simple_expression,
    normalize_identifier,
    parse_declared,
    parse_expression,
)
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.plusoperator import plus_after_qualifier, strip_plus_operator
from licenseid.versionkey import version_key

ROWS = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
    *GPL2,
    GPL2_PLUS,
)


@pytest.fixture(name="matcher")
def _matcher() -> Generator[AggregatedLicenseMatcher, None, None]:
    for path in seeded_db("test_plus_and_depth", ROWS):
        yield AggregatedLicenseMatcher(path)


def ids(matcher: AggregatedLicenseMatcher, **kwargs: str) -> list[str]:
    return [r["license_id"] for r in matcher.match(**kwargs)]


# value: what match answers for it as text, as a tag, and what resolve gives
PLUS = [
    ("GPL-2+", "GPL-2.0-or-later", "GPL-2.0-or-later"),
    ("gpl2+", "GPL-2.0-or-later", "GPL-2.0-or-later"),
    ("Apache-2+", "Apache-2.0+", "Apache-2.0+"),  # no -or-later ID: the "+" stays
    ("GPL-2.0+", "GPL-2.0-or-later", "GPL-2.0-or-later"),
    ("MIT+", "MIT+", "MIT+"),
    ("MI+", None, None),  # a bare prefix: it was MIT+
    ("GPL-2.0-only+", None, None),  # a qualifier stated twice
    ("GPL-2.0-or-later+", None, None),
    ("gpl-2.0-ONLY+", None, None),
]


@pytest.mark.parametrize(("value", "answer", "resolved"), PLUS)
def test_a_plus_after_an_id_answers_alike_everywhere(
    matcher: AggregatedLicenseMatcher,
    value: str,
    answer: str | None,
    resolved: str | None,
) -> None:
    expected = [answer] if answer else []
    assert ids(matcher, text=value) == expected
    tag = f"/* SPDX-License-Identifier: {value} */"
    assert ids(matcher, text=tag) == expected
    assert resolve(value, matcher.db)["expression"] == resolved


def test_a_plus_after_a_qualifier_voids_the_whole_tag(
    matcher: AggregatedLicenseMatcher,
) -> None:
    """One operand cannot be answered without the grant it states twice."""
    assert ids(matcher, text="SPDX-License-Identifier: GPL-2.0-only+ OR MIT") == []


@pytest.mark.parametrize(
    ("expression", "twice"),
    [
        ("GPL-2.0-only+", True),
        ("MIT OR GPL-2.0-or-later+", True),
        ("(GPL-2.0-ONLY+)", True),
        ("GPL-2.0+", False),
        ("GPL-2.0-only", False),
        ("GPL-2.0-only +", False),  # a detached "+" is no operator
        ("MIT WITH Foo-only+", False),  # an exception takes no "+" anyway
        ("LicenseRef-x-only+", False),  # nor does a LicenseRef
        ("GPL-2.0-onlyx+", False),
    ],
)
def test_plus_after_qualifier(expression: str, twice: bool) -> None:
    assert plus_after_qualifier(expression) is twice
    unparsed = parse_expression(strip_plus_operator(expression)) is None
    assert (parse_declared(expression) is None) is (twice or unparsed)


@pytest.mark.parametrize(
    ("value", "simple"),
    [
        ("GPL-2.0-only+", False),
        ("(gpl-2.0-OR-LATER+)", False),
        ("GPL-2.0-only+ WITH Classpath-exception-2.0", False),
        ("GPL-2.0+", True),
        ("MI+", True),  # shaped as one ID; that it names none is match's answer
        ("GPL-2.0-only", True),
    ],
)
def test_a_plus_after_a_qualifier_declares_no_licence(value: str, simple: bool) -> None:
    assert is_simple_expression(value) is simple


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("GPL-2.0-only+", 2),  # malformed: a usage error, as resolve says
        ("GPL-2.0-or-later+", 2),
        ("MI+", 1),  # well formed, names nothing: "no", as for any unknown ID
        ("Foo", 1),
    ],
)
@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_id_refuses_a_plus_after_a_qualifier(
    command: str, value: str, code: int
) -> None:
    for path in seeded_db("test_plus_and_depth_cli", ROWS):
        result = CliRunner().invoke(cli, ["--db", path, command, "--id", value])
        assert result.exit_code == code
        if code == 2:
            assert result.stdout == ""
            assert result.stderr.splitlines()[-1] == (
                f"ERROR: option: invalid: --id: {value}; pass one license ID"
            )


@pytest.mark.parametrize(
    ("value", "category"),
    [
        ("MIT OR GPL-2.0-only+", "malformed"),  # as GPL-2.0-only+ on its own
        ("(MIT AND GPL-2.0-or-later+)", "malformed"),
        ("MIT OR GPL-2.0+", "expression"),
        ("MIT OR GPL-2.0-only", "expression"),
        ("MIT OR " + "GPL-2.0-only+ OR " * 8 + "MIT", "malformed"),  # a long one
        ("Proprietary or GPL-2.0-only+", "unresolved"),  # not an expression
    ],
)
def test_a_plus_after_a_qualifier_in_an_expression_is_malformed(
    matcher: AggregatedLicenseMatcher, value: str, category: str
) -> None:
    assert resolve(value, matcher.db)["category"] == category


def chain(operators: int) -> str:
    return " AND ".join(f"LicenseRef-{i}" for i in range(operators + 1))


def nest(depth: int) -> str:
    return "(MIT AND " * depth + "MIT" + ")" * depth


@pytest.mark.parametrize(
    ("expression", "parsed"),
    [
        (chain(150), True),
        (chain(151), False),
        (nest(149), True),  # 149 operators and brackets
        (nest(150), True),
        (nest(151), False),
        ("(" * 150 + "MIT" + ")" * 150, True),
        ("(" * 151 + "MIT" + ")" * 151, False),
        (" AND ".join(["(MIT)"] * 151), True),  # side by side, not nested
        (" or ".join(["MIT"] * 151), True),  # 150 operators
        (" or ".join(["MIT"] * 152), False),  # any case of operator counts
        (chain(400), False),  # Python 3.10 gave up here, 3.14 did not
        ("((" + chain(200) + "))", False),
    ],
    ids=lambda v: str(len(v)) if isinstance(v, str) else str(v),
)
def test_the_parser_is_given_150_operators_and_150_brackets(
    expression: str, parsed: bool
) -> None:
    assert (parse_expression(expression) is not None) is parsed


def test_under_the_cap_the_parser_fits_python_3_10s_recursion_limit(
    matcher: AggregatedLicenseMatcher,
) -> None:
    """The deepest shape the cap lets through parses at Python 3.10's
    recursion limit (1000), whatever this interpreter's is."""
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(1000)
    try:
        assert parse_expression(nest(150)) is not None
        tagged = f"/*\n * SPDX-License-Identifier: {chain(150)}\n */"
        assert len(ids(matcher, text=tagged)) == 1
    finally:
        sys.setrecursionlimit(limit)


def test_a_long_chain_is_no_answer_on_any_python(
    matcher: AggregatedLicenseMatcher,
) -> None:
    tagged = f"/*\n * SPDX-License-Identifier: {chain(399)}\n */\n" + "word " * 40
    assert ids(matcher, text=tagged) == []


@pytest.mark.parametrize(
    ("value", "found"),
    [
        ("GPL2-only+", "GPL2-only+"),  # a loose -only: still no ID takes "+"
        ("GPL2-or-later+", "GPL2-or-later+"),
        ("GPL2+", "GPL-2.0-or-later"),
    ],
)
def test_a_loose_id_that_states_its_qualifier_keeps_the_plus(
    matcher: AggregatedLicenseMatcher, value: str, found: str
) -> None:
    assert normalize_identifier(value, matcher.db) == found


def test_a_long_id_before_a_plus_costs_no_version_key(
    matcher: AggregatedLicenseMatcher,
) -> None:
    with mock.patch("licenseid.versionkey.version_key", wraps=version_key) as key:
        assert normalize_identifier("A" * 101 + "+", matcher.db) == "A" * 101 + "+"
    key.assert_not_called()

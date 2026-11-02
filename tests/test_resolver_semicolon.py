# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``match()`` and a ``;`` between licences (task T8b; decisions P81 to
P86): ``MIT ; Apache 2`` names two licences and states no operator, so it
resolves to no expression and lists each part as an operand, read as the
same text would be read alone. The values that were refused for ``;`` before
keep a refusal; the ones the ``;`` ends (``MIT; OR ISC``) are the compound
reader's."""
# pylint: disable=missing-function-docstring

import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship
from resolver_helpers import no_reader_reason

from licenseid import LicenseDatabase, match

REASON = "operator not stated: ;"


def answer_of(result: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """The *keys* of a result or of an operand."""
    return {key: result[key] for key in keys}


# (value, [(text, span, expression, category), ...])
LISTS = [
    (
        "MIT ; Apache 2",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("Apache 2", (6, 14), "Apache-2.0", "version_spelling"),
        ],
    ),
    (
        "MIT;Apache-2.0",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("Apache-2.0", (4, 14), "Apache-2.0", "exact"),
        ],
    ),
    (
        "  MIT;\tISC  ",
        [("MIT", (2, 5), "MIT", "exact"), ("ISC", (7, 10), "ISC", "exact")],
    ),
    (
        "MIT; Apache-2.0; ISC;",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("Apache-2.0", (5, 15), "Apache-2.0", "exact"),
            ("ISC", (17, 20), "ISC", "exact"),
        ],
    ),
    (
        "MIT; GPL-2.0+",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("GPL-2.0+", (5, 13), "GPL-2.0-or-later", "plus_to_or_later"),
        ],
    ),
    (
        "MIT; GPL-3.0",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("GPL-3.0", (5, 12), "GPL-3.0", "assumed_only"),
        ],
    ),
    (
        '"MIT"; "ISC"',
        [('"MIT"', (0, 5), "MIT", "lexical"), ('"ISC"', (7, 12), "ISC", "lexical")],
    ),
    ("(MIT; ISC)", [("MIT", (1, 4), "MIT", "exact"), ("ISC", (6, 9), "ISC", "exact")]),
    ("MIT; MIT", [("MIT", (0, 3), "MIT", "exact"), ("MIT", (5, 8), "MIT", "exact")]),
    (
        "MIT OR ISC; Apache-2.0",
        [
            ("MIT OR ISC", (0, 10), "ISC OR MIT", "lexical"),
            ("Apache-2.0", (12, 22), "Apache-2.0", "exact"),
        ],
    ),
    (
        "MIT and ISC;Apache-2.0",
        [
            ("MIT and ISC", (0, 11), "ISC AND MIT", "lexical"),
            ("Apache-2.0", (12, 22), "Apache-2.0", "exact"),
        ],
    ),
    (
        "MIT; Apache 2.0?",
        [("MIT", (0, 3), "MIT", "exact"), ("Apache 2.0?", (5, 16), None, "unresolved")],
    ),
    (
        "MIT; Foo; ISC",
        [
            ("MIT", (0, 3), "MIT", "exact"),
            ("Foo", (5, 8), None, "unresolved"),
            ("ISC", (10, 13), "ISC", "exact"),
        ],
    ),
    (
        "Apache 2; BSD 3-Clause License",
        [
            ("Apache 2", (0, 8), "Apache-2.0", "version_spelling"),
            ("BSD 3-Clause License", (10, 30), "BSD-3-Clause", "prose_form"),
        ],
    ),
]


@pytest.fixture(name="shipped")
def _shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wheel ships the List of the fixtures, for ``source="packaged"``."""
    ship(monkeypatch, fixture_bundle())


@pytest.mark.parametrize(("value", "parts"), LISTS, ids=lambda v: str(v)[:24])
def test_licences_joined_by_a_semicolon_are_listed_not_combined(
    corpus_db: LicenseDatabase, value: str, parts: list[tuple[Any, ...]]
) -> None:
    got = match(value, corpus_db)
    assert got["expression"] is None
    assert got["category"] == "unresolved"
    assert got["trust"] == "none"
    assert got["reason"] == REASON
    assert got["candidates"] == [] and got["expansions"] == []
    assert [
        (o["text"], tuple(o["span"]), o["expression"], o["category"])
        for o in got["operands"]
    ] == parts
    for operand in got["operands"]:
        assert value[operand["span"][0] : operand["span"][1]] == operand["text"]


def test_the_steps_of_the_whole_are_the_ones_taken_before_the_split(
    corpus_db: LicenseDatabase,
) -> None:
    got = match("  (MIT; ISC) ", corpus_db)
    assert [s["kind"] for s in got["steps"]] == ["trim", "brackets"]
    assert [tuple(o["span"]) for o in got["operands"]] == [(3, 6), (8, 11)]


@pytest.mark.parametrize(
    ("value", "parser"),
    [("MIT; ISC", False), ("MIT OR ISC; Apache-2.0", True)],
)
def test_the_parser_is_a_component_when_a_part_needed_it(
    corpus_db: LicenseDatabase, value: str, parser: bool
) -> None:
    assert bool(match(value, corpus_db)["components"]) is parser


def test_a_refused_part_keeps_its_own_reason_and_steps(
    corpus_db: LicenseDatabase,
) -> None:
    got = match("Apache 2.0?; MIT", corpus_db)
    refused, named = got["operands"]
    assert got["reason"] == REASON
    assert refused["reason"] == "character dropped: U+003F"
    assert [(s["kind"], s["applied"]) for s in refused["steps"]] == [("drop", False)]
    assert named["expression"] == "MIT"


# Not a list: the value is refused as it was before T8b, or read by another rule.
NOT_A_LIST = {
    "MIT;;Apache-2.0": "not an SPDX operator: ;;",  # an empty part (P82)
    "MIT;;": "character dropped: U+003B",
    "; MIT": "character dropped: U+003B",
    ";MIT;ISC": None,
    "MIT; ;ISC": None,
    ";": None,
    ";;;": None,
    "MIT; foo": "not an SPDX operator: ;",  # one licence only (P83)
    "foo; bar": "not an SPDX operator: ;",
    "MIT; Copyright (c) 2016": None,
    "(MIT; ISC": None,  # a bracket that does not close
    "MIT; ISC)": None,
    ")MIT; ISC(": None,
    "(MIT; ISC) OR GPL-2.0": "not an SPDX operator: ;",  # a ; in brackets (P85)
    "(MIT; ISC); Apache-2.0": None,  # a list is not split twice (P85)
    "MIT OR; ISC": None,  # an operator beside the ; (P79)
    "MIT; OR": "parse failed: Unexpected 'OR'",
    "Apache 2; OR MIT": "operand of several words: Apache 2,",  # (; folded)
    "(MIT; ISC; Apache-2.0": None,  # a bracket that does not close (P85)
    "MIT; ISC; Apache-2.0)": None,
    "MIT; ISC; (Apache-2.0": None,  # opens after the last ;
    "MIT); (ISC; Zlib; Apache-2.0": None,  # closes before it opens
    # an operator word on a part means one was stated (P84), in any case
    "MIT; OR ISC; Apache-2.0": "not an SPDX operator: ;",
    "MIT; AND; ISC": "not an SPDX operator: ;",
    "MIT;OR;ISC": "not an SPDX operator: ;",
    "MIT; or ISC; Apache-2.0": "not an SPDX operator: ;",
    "ANTLR-PD-fallback ; OR ISC; GPL-2.0+": (
        "operand of several words: ANTLR-PD-fallback ,"
    ),
    "MIT; ISC; and others": None,
    "MIT; ISC OR; Zlib": None,  # at the end of a part
    "MIT; ISC; Zlib AND": "not an SPDX operator: ;",
    # no part resolves (P88)
    "-MIT ; -MIT": None,
    "MIT...; MIT -": None,
    "MIT, ISC; Apache-2.0": "not an SPDX operator: ,",  # a comma is no separator
    "MIT/ISC; Apache-2.0": "not an SPDX operator: /",
    "MIT, Apache-2.0": "not an SPDX operator: ,",
    "MIT/Apache-2.0": "not an SPDX operator: /",
}


@pytest.mark.parametrize("value", sorted(NOT_A_LIST), ids=lambda v: v[:24])
def test_a_value_that_is_no_list_keeps_its_refusal(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert got["reason"] != REASON
    assert got["expression"] is None
    if NOT_A_LIST[value] is None:  # no reader's own: the default (P5)
        assert no_reader_reason(got["reason"])
    else:
        assert got["reason"] == NOT_A_LIST[value]


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("MIT; OR ISC", "ISC OR MIT"),  # the ; ends an operand (P79)
        ("MIT; and ISC", "ISC AND MIT"),
        ("MIT AND; ISC", None),
        ("MIT;", "MIT"),
        ("MIT OR ISC;", "ISC OR MIT"),
        ("MIT OR ISC", "ISC OR MIT"),
    ],
)
def test_the_neighbours_that_keep_their_answer(
    corpus_db: LicenseDatabase, value: str, expression: str | None
) -> None:
    assert match(value, corpus_db)["expression"] == expression


def test_a_lower_case_operator_in_a_part_is_that_parts_reading(
    corpus_db: LicenseDatabase,
) -> None:
    got = match("MIT or ISC; Apache-2.0 and Zlib", corpus_db)
    assert got["reason"] == REASON
    assert [o["expression"] for o in got["operands"]] == [
        "ISC OR MIT",
        "Apache-2.0 AND Zlib",
    ]


def test_a_part_that_is_prose_is_listed_unresolved(corpus_db: LicenseDatabase) -> None:
    got = match("MIT; ISC; see the file LICENSE", corpus_db)
    assert got["reason"] == REASON
    assert [o["expression"] for o in got["operands"]] == ["MIT", "ISC", None]


def test_a_semicolon_in_brackets_does_not_cut_a_part(
    corpus_db: LicenseDatabase,
) -> None:
    got = match("(ISC; Zlib); MIT; Apache-2.0", corpus_db)
    assert got["reason"] == REASON
    assert [o["text"] for o in got["operands"]] == [
        "(ISC; Zlib)",
        "MIT",
        "Apache-2.0",
    ]
    inside = got["operands"][0]
    assert (inside["expression"], inside["reason"]) == (
        None,
        "not an SPDX operator: ;",  # a part is not split again (P85)
    )


def test_square_brackets_count_as_brackets(corpus_db: LicenseDatabase) -> None:
    got = match("[ISC; Zlib]; MIT; Apache-2.0", corpus_db)
    assert got["reason"] == REASON
    assert [o["text"] for o in got["operands"]] == [
        "[ISC; Zlib]",
        "MIT",
        "Apache-2.0",
    ]


@pytest.mark.parametrize(
    ("value", "expression", "category"),
    [
        ("MIT; (MIT)", "MIT", "separator"),  # a name and its short form (P87)
        ("MIT ;  (MIT)", "MIT", "separator"),
        ('"MIT; (MIT)', "MIT", "separator"),
        ("MIT License;\t(MIT)", "MIT", "prose_form"),
    ],
    ids=lambda v: v[:14],
)
def test_a_name_that_reads_whole_is_not_a_list(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)
    assert got["reason"] is None


def test_a_list_needs_one_operand_that_resolves(corpus_db: LicenseDatabase) -> None:
    got = match("Apache 2.0?; MIT -", corpus_db)
    assert got["reason"] != REASON


def test_a_nested_list_does_not_recurse(corpus_db: LicenseDatabase) -> None:
    deep = "(" * 400 + "MIT; ISC" + ")" * 400
    got = match(deep, corpus_db)
    assert got["reason"] == REASON
    assert len(got["operands"]) == 2


# --- the property: each operand is the part read alone ---


def _samples(db: LicenseDatabase) -> list[str]:
    """Some listed IDs and some listed names, spread over the List."""
    by_name = sorted(db.get_active_ids_by_name().items())
    names = [name for name, _ in by_name[:: max(1, len(by_name) // 25)]]
    ids = sorted({i for _, found in by_name for i in found})
    return ids[:: max(1, len(ids) // 25)] + names


def test_every_operand_is_the_reading_of_its_part_alone(
    corpus_db: LicenseDatabase,
) -> None:
    samples = _samples(corpus_db)
    assert len(samples) > 40
    checked = 0
    for first in samples:
        for second in samples[:: max(1, len(samples) // 12)]:
            value = f"{first} ; {second}"
            got = match(value, corpus_db)
            if got["reason"] != REASON:  # a part names nothing, or has a ;
                continue
            for operand, part in zip(got["operands"], (first, second)):
                kept = set(operand) - {"text", "span"}
                alone = match(part, corpus_db)
                assert answer_of(operand, kept) == answer_of(alone, kept), value
            assert [o["text"] for o in got["operands"]] == [first, second]
            checked += 1
    assert checked > 200


@pytest.mark.usefixtures("shipped")
def test_the_packaged_list_gives_the_same_answers(bundle_db: LicenseDatabase) -> None:
    for value in [*(v for v, _ in LISTS), *NOT_A_LIST]:
        with_db, without = match(value, bundle_db), match(value, source="packaged")
        assert masked(with_db) == masked(without), value
        assert bool(with_db["reason"] == REASON) == bool(without["reason"] == REASON)


# --- time ---


@pytest.mark.parametrize("payload", [lambda n: "MIT;" * n, lambda n: ";" * n])
@pytest.mark.usefixtures("shipped")
def test_a_long_list_is_read_in_time(payload: Callable[[int], str]) -> None:
    start = time.monotonic()
    match(payload(400), source="packaged")
    assert time.monotonic() - start < 3.0


@pytest.mark.benchmark
@pytest.mark.usefixtures("shipped")
@pytest.mark.parametrize("size", [500, 2_000])
def test_a_semicolon_list_is_linear_in_its_length(size: int) -> None:
    for make in (
        lambda n: "MIT;" * n,
        lambda n: ";" * n,
        lambda n: "; ".join(f"MIT{i}" for i in range(n)),
        lambda n: "(" * n + "MIT;" * n + ")" * n,
    ):
        start = time.monotonic()
        match(make(size), source="packaged")
        assert time.monotonic() - start < 5.0

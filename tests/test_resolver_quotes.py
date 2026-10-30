# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``match()`` does with a quoted value (task T6b, decision Q12).

Quote marks around the whole value are taken off by the ``unquote`` step
(:mod:`licenseid.quotes`) and the inside is read as it would be alone. A mark
on one end only is read too, as a weaker answer. Marks inside the value, a
mark of the wrong kind and a value that is only quotes are not read. Before
T6b every one of these was refused by the drop guard (T6).
"""

# pylint: disable=missing-function-docstring

import time
from collections.abc import Sequence

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship

from licenseid import LicenseDatabase, match

#: ``(value, inside)``: a balanced pair of one kind around the whole value,
#: whichever mark opens. One of each shape of a mark: ASCII, grave accent,
#: curly, German, guillemets, single guillemets, primes, modifier letters.
BALANCED = [
    ('"MIT"', "MIT"),
    ("'MIT'", "MIT"),
    ("`MIT`", "MIT"),
    ("`MIT'", "MIT"),
    ("“MIT”", "MIT"),
    ("”MIT”", "MIT"),
    ("„MIT“", "MIT"),
    ("‚MIT‘", "MIT"),
    ("‘MIT’", "MIT"),
    ("«MIT»", "MIT"),
    ("»MIT«", "MIT"),
    ("‹MIT›", "MIT"),
    ("′MIT′", "MIT"),
    ("″MIT″", "MIT"),
    ("ʼMITʼ", "MIT"),
    ("ʺMITʺ", "MIT"),
    ('“MIT"', "MIT"),  # curly open, straight close: one kind
    ('  "MIT"\t', "MIT"),  # trimmed first
    ('" MIT "', "MIT"),  # white space inside the quotes
    ('"mit"', "mit"),  # the inside is read as it would be alone
    ('"Apache 2.0"', "Apache 2.0"),
    ('"Apache2"', "Apache2"),
    ('"GPLv2 or later"', "GPLv2 or later"),
    ('"GPL-2.0+"', "GPL-2.0+"),
    ('"GPL-2.0 WITH Classpath-exception-2.0"', "GPL-2.0 WITH Classpath-exception-2.0"),
    ('"MIT License"', "MIT License"),
    ('"AMD\'s plpa_map.c License"', "AMD's plpa_map.c License"),
    ("'AMD's plpa_map.c License'", "AMD's plpa_map.c License"),
    ('"(MIT)"', "(MIT)"),
]

#: Layers: each is a balanced pair, the kinds may differ between layers.
NESTED = [
    ('""MIT""', 2),
    ("'\"MIT\"'", 2),
    ("\"'MIT'\"", 2),
    ('"""MIT"""', 3),
    ('" "MIT" "', 2),
]

#: One mark on one end only (and nothing else on the other).
UNBALANCED = [
    ('"MIT', "start"),
    ('MIT"', "end"),
    ("'MIT", "start"),
    ("MIT'", "end"),
    ("`MIT", "start"),
    ("MIT`", "end"),
    ("“MIT", "start"),
    ("MIT”", "end"),
    ("«MIT", "start"),
    ("MIT»", "end"),
    ('""MIT"', "start"),  # a pair, then a stray
    ('"MIT""', "end"),
    ('" MIT', "start"),
    ('MIT "', "end"),
]

#: Marks at both ends that do not pair (a double and a single mark): which one
#: is the stray is not known. Refused by the drop guard, with its marks.
MISMATCHED = [
    ("\"MIT'", "U+0022 U+0027"),
    ("'MIT\"", "U+0027 U+0022"),
    ("“MIT’", "U+201C U+2019"),
    ('`MIT"', "U+0060 U+0022"),
    ("«MIT›", "U+00AB U+203A"),
]

#: A mark inside the value, or after the quotes: never read by `unquote`.
#: The drop guard refuses the ones that reach it (value, reason).
INSIDE = [
    ('Apache "2.0"', "U+0022"),
    ('GPL "2.0"', "U+0022"),
    ('"GPL" 2.0', "U+0022"),
    ('"MIT?"', "U+003F"),  # unquoted, then refused for the mark
    ('"MIT*"', "U+002A"),
    ('"MIT".', "U+0022"),
    ('"MIT" ?', "U+0022 U+003F"),
]

#: Not read, no reason: nothing the guard saw (nothing to unquote or an
#: unquoted value that names nothing).
UNREAD = [
    '""',
    '"',
    '"""',
    "' '",
    '" "',
    "''",
    "“”",
    'MIT "or" Apache-2.0',
    '"BSD 3-Clause "New" or "Revised" License"',  # inner marks: not unquoted
    '"BSD"',  # unquoted, but BSD names no one licence
    "'BSD'",
]


def _ids(rows: Sequence[object]) -> list[str]:
    return [ascii(row[0] if isinstance(row, tuple) else row)[:30] for row in rows]


def _steps(value: str, db: LicenseDatabase) -> list[tuple[str, str, str]]:
    return [(s["kind"], s["to"], s["detail"]) for s in match(value, db)["steps"]]


@pytest.mark.parametrize(("value", "inside"), BALANCED, ids=_ids(BALANCED))
def test_a_balanced_pair_is_taken_off(
    corpus_db: LicenseDatabase, value: str, inside: str
) -> None:
    """The step records the text it leaves; the answer is the inside's own."""
    got = match(value, corpus_db)
    alone = match(inside.strip(), corpus_db)
    assert got["expression"] == alone["expression"]
    assert got["expression"] is not None
    unquoted = [s for s in got["steps"] if s["kind"] == "unquote"]
    assert len(unquoted) == 1
    assert (unquoted[0]["applied"], unquoted[0]["to"]) == (True, inside.strip())
    assert unquoted[0]["detail"] == "balanced"
    assert got["reason"] is None


def test_the_unquote_step_is_a_change_of_form(corpus_db: LicenseDatabase) -> None:
    """Like brackets: category lexical, trust identity, no list cited."""
    got = match('"MIT"', corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        "MIT",
        "lexical",
        "identity",
    )
    assert got["steps"] == [
        {
            "kind": "unquote",
            "applied": True,
            "from": '"MIT"',
            "to": "MIT",
            "list": "",
            "detail": "balanced",
            "by": "",
        }
    ]
    assert got["input"] == '"MIT"'


@pytest.mark.parametrize(
    ("value", "category", "trust"),
    [
        ('"mit"', "lexical", "identity"),
        ('"Apache 2.0"', "separator", "resolver_rule"),
        ('"GPLv2 or later"', "version_spelling", "resolver_rule"),
        ('"GPL-2.0+"', "plus_to_or_later", "list_data"),
        ('"MIT License"', "listed_name", "list_data"),
        ('"GPL-3.0"', "assumed_only", "none"),
        ('"GPL-2.0 WITH Classpath-exception-2.0"', "assumed_only", "none"),
        ('"Apache-2.0 WITH LLVM-exception"', "lexical", "identity"),
    ],
    ids=["id-case", "loose", "grant", "plus", "name", "deprecated", "with", "with-ok"],
)
def test_the_inside_keeps_its_own_category(
    corpus_db: LicenseDatabase, value: str, category: str, trust: str
) -> None:
    """The weakest step wins: the quotes never make an answer stronger or
    weaker than the inside is alone."""
    got = match(value, corpus_db)
    assert (got["category"], got["trust"]) == (category, trust)
    inside = got["steps"][0]["to"]
    assert match(inside, corpus_db)["category"] == (
        "exact" if category == "lexical" and inside == got["expression"] else category
    )


@pytest.mark.parametrize(("value", "layers"), NESTED, ids=_ids(NESTED))
def test_every_balanced_layer_is_taken_off(
    corpus_db: LicenseDatabase, value: str, layers: int
) -> None:
    got = match(value, corpus_db)
    assert got["expression"] == "MIT"
    assert _steps(value, corpus_db) == [
        ("unquote", "MIT", f"balanced, {layers} layers")
    ]
    assert got["category"] == "lexical"


@pytest.mark.parametrize(("value", "side"), UNBALANCED, ids=_ids(UNBALANCED))
def test_a_mark_on_one_end_is_read_as_a_weaker_answer(
    corpus_db: LicenseDatabase, value: str, side: str
) -> None:
    """The author's text was not complete: read, but as a rule of the
    resolver (`separator`), and the step says which end."""
    got = match(value, corpus_db)
    assert got["expression"] == "MIT"
    assert (got["category"], got["trust"]) == ("separator", "resolver_rule")
    assert _steps(value, corpus_db) == [("unquote", "MIT", f"unbalanced, {side}")]


@pytest.mark.parametrize(("value", "points"), MISMATCHED, ids=_ids(MISMATCHED))
def test_marks_of_two_kinds_are_not_read(
    corpus_db: LicenseDatabase, value: str, points: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"character dropped: {points}"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]


@pytest.mark.parametrize(("value", "points"), INSIDE, ids=_ids(INSIDE))
def test_a_mark_inside_the_value_is_refused_by_the_guard(
    corpus_db: LicenseDatabase, value: str, points: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"character dropped: {points}"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]


def test_a_dropped_mark_after_unquoting_names_only_that_mark(
    corpus_db: LicenseDatabase,
) -> None:
    """``"MIT?"`` is refused for the question mark, not for the quotes; the
    step is the guard's, the unquote step is not kept (P11)."""
    got = match('"MIT?"', corpus_db)
    assert got["steps"][0]["from"] == "MIT?"
    assert got["steps"][0]["detail"] == "U+003F"


@pytest.mark.parametrize("value", UNREAD, ids=_ids(UNREAD))
def test_a_value_with_nothing_to_read_has_no_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        None,
    )
    assert got["steps"] == []


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ('BSD 3-Clause "New" or "Revised" License', "BSD-3-Clause"),
        ("AMD's plpa_map.c License", "AMDPLPA"),
        (
            "Do What The F*ck You Want To But It's Not My Fault Public License",
            "WTFNMFPL",
        ),
    ],
    ids=["bsd-3", "amd", "wtfnmfpl"],
)
def test_a_listed_name_with_quotes_inside_is_read_as_before(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        expression,
        "listed_name",
        None,
    )
    assert [s["kind"] for s in got["steps"]] == ["listed_name"]


@pytest.mark.parametrize(
    ("value", "kinds"),
    [
        ('("MIT")', ["brackets", "unquote"]),
        ('( "MIT" )', ["brackets", "unquote"]),
        ('"(MIT)"', ["unquote", "brackets"]),
        ("\u201c(MIT)\u201d", ["unquote", "brackets"]),
    ],
)
def test_quotes_and_brackets_come_off_in_either_order(
    corpus_db: LicenseDatabase, value: str, kinds: list[str]
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == ("MIT", "lexical")
    assert [s["kind"] for s in got["steps"]] == kinds


@pytest.mark.parametrize(
    ("value", "kinds"),
    [
        ('"MIT" or "Apache-2.0"', ["unquote", "unquote", "operator_case", "reorder"]),
        ('MIT OR "Apache-2.0"', ["unquote", "reorder"]),
        ("'MIT' OR 'Apache-2.0'", ["unquote", "unquote", "reorder"]),
        (
            "\u201cMIT\u201d OR \u201cApache-2.0\u201d",
            ["unquote", "unquote", "reorder"],
        ),
    ],
)
def test_the_quotes_around_each_operand_come_off(
    corpus_db: LicenseDatabase, value: str, kinds: list[str]
) -> None:
    """Fixed by T7 (was labelled ``expression``): each operand is read as it
    would be alone, so its quotes come off, one ``unquote`` step each."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == ("Apache-2.0 OR MIT", "lexical")
    assert [s["kind"] for s in got["steps"]] == kinds
    assert [o["expression"] for o in got["operands"]] == ["MIT", "Apache-2.0"]


@pytest.mark.parametrize("value", ['"MIT" OR Apache-2.0"', '"MIT OR "Apache-2.0"'])
def test_a_quote_left_over_in_a_compound_is_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A lone quote is not paired with one in another operand: the operand
    keeps it and the drop guard refuses it."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == "character dropped: U+0022"


def test_a_compound_in_quotes_is_still_a_compound(
    corpus_db: LicenseDatabase,
) -> None:
    """The quotes around the whole come off first, then the compound is read."""
    for value, kinds in (
        ('"MIT OR Apache-2.0"', ["unquote", "reorder"]),
        ("MIT OR Apache-2.0", ["reorder"]),
    ):
        got = match(value, corpus_db)
        assert (got["expression"], got["category"]) == ("Apache-2.0 OR MIT", "lexical")
        assert [s["kind"] for s in got["steps"]] == kinds


@pytest.mark.parametrize(
    "size", [1_000, 5_000, pytest.param(200_000, marks=pytest.mark.benchmark)]
)
def test_a_long_run_of_quotes_is_fast(corpus_db: LicenseDatabase, size: int) -> None:
    """Balanced, unbalanced and mismatched runs, marks inside, and a run of
    apostrophes between letters, read whole through ``match()``. That
    ``unquote`` is linear is ``test_quotes.test_unquote_is_linear_in_the_length``;
    200,000 marks are a benchmark (``--run-benchmark``), too slow to
    run on every commit (PR #121)."""
    values = [
        '"' * size + "MIT" + '"' * size,
        "“" * size + "MIT" + '"' * size,
        '"' * size + "MIT",
        '"' * size + "MIT" + "'" * size,
        '"' * size,
        '"' + 'a"' * size + '"',
        '"' + "a'" * size + 'a"',
        '"MIT' + ' "x"' * size,
    ]
    start = time.monotonic()
    answers = [match(value, corpus_db)["expression"] for value in values]
    assert time.monotonic() - start < 10
    # Two balanced runs are read; one stray mark is taken off, not a run of
    # them; marks inside the value are not read.
    assert answers == ["MIT", "MIT"] + [None] * 6


def test_a_value_over_the_length_limit_is_unresolved_whatever_the_quotes(
    corpus_db: LicenseDatabase,
) -> None:
    assert match('"' + "x" * 5_000 + '"', corpus_db)["expression"] is None


def test_the_same_answer_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    """The packaged list gives the whole answer, steps included, for every
    value of the tables above."""
    ship(monkeypatch, fixture_bundle())
    rows = BALANCED + UNBALANCED + MISMATCHED + INSIDE
    values = [row[0] for row in rows] + [row[0] for row in NESTED] + UNREAD
    for value in values:
        assert masked(match(value, bundle_db)) == masked(
            match(value, source="packaged")
        ), value

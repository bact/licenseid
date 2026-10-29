# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Properties of the compounds ``match()`` reads (task T7), over the parity
corpus, the PyPI sample and the generated compounds: an operand reads as the
same text alone, the answer is the same from the database and the packaged
list, the order is deterministic, every answer parses and is a fixed point.
"""

import itertools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import py_spdx_license
import pytest
from compound_cases import generated_compounds
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship
from resolver_corpus import corpus_rows

from licenseid import LicenseDatabase, match
from licenseid.resolverinfo import parser_info
from licenseid.resolvertypes import CATEGORY_ORDER, Operand
from tools.pypi_licence_sample.answer import unescape_field

#: The steps of the compound itself, after those of its operands.
_RE_WITH = re.compile(r" WITH [A-Za-z0-9.:-]+")
CANONICAL_KINDS = ("operator_case", "whitespace", "brackets", "reorder", "dedupe")


def _values() -> list[str]:
    """Every corpus value and every generated compound, once each."""
    corpus = [unescape_field(row["value"]) for row in corpus_rows()]
    return list(dict.fromkeys(corpus + generated_compounds()))


VALUES = _values()


def _alone(operand: Operand) -> tuple[object, ...]:
    """What an operand says of itself, as a whole result would say it."""
    return (
        operand["expression"],
        operand["category"],
        operand["candidates"],
        operand["reason"],
        operand["steps"],
        operand["expansions"],
    )


def test_an_operand_reads_as_the_same_text_alone(corpus_db: LicenseDatabase) -> None:
    """For every value, each operand is what ``match`` answers for its
    text, and its span points at that text in the input."""
    wrong = []
    for value in VALUES:
        for operand in match(value, corpus_db)["operands"]:
            start, end = operand["span"]
            alone = match(operand["text"], corpus_db)
            got = (
                alone["expression"],
                alone["category"],
                alone["candidates"],
                alone["reason"],
                alone["steps"],
                alone["expansions"],
            )
            if value[start:end] != operand["text"] or got != _alone(operand):
                wrong.append(f"{value!r}: {operand['text']!r}")
    assert len(VALUES) > 600
    assert not wrong, wrong


def test_a_compound_is_as_weak_as_its_weakest_operand(
    corpus_db: LicenseDatabase,
) -> None:
    """The category of a resolved compound is its weakest operand's, or
    ``lexical`` when only the form changed; never stronger than an operand."""
    for value in VALUES:
        got = match(value, corpus_db)
        if got["expression"] is None or len(got["operands"]) < 2:
            continue
        weakest = max(
            (o["category"] for o in got["operands"]), key=CATEGORY_ORDER.index
        )
        if weakest == "exact":
            assert got["category"] in ("exact", "lexical"), value
            continue
        assert got["category"] == weakest, value


def test_a_compound_reads_the_same_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    """The generated compounds, from the database and the packaged list:
    only ``lists[*].source`` differs."""
    ship(monkeypatch, fixture_bundle())
    for value in generated_compounds():
        with_db, without = match(value, bundle_db), match(value, source="packaged")
        assert masked(with_db) == masked(without), value


def test_every_answer_parses_as_an_spdx_expression(corpus_db: LicenseDatabase) -> None:
    """A drift guard: every expression ``match`` gives is one the SPDX
    parser reads, its ``WITH`` and ``+`` taken off (the parser reads neither
    with unknown IDs allowed)."""
    for value in VALUES:
        expression = match(value, corpus_db)["expression"]
        if expression is not None:
            bare = _RE_WITH.sub("", expression).replace("+", "")
            py_spdx_license.parse(bare, allow_unknown=True)


def test_every_answer_is_a_fixed_point(corpus_db: LicenseDatabase) -> None:
    """Resolving an answer gives the answer again, with no step of form: it
    is already in canonical order."""
    for value in VALUES:
        expression = match(value, corpus_db)["expression"]
        if expression is None:
            continue
        again = match(expression, corpus_db)
        assert again["expression"] == expression, value
        kinds = {s["kind"] for s in again["steps"]}
        assert not kinds & set(CANONICAL_KINDS), (value, kinds)


@pytest.mark.parametrize(
    "operands",
    [
        ("MIT", "Apache-2.0", "ISC"),
        ("GPL-2.0+", "LicenseRef-x", "Apache-2.0 WITH LLVM-exception"),
        ("(MIT AND ISC)", "0BSD", "(BSD-2-Clause OR Zlib)"),
    ],
    ids=["ids", "kinds", "groups"],
)
@pytest.mark.parametrize("operator", ["OR", "AND"])
def test_the_order_written_does_not_change_the_answer(
    corpus_db: LicenseDatabase, operands: tuple[str, ...], operator: str
) -> None:
    """Every permutation of the operands gives one expression."""
    answers = {
        match(f" {operator} ".join(order), corpus_db)["expression"]
        for order in itertools.permutations(operands)
    }
    assert len(answers) == 1
    assert None not in answers


def test_the_answer_does_not_depend_on_the_hash_seed(
    bundle_db: LicenseDatabase, tmp_path: Path
) -> None:
    """Interpreters with other hash seeds give the same expressions (no set
    or dict order leaks into the sort)."""
    script = (
        "import json, sys\n"
        "from licenseid import LicenseDatabase, match\n"
        "db = LicenseDatabase(sys.argv[1], create=False)\n"
        "values = json.loads(sys.stdin.read())\n"
        "print(json.dumps([match(v, db)['expression'] for v in values]))\n"
    )
    values = json.dumps(
        [
            "LicenseRef-b OR MIT OR LicenseRef-a OR isc OR LicenseRef-B",
            "(ISC OR MIT) AND (Zlib OR 0BSD) AND MIT WITH LLVM-exception",
        ]
    )
    outputs = set()
    for seed in ("1", "2", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "HOME": str(tmp_path)}
        done = subprocess.run(
            [sys.executable, "-c", script, str(bundle_db.db_path)],
            input=values,
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parents[1],
            check=False,
            timeout=60,
        )
        assert done.returncode == 0, done.stderr
        outputs.add(done.stdout)
    assert len(outputs) == 1, outputs


def test_a_compound_names_the_parser_as_a_component(
    corpus_db: LicenseDatabase,
) -> None:
    """The parser that read the expression is listed; a single value, none."""
    assert match("MIT OR ISC", corpus_db)["components"] == [parser_info()]
    assert not match("MIT", corpus_db)["components"]

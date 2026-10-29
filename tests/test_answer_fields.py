# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How a fixture file writes an answer (``tools.pypi_licence_sample.answer``)
and how the guard reads a TSV file (``resolver_corpus.read_rows``)."""

from pathlib import Path
from typing import cast

import pytest
from resolver_corpus import read_rows

from licenseid.resolvertypes import Resolution
from tools.pypi_licence_sample.answer import (
    ANSWER_COLUMNS,
    Answer,
    answer_diff,
    answer_fields,
    answer_from_row,
    answer_of,
    dump_targets,
    load_targets,
)

RESULT = {
    "input": "MIT",
    "expression": "MIT",
    "category": "exact",
    "trust": "identity",
    "steps": [],
    "expansions": [],
    "candidates": [],
}

PLAIN = Answer(
    expression="MIT",
    category="separator",
    candidates=(),
    steps=("separator",),
    step_targets=("MIT",),
    expansions=(),
    expansion_targets=(),
    trust="resolver_rule",
    input_same=True,
    reason=None,
)


@pytest.mark.parametrize(
    "answer",
    [
        PLAIN,
        PLAIN._replace(expression=None, steps=(), step_targets=()),
        PLAIN._replace(
            steps=("trim", "separator!"),
            step_targets=("MIT", "a,b"),
            expansions=("assumed_only!",),
            expansion_targets=("GPL-3.0",),
            input_same=False,
            reason="lone surrogate",
        ),
        PLAIN._replace(step_targets=("tab\there", "back\\slash", "é", "\udcff", "-")),
        PLAIN._replace(reason="tab\t back\\slash \udcff é"),
        PLAIN._replace(candidates=("GPL-3.0-only", "GPL-3.0-or-later")),
    ],
    ids=["plain", "none", "all-fields", "escapes", "reason-escapes", "candidates"],
)
def test_an_answer_survives_its_fields(answer: Answer) -> None:
    """Writing an answer as TSV fields and reading it back gives the same."""
    fields = answer_fields(answer)
    assert len(fields) == len(ANSWER_COLUMNS)
    assert all("\t" not in f and "\n" not in f for f in fields)
    assert answer_from_row(dict(zip(ANSWER_COLUMNS, fields))) == answer


def test_a_target_with_a_comma_stays_one_target() -> None:
    """The list separator in a target is escaped."""
    assert load_targets(dump_targets(("a,b", "c"))) == ("a,b", "c")


def test_an_empty_target_cannot_be_written() -> None:
    """One empty target would read back as no target."""
    with pytest.raises(ValueError, match="empty target"):
        dump_targets(("",))


def test_the_diff_names_only_the_fields_that_differ() -> None:
    """Field by field, not two whole tuples."""
    new = PLAIN._replace(trust="none", step_targets=("ISC",))
    assert answer_diff(PLAIN, new) == (
        "step_targets: ('MIT',) -> ('ISC',); trust: 'resolver_rule' -> 'none'"
    )
    assert answer_diff(PLAIN, PLAIN) == ""


@pytest.mark.parametrize(
    ("row", "count"), [("x\ty\tz", 3), ("x", 1)], ids=["too-many", "too-few"]
)
def test_a_row_with_the_wrong_field_count_is_refused(
    tmp_path: Path, row: str, count: int
) -> None:
    """A short or long row would silently lose or misplace a column."""
    path = tmp_path / "t.tsv"
    path.write_text(f"# c\na\tb\n1\t2\n{row}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"t\.tsv: row 3 has {count} fields, the h"):
        read_rows(path)


def test_a_well_formed_file_is_read(tmp_path: Path) -> None:
    """Fields are not stripped."""
    path = tmp_path / "t.tsv"
    path.write_text("# c\na\tb\n 1\t2 \n", encoding="utf-8")
    assert read_rows(path) == [{"a": " 1", "b": "2 "}]


def test_the_reason_of_a_result_is_pinned() -> None:
    """``Resolution.reason`` comes with T6; until then a result without one is
    ``None`` and a result with one is read."""
    result = cast(Resolution, {**RESULT})
    assert answer_of("MIT", result).reason is None
    assert answer_of("MIT", cast(Resolution, {**RESULT, "reason": "x"})).reason == "x"


def test_a_step_that_did_not_apply_is_pinned_with_a_bang() -> None:
    """The first such step comes with T6's ``drop`` (``applied: false``)."""
    step = {"kind": "drop", "applied": False, "from": "MIT?", "to": "MIT"}
    result = cast(Resolution, {**RESULT, "steps": [step], "expansions": [step]})
    answer = answer_of("MIT?", result)
    assert answer.steps == ("drop!",)
    assert answer.expansions == ("drop!",)
    assert answer.step_targets == ("MIT",)

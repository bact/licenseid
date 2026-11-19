# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An end mark after an "or later" grant is cut, so the value is not exact
(tech-debt roadmap, item 58).

``MIT or later.`` was read as ``MIT+`` with no step, so ``resolve()`` gave
``stated_qualifier`` and ``detect()`` said ``exact``: the argument, a
``license`` field and a compound operand dropped the mark in silence, where
``MIT.`` and ``MIT;`` took a ``separator`` step, "end mark", and were not
exact. The grant reader (``resolveleaf._single``) now takes one end mark off
as they do, and a field is judged by it too (``ruleread.tag_inexact``,
``resolvefirst.was_cut``). A tag keeps its answer: it runs on into prose.

A database of the whole List (``corpus_db``)."""
# pylint: disable=missing-function-docstring

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import answers

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector

LICENCES = [
    ("MIT", "MIT+"),
    ("GPL-2.0", "GPL-2.0-or-later"),
    ("LGPL v2.1", "LGPL-2.1-or-later"),
    ("Apache 2.0", "Apache-2.0+"),
]
GRANTS = [" or later", " (or later)", " [or later]", " or any later version"]
ENDS = [".", ",", ";", ":", " ."]


def _steps(db: LicenseDatabase, value: str) -> list[tuple[str, str | None]]:
    return [(s["kind"], s["detail"]) for s in resolve(value, db)["steps"]]


@pytest.mark.parametrize("end", ENDS, ids=repr)
@pytest.mark.parametrize("grant", GRANTS)
@pytest.mark.parametrize(("name", "expression"), LICENCES)
def test_one_end_mark_after_a_grant_is_a_cut_ending(
    corpus_db: LicenseDatabase, name: str, expression: str, grant: str, end: str
) -> None:
    value = name + grant + end
    found = resolve(value, corpus_db)
    assert found["expression"] == expression  # the answer does not move
    assert ("separator", "end mark") in _steps(corpus_db, value)
    got = answers(corpus_db, value)
    assert got["argument"] == (expression, False)
    assert got["field"] == (expression, False)
    # a tag runs on into prose: the mark changes nothing there
    assert got["tag"] == answers(corpus_db, name + grant)["tag"]


def test_the_end_mark_step_comes_first(corpus_db: LicenseDatabase) -> None:
    """The end mark is the first step, before the readings of the grant."""
    assert _steps(corpus_db, "MIT or later.") == [("separator", "end mark")]
    assert _steps(corpus_db, "GPL-2.0 - or later.") == [
        ("separator", "end mark"),
        ("separator", None),
    ]


@pytest.mark.parametrize(
    "value",
    [
        "MIT or later",
        "MIT (or later)",
        "MIT [or later]",
        "MIT or any later version",
        "MIT or later)",  # a closing bracket is no end mark
        "MIT or later]",
        "GPL-2.0 or later",
    ],
)
def test_a_grant_with_no_end_mark_is_unchanged(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _steps(corpus_db, value) == []
    assert resolve(value, corpus_db)["category"] == "stated_qualifier"
    got = answers(corpus_db, value)
    assert got["argument"] is not None and got["argument"][1] is True
    assert got["field"] == got["argument"]


@pytest.mark.parametrize("value", ["MIT or later;", "MIT or later:"])
def test_the_cli_says_it_was_cut(corpus_db: LicenseDatabase, value: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "detect", "--text", value, "--json"]
    )
    assert result.exit_code == 0
    assert '"exact":false' in result.stdout
    assert '"expression":"MIT+"' in result.stdout


@pytest.mark.parametrize(
    "value", ["LicenseRef-x or later.", "GPL-2.0-only or later.", "MIT or later?"]
)
def test_a_refused_value_gets_no_end_mark_step(
    corpus_db: LicenseDatabase, value: str
) -> None:
    found = resolve(value, corpus_db)
    assert found["expression"] is None
    assert ("separator", "end mark") not in _steps(corpus_db, value)


def test_an_operand_with_an_end_mark_is_not_exact(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    value = "GPL-2.0 or later, OR MIT"
    found = resolve(value, corpus_db)
    assert (found["expression"], found["category"]) == (
        "GPL-2.0-or-later OR MIT",
        "separator",
    )
    top = LicenseDetector(corpus_db.location).detect(text=value)[0]
    assert top["exact"] is False
    assert not given.conditions()


@pytest.mark.parametrize("value", ["MIT or later..", "MIT or later;;"])
def test_two_marks_after_a_grant_are_still_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Not this fix's to move: ``MIT;;`` is refused, but these answer MIT+."""
    assert resolve(value, corpus_db)["expression"] == "MIT+"  # BUG: stays


@pytest.mark.parametrize(
    "value",
    [
        "(GPL-2.0) or later.",
        "(GPL-2.0 WITH Classpath-exception-2.0) or later;",
        "GPLv2 version 2 or later.",
    ],
)
def test_a_field_resolve_refuses_keeps_its_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A field is only judged by what ``resolve()`` cut: one it refuses
    answers as before (a right answer is never lost for the mark)."""
    assert answers(corpus_db, value)["field"] is not None
    assert answers(corpus_db, value)["field"] == answers(corpus_db, value)["tag"]

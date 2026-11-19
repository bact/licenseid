# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A stated qualifier, a doubled one, a "+" beside a WITH, a blank
database path and one end mark after a lone expression: findings of a
review of the pre-freeze changes of 0.7.0 (2026-11-02), on the whole
3.29.0 List.

Each test was first a pin of what the branch did when the review found it
(the commit before the fix); it now holds the new answer and names the
decision (working-docs/design/resolver-0-7-review.md).
"""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import InvalidInputError, LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.identifiers import disambiguate_deprecated_id


def _top(corpus_db: LicenseDatabase, text: str) -> tuple[str, bool] | None:
    found = LicenseDetector(corpus_db.location).detect(text)
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _field(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> str | None:
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"license": value}), encoding="utf-8")
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    return found[0]["expression"] if found and found[0]["exact"] else None


# --- A prose qualifier answers one operand only --------------------


@pytest.mark.parametrize(
    ("value", "field"),
    [
        ("LicenseRef-Proprietary AND GPL-2.0 only", None),
        ("MIT AND GPL-2.0 only", None),
        # The field's own reader reads the grant beside its ID.
        ("Apache-2.0 OR GPL-2.0 or later", "Apache-2.0 OR GPL-2.0-or-later"),
        ("BSD-3-Clause AND LGPL-2.1 or later", "BSD-3-Clause AND LGPL-2.1-or-later"),
        ("LGPL-2.1+ AND GPL-2.0 only", None),
        ("GPL-2.0 or later OR MIT", "GPL-2.0-or-later OR MIT"),  # resolve() reads it
        ("GPL-2.0 or later, and also MIT", None),
        # A deprecated ID inside another ID is no ID: "-" before it.
        ("LicenseRef-GPL-2.0 or later", None),
        ("LicenseRef-x-GPL-2.0 only", None),
    ],
)
def test_a_qualifier_never_answers_a_compound_alone(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    value: str,
    field: str | None,
    given: GivenWarnings,
) -> None:
    """Was: the prose reader read the whole value, so one qualified ID
    answered the compound, exact, from an argument and a manifest field;
    ``LicenseRef-GPL-2.0 or later`` was GPL-2.0-or-later; now the reader
    declines when an operator outside its phrase joins another licence, so
    no answer drops an operand. A field's own reader still reads the whole
    expression where it can. The whole value as text is resolve()'s."""
    assert disambiguate_deprecated_id(value) is None
    top = _top(corpus_db, value)
    expression = resolve(value, corpus_db)["expression"]
    if expression is None:
        assert top is None or not top[1], top
    else:
        assert top == (expression, True)
    assert _field(corpus_db, tmp_path, value) == field
    # A refused value is too short to match as text, and says why.
    assert given.conditions() <= {"too few words for text"}


def test_the_predicate_says_nothing(corpus_db: LicenseDatabase) -> None:
    """Was: ``is-osi "LicenseRef-Proprietary AND GPL-2.0 only"`` said
    true, exit 0; now no licence found, so no flag."""
    result = CliRunner().invoke(
        cli,
        [
            "--db",
            corpus_db.location,
            "is-osi",
            "LicenseRef-Proprietary AND GPL-2.0 only",
        ],
    )
    assert (result.exit_code, result.stdout) == (1, "EXPRESSION=\tIS_OSI_APPROVED=\n")


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("GPL-2.0 or any later version", "GPL-2.0-or-later"),
        ("GPL-2.0 only", "GPL-2.0-only"),
        ("(GPL-2.0 or later)", "GPL-2.0-or-later"),
        ("licensed under GPL-2.0. This version only.", "GPL-2.0-only"),
        ("LGPL-2.1 or, at your option, any later version", "LGPL-2.1-or-later"),
    ],
)
def test_a_lone_qualified_id_still_reads(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """The "or" of the phrase is the phrase's, and prose
    with no operator still answers."""
    assert disambiguate_deprecated_id(value) == answer
    if len(value.split()) < 6:
        assert _top(corpus_db, value) == (answer, value != "GPL-2.0 only")


# --- A "+" after a deprecated -with- ID is its licence's ------------


@pytest.mark.parametrize(
    ("value", "reading"),
    [
        (
            "GPL-2.0-with-classpath-exception+",
            "GPL-2.0-or-later WITH Classpath-exception-2.0",
        ),
        ("GPL-3.0-with-GCC-exception+", "GPL-3.0-or-later WITH GCC-exception-3.1"),
        ("gpl-2.0-with-font-exception+", "GPL-2.0-or-later WITH Font-exception-2.0"),
    ],
)
def test_a_with_id_and_a_plus_reads_as_or_later(
    corpus_db: LicenseDatabase, value: str, reading: str
) -> None:
    """Was: ``GPL-2.0-with-classpath-exception+`` answered itself, a
    deprecated ID, exact, and ``is-osi`` said a judged false; now the "+" is
    the grant of its licence, and no warning. Not exact:
    ``resolve()`` calls it ambiguous (``deprecated_ambiguous``)."""
    for text in (value, f"SPDX-License-Identifier: {value}"):
        assert _top(corpus_db, text) == (reading, False)
    (found,) = LicenseDetector(corpus_db.location).detect(license_id=value)
    assert (found["expression"], found["exact"]) == (reading, False)


def test_a_doubled_qualifier_is_still_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    """``-only+`` stays no licence, and says why."""
    assert _top(corpus_db, "GPL-2.0-only+") is None
    assert given.conditions() == {"too few words for text"}


# --- A tag that states the "+" again ---------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "LGPL-2.1+ only",
        "GPL-2.0+ or later",
        "GPL-2.0+ or any later version",
        # A grant after -only (maintainer, 2026-11-02; was GPL-2.0-only).
        "GPL-2.0-only or (at your option) any later version",
    ],
)
def test_a_tag_refuses_a_plus_stated_twice(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Was: the tag answered LGPL-2.1-or-later, exact, where ``resolve()``
    refuses, ``qualifier stated twice``, and the argument finds none. A
    grant after an ID that states its qualifier is refused the same way."""
    assert _top(corpus_db, f"SPDX-License-Identifier: {value}") is None


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0+ some comment", "GPL-2.0-or-later"),  # prose after a tag
        ("GPL-2.0-only, see COPYING", "GPL-2.0-only"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
    ],
)
def test_other_words_after_a_tag_still_read(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """Only a qualifier stated again is refused."""
    assert _top(corpus_db, f"SPDX-License-Identifier: {value}") == (answer, True)


# --- LicenseDatabase("") ----------------------------------------------


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_database_path_is_refused(create: bool, blank: str) -> None:
    """Was: ``LicenseDatabase("")`` raised a raw sqlite3 error, and
    ``create=False`` named the working directory as unreadable."""
    with pytest.raises(
        InvalidInputError, match="^database: missing: db_path; pass a path$"
    ):
        LicenseDatabase(blank, create=create)


# --- A "+" before an end mark -----------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0+,", ("GPL-2.0-or-later", False)),
        ("GPL-2.0+.", ("GPL-2.0-or-later", False)),
        ("GPL-2.0+;", ("GPL-2.0-or-later", False)),
        ("Apache-2.0+,", ("Apache-2.0+", False)),
        ("MIT,", ("MIT", False)),  # a separator: no list,
        ("GPL-2.0,", ("GPL-2.0", False)),  # bare: kept as written
    ],
)
def test_one_end_mark_ends_a_lone_expression(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    value: str,
    answer: tuple[str, bool],
    given: GivenWarnings,
) -> None:
    """Was: the argument and the field lost the "+" before a comma or
    full stop, ``GPL-2.0+,`` as GPL-2.0-only with a warning, and
    ``Apache-2.0+,`` as Apache-2.0, exact; now one end mark ends the value,
    as for a tag and ``resolve()``."""
    assert _top(corpus_db, value) == answer
    assert _field(corpus_db, tmp_path, value) == (answer[0] if answer[1] else None)
    assert given.conditions() <= {"variant not stated"}

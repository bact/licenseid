# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The second review of the contract batch of 0.7.0 (findings S1 to S7,
2026-11-02), on the whole 3.29.0 List.

Each test was first a pin of what the branch did when the review found it
(the commit before the fix); it now holds the new answer and names the
decision (P169 on, working-docs/design/resolver-0-7-review.md).
"""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import InvalidInputError, LicenseDatabase
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.identifiers import disambiguate_deprecated_id, simple_value


def _top(corpus_db: LicenseDatabase, text: str) -> tuple[str, bool] | None:
    found = LicenseDetector(corpus_db.location).detect(text)
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _field(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> str | None:
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"license": value}), encoding="utf-8")
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    return found[0]["expression"] if found and found[0]["exact"] else None


# --- S1: a prose qualifier answers one operand only (P169) --------------------


@pytest.mark.parametrize(
    ("value", "field"),
    [
        ("LicenseRef-Proprietary AND GPL-2.0 only", None),
        ("MIT AND GPL-2.0 only", None),
        # The field's own reader reads the grant beside its ID.
        ("Apache-2.0 OR GPL-2.0 or later", "Apache-2.0 OR GPL-2.0-or-later"),
        ("BSD-3-Clause AND LGPL-2.1 or later", "BSD-3-Clause AND LGPL-2.1-or-later"),
        ("LGPL-2.1+ AND GPL-2.0 only", None),
        ("GPL-2.0 or later OR MIT", None),
        ("GPL-2.0 or later, and also MIT", None),
        # A deprecated ID inside another ID is no ID: "-" before it.
        ("LicenseRef-GPL-2.0 or later", None),
        ("LicenseRef-x-GPL-2.0 only", None),
    ],
)
def test_s1_a_qualifier_never_answers_a_compound_alone(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, field: str | None
) -> None:
    """S1 (was: the prose reader read the whole value, so one qualified ID
    answered the compound, exact, from an argument and a manifest field;
    ``LicenseRef-GPL-2.0 or later`` was GPL-2.0-or-later): the reader
    declines when an operator outside its phrase joins another licence, so
    no answer drops an operand. A field's own reader still reads the whole
    expression where it can."""
    assert disambiguate_deprecated_id(value) is None
    top = _top(corpus_db, value)
    assert top is None or not top[1], top
    assert _field(corpus_db, tmp_path, value) == field


def test_s1_the_predicate_says_nothing(corpus_db: LicenseDatabase) -> None:
    """S1 (was: ``is-osi "LicenseRef-Proprietary AND GPL-2.0 only"`` said
    true, exit 0): no licence found, so no flag."""
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
def test_s1_a_lone_qualified_id_still_reads(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """S1, adversarial: the "or" of the phrase is the phrase's, and prose
    with no operator still answers."""
    assert disambiguate_deprecated_id(value) == answer
    if len(value.split()) < 6:
        assert _top(corpus_db, value) == (answer, True)


# --- S2: a "+" after a deprecated -with- ID is its licence's (P170) ------------


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
def test_s2_a_with_id_and_a_plus_reads_as_or_later(
    corpus_db: LicenseDatabase, value: str, reading: str
) -> None:
    """S2 (was: ``GPL-2.0-with-classpath-exception+`` answered itself, a
    deprecated ID, exact, and ``is-osi`` said a judged false): the "+" is
    the grant of its licence, stated, so exact and no warning."""
    for text in (value, f"SPDX-License-Identifier: {value}"):
        assert _top(corpus_db, text) == (reading, True)
    (found,) = LicenseDetector(corpus_db.location).detect(license_id=value)
    assert (found["expression"], found["exact"]) == (reading, True)


def test_s2_a_doubled_qualifier_is_still_refused(corpus_db: LicenseDatabase) -> None:
    """S2, adversarial: ``-only+`` stays no licence."""
    assert _top(corpus_db, "GPL-2.0-only+") is None


# --- S4: a tag that states the "+" again (P172) ---------------------------------


@pytest.mark.parametrize(
    "value", ["LGPL-2.1+ only", "GPL-2.0+ or later", "GPL-2.0+ or any later version"]
)
def test_s4_a_tag_refuses_a_plus_stated_twice(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """S4 (was: the tag answered LGPL-2.1-or-later, exact, where ``match()``
    refuses, ``qualifier stated twice``, and the argument finds none)."""
    assert _top(corpus_db, f"SPDX-License-Identifier: {value}") is None


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0+ some comment", "GPL-2.0-or-later"),  # prose after a tag
        ("GPL-2.0-only or (at your option) any later version", "GPL-2.0-only"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
    ],
)
def test_s4_other_words_after_a_tag_still_read(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """S4, adversarial: only a qualifier after a "+" is refused."""
    assert _top(corpus_db, f"SPDX-License-Identifier: {value}") == (answer, True)


# --- S6: LicenseDatabase("") (P174) ----------------------------------------------


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("blank", ["", "  "])
def test_s6_a_blank_database_path_is_refused(create: bool, blank: str) -> None:
    """S6 (was: ``LicenseDatabase("")`` raised a raw sqlite3 error, and
    ``create=False`` named the working directory as unreadable)."""
    with pytest.raises(
        InvalidInputError, match="^database: missing: db_path; pass a path$"
    ):
        LicenseDatabase(blank, create=create)


# --- S7: a "+" before an end mark (P175) -----------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0+,", ("GPL-2.0-or-later", True)),
        ("GPL-2.0+.", ("GPL-2.0-or-later", True)),
        ("GPL-2.0+;", ("GPL-2.0-or-later", True)),
        ("Apache-2.0+,", ("Apache-2.0+", True)),
        ("MIT,", ("MIT", True)),
        ("GPL-2.0,", ("GPL-2.0-only", False)),  # bare: the narrow guess
    ],
)
def test_s7_one_end_mark_ends_a_lone_expression(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, answer: tuple[str, bool]
) -> None:
    """S7 (was: the argument and the field lost the "+" before a comma or
    full stop, ``GPL-2.0+,`` as GPL-2.0-only with a warning, and
    ``Apache-2.0+,`` as Apache-2.0, exact): one end mark ends the value,
    as for a tag and ``match()``."""
    assert _top(corpus_db, value) == answer
    assert _field(corpus_db, tmp_path, value) == (answer[0] if answer[1] else None)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("MIT", "MIT"),
        ("GPL-2.0+,", "GPL-2.0+"),
        ("MIT ;", "MIT"),
        ("MIT,,", None),  # two marks: P77
        ("MIT OR", None),
        ("MIT OR ISC,", None),  # a compound is no simple expression
        (",", None),
    ],
)
def test_s7_simple_value(text: str, value: str | None) -> None:
    assert simple_value(text) == value

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag that lists licences, and a dashed grant, on the whole SPDX List
(the review of #158): every ID is there, so a plain word that is an ID too
("Intel", "Zlib", "DOC") is seen as one.
"""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector


def _tag(db: LicenseDatabase, value: str) -> tuple[str, bool] | None:
    found = LicenseDetector(db.location).detect(f"SPDX-License-Identifier: {value}\n")
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _field(db: LicenseDatabase, tmp_path: Path, value: str) -> str | None:
    path = tmp_path / "pyproject.toml"
    path.write_text(f'[project]\nlicense = "{value}"\n', encoding="utf-8")
    found = LicenseDetector(db.location).detect(file_path=str(path))
    return found[0]["expression"] if found else None


@pytest.mark.parametrize(
    "value",
    [
        "MIT, Zlib",  # a plain-word ID alone in its item
        "MIT, X11 style",  # an ID with a version in it, as _lists_another reads
        "MIT, Classpath-exception-2.0",
        "MIT, LicenseRef-x see notes",  # a reference is never prose
        "MIT/ISC License",  # a last "License" leaves the ID alone in its item
        "Apache-2.0, MIT license",
        "MIT, Intel, ISC",  # an item ends at the next mark
    ],
)
def test_a_listed_licence_after_a_mark_is_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _tag(corpus_db, value) is None


@pytest.mark.parametrize(
    ("value", "kept"),
    [
        ("Apache-2.0, Intel copyright", "Apache-2.0"),
        ("MIT, Zlib style", "MIT"),
        ("MIT; Doc: see README", "MIT"),  # DOC is an ID in any case
        ("MIT, Python", "MIT"),
    ],
)
def test_a_plain_word_id_in_prose_lists_no_licence(
    corpus_db: LicenseDatabase, value: str, kept: str
) -> None:
    """It was refused once the tag read every ID after a mark (#158)."""
    assert _tag(corpus_db, value) == (kept, True)


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 - or later OR MIT",
        "MIT AND GPL-2.0 - or later AND Apache-2.0",
        "MIT - or later OR ISC",
    ],
)
def test_a_dashed_grant_ends_the_expression_of_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """As the plain grant does: operands after it would be lost (it was
    GPL-2.0-or-later, exact, with MIT or Apache-2.0 dropped)."""
    plain = value.replace(" - ", " ")
    assert _tag(corpus_db, plain) is None
    assert _tag(corpus_db, value) is None
    assert resolve(value, corpus_db)["expression"] is not None


@pytest.mark.parametrize("value", ["MIT - OR ISC", "MIT -- AND ISC"])
def test_a_dash_before_an_operator_is_no_gap_of_the_expression(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    """A dash is crossed only before a grant (D10), never before AND or OR."""
    # BUG: the tag drops the operator and what follows (tech-debt-roadmap.md
    # item 46); it must not read them as an expression either.
    assert _tag(corpus_db, value) == ("MIT", True)
    assert _field(corpus_db, tmp_path, value) is None


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 - - or later",
        "GPL-2.0 (- or later)",
        "GPL-2.0 [-or later]",
        "(GPL-2.0)-or later",  # a dash with no white space: no separator
    ],
)
def test_more_than_a_dash_between_words_is_refused_everywhere(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    """One rule of the gap (``classify.grant_head``): it was GPL-2.0-or-later
    in resolve() alone."""
    assert resolve(value, corpus_db)["expression"] is None
    assert _tag(corpus_db, value) is None
    assert _field(corpus_db, tmp_path, value) is None


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("(GPL-2.0 - or later)", "GPL-2.0-or-later"),
        ("MIT OR (GPL-2.0 - or later)", "GPL-2.0-or-later OR MIT"),
    ],
)
def test_a_dashed_grant_in_brackets_reads_as_a_plain_one(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    given: GivenWarnings,
    value: str,
    answer: str,
) -> None:
    assert resolve(value, corpus_db)["expression"] == answer
    assert _tag(corpus_db, value) == (answer, True)
    assert _field(corpus_db, tmp_path, value) == answer
    assert given.conditions() <= {"variant not stated"}

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterisation pins for the second review of the contract batch of
0.7.0 (findings S1 to S7, 2026-11-02), on the whole 3.29.0 List.

Each pin records what the branch did when the review found it; a later
commit flips it to the new answer and names the decision (P169 on).
"""
# pylint: disable=missing-function-docstring

import json
import sqlite3
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import DatabaseNotReadyError, LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.identifiers import disambiguate_deprecated_id


def _top(corpus_db: LicenseDatabase, text: str) -> tuple[str, bool] | None:
    found = LicenseDetector(corpus_db.location).detect(text)
    return (found[0]["expression"], found[0]["exact"]) if found else None


# --- S1: a prose qualifier wins a compound ------------------------------------


@pytest.mark.parametrize(
    ("value", "answer", "field"),
    [
        ("LicenseRef-Proprietary AND GPL-2.0 only", "GPL-2.0-only", "GPL-2.0-only"),
        ("MIT AND GPL-2.0 only", "GPL-2.0-only", "GPL-2.0-only"),
        (
            "Apache-2.0 OR GPL-2.0 or later",
            "GPL-2.0-or-later",
            "Apache-2.0 OR GPL-2.0-or-later",  # the field's own reader
        ),
        (
            "BSD-3-Clause AND LGPL-2.1 or later",
            "LGPL-2.1-or-later",
            "BSD-3-Clause AND LGPL-2.1-or-later",
        ),
        ("LGPL-2.1+ AND GPL-2.0 only", "GPL-2.0-only", "GPL-2.0-only"),
        ("LicenseRef-GPL-2.0 or later", "GPL-2.0-or-later", "GPL-2.0-or-later"),
    ],
)
def test_s1_a_qualified_id_drops_the_other_operands(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, answer: str, field: str
) -> None:
    """S1, BUG: the prose reader read the whole value, so one qualified ID
    answered the compound, exact, from an argument and a manifest field."""
    assert disambiguate_deprecated_id(value) == answer
    assert _top(corpus_db, value) == (answer, True)
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"license": value}), encoding="utf-8")
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    assert (found[0]["expression"], found[0]["exact"]) == (field, True)


# --- S2: a "+" after a deprecated -with- ID ----------------------------------


def test_s2_a_with_id_and_a_plus_is_answered_as_written(
    corpus_db: LicenseDatabase,
) -> None:
    """S2, BUG: ``GPL-2.0-with-classpath-exception+`` answered itself, a
    deprecated ID, exact."""
    for text in (
        "GPL-2.0-with-classpath-exception+",
        "SPDX-License-Identifier: GPL-2.0-with-classpath-exception+",
    ):
        assert _top(corpus_db, text) == ("GPL-2.0-with-classpath-exception+", True)


# --- S4: a tag that states its qualifier twice --------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("LGPL-2.1+ only", "LGPL-2.1-or-later"),
        ("GPL-2.0+ or later", "GPL-2.0-or-later"),
    ],
)
def test_s4_a_tag_reads_a_qualifier_stated_twice(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    """S4, BUG: the tag answered, exact, where ``match()`` refuses
    (``qualifier stated twice``) and the argument finds none."""
    assert _top(corpus_db, f"SPDX-License-Identifier: {value}") == (answer, True)


# --- S7: a "+" before an end mark ------------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GPL-2.0+,", ("GPL-2.0-only", False)),
        ("GPL-2.0+.", ("GPL-2.0-only", False)),
        ("Apache-2.0+,", ("Apache-2.0", True)),
    ],
)
def test_s7_a_plus_before_an_end_mark_is_lost(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool]
) -> None:
    """S7, BUG: the argument lost the "+" before a comma or full stop (the
    tag and ``match()`` read ``GPL-2.0-or-later``)."""
    assert _top(corpus_db, value) == answer


# --- S6: LicenseDatabase("") ------------------------------------------------


def test_s6_a_blank_database_path_fails_in_sqlite() -> None:
    """S6, BUG: ``LicenseDatabase("")`` raised a raw sqlite3 error, and
    ``create=False`` named the working directory as unreadable."""
    with pytest.raises(sqlite3.OperationalError):
        LicenseDatabase("")
    with pytest.raises(DatabaseNotReadyError, match="unreadable"):
        LicenseDatabase("", create=False)

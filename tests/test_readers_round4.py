# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, fourth round: what round 3 refused that it must not,
on the whole 3.29.0 List (every ID a row, Intel, Nokia and Ruby too).

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.types import Detection

Answer = tuple[str, bool] | None


def _top(found: list[Detection]) -> Answer:
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _text(corpus_db: LicenseDatabase, value: str) -> Answer:
    return _top(LicenseDetector(corpus_db.location).detect(text=value))


def _file(corpus_db: LicenseDatabase, tmp_path: Path, content: str) -> Answer:
    path = tmp_path / "notice.c"
    path.write_text(content, "utf-8")
    return _top(LicenseDetector(corpus_db.location).detect(file_path=str(path)))


# --- 1: a word that is also an ID, in prose beside a granted ID ----------------

PROSE = {
    # BUG: no answer; it was exact on 90e89fb (Intel, Nokia, fair, doc,
    # Ruby, curl are IDs of the List, and plain words here).
    "Copyright Intel Corp. GPL-2.0 or later": None,
    "(c) Nokia 2009, LGPL-2.1 or any later version": None,
    "Distributed under GPL-3.0 or later; fair use applies": None,
    "GPL-2.0 only, see the doc folder": None,
    "GPL-2.0 or later, the same as Ruby": None,
    "LGPL-2.1 or later (see LICENSE). Uses curl.": None,
}


@pytest.mark.parametrize("value", sorted(PROSE))
def test_an_id_word_in_prose(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    answer = PROSE[value]
    assert (_text(corpus_db, value), _file(corpus_db, tmp_path, value)) == (
        answer,
        answer,
    )


def test_an_id_word_in_a_header(corpus_db: LicenseDatabase, tmp_path: Path) -> None:
    header = "// Copyright 2015 Intel Corporation\n// Licensed under GPL-2.0 or later\n"
    assert _file(corpus_db, tmp_path, header) is None  # BUG


@pytest.mark.parametrize(
    "value",
    ["Copyright Intel Corp. GPL-2.0 or later", "GPL-2.0 or later, the same as Ruby"],
)
def test_an_id_word_in_prose_is_spdx(corpus_db: LicenseDatabase, value: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "is-spdx", "--text", value]
    )
    assert result.exit_code == 1  # BUG: it names GPL-2.0-or-later


# A licence listed beside the granted one is still refused, as match() does:
# no exact answer (one with "and" goes on to the text tiers, not exact).
LISTED = [
    "GPL-3.0, LGPL-2.1 or later",
    "LGPL-2.1 or later, GPL-3.0",
    "MIT, GPL-2.0 or later",
    "GPL-2.0 or later; docs under the GFDL-1.3",
    "GPL-2.0 / LGPL-2.1 or later",
    "ISC and GPL-2.0 or later",
]


@pytest.mark.parametrize("value", LISTED)
def test_a_listed_licence_beside_a_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    for answer in (_text(corpus_db, value), _file(corpus_db, tmp_path, value)):
        assert answer is None or not answer[1]  # never the granted one, exact


# --- 2: a grant wrapped onto a comment line -------------------------------------

WRAPPED = {
    "/*\n * Licensed under GPL-2.0\n * or (at your option) any later version.\n */\n": (
        None  # BUG: it was GPL-2.0-or-later, exact, on 90e89fb
    ),
    "# This file is GPL-2.0\n# or any later version\n": None,  # BUG
    "// GPL-2.0\n// or later\n": None,  # BUG
}


@pytest.mark.parametrize("content", sorted(WRAPPED), ids=["block", "hash", "slash"])
def test_a_grant_wrapped_onto_a_comment_line(
    corpus_db: LicenseDatabase, tmp_path: Path, content: str
) -> None:
    assert _file(corpus_db, tmp_path, content) == WRAPPED[content]

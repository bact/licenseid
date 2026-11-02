# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A short input answers by what it names or what it is, not by a word it
shares with a licence.

``Foo`` answered 3D-Slicer-1.0 by text at 1.0 (coverage 0.0006) on the
3.29.0 list, and ``the`` MirOS by name at 1.0: a word found inside a long
licence text, or inside a name, scored as a perfect match. The rows below
are real licences with their real texts and names (the fixtures), so the
near neighbours that gave those answers are here: a database without texts
would answer nothing and pass for the wrong reason.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.types import Detection

FIXTURES = Path(__file__).parent / "fixtures" / "license-text-long"

# Each a real licence: the near neighbours of the inputs below on the
# 3.29.0 list (the names holding "the", "gpl" and "license", the texts
# holding "foo" and "this program is free software").
IDS = (
    "0BSD",
    "AGPL-3.0-only",
    "AML",
    "Apache-1.0",
    "Apache-1.1",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-SA-2.1-JP",
    "CDDL-1.0",
    "CDDL-1.1",
    "CNRI-Python-GPL-Compatible",
    "FSFAP",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "HPND",
    "ISC",
    "Interbase-1.0",
    "LGPL-2.1-only",
    "LGPL-3.0-only",
    "MIT",
    "MIT-0",
    "MirOS",
    "MulanPSL-1.0",
    "MulanPSL-2.0",
    "PHP-3.0",
    "PHP-3.01",
    "Parity-7.0.0",
    "Unlicense",
    "WTFPL",
)


def fixture(license_id: str) -> dict[str, str]:
    data = json.loads((FIXTURES / f"{license_id}.json").read_text(encoding="utf-8"))
    return {"name": str(data["name"]), "text": str(data["license_text"])}


def head(license_id: str, lines: int) -> str:
    """The first *lines* lines of a licence that are not blank."""
    kept = [line for line in fixture(license_id)["text"].splitlines() if line.strip()]
    return "\n".join(kept[:lines])


@pytest.fixture(scope="module")
def db_path() -> Generator[str, None, None]:
    rows = [
        Lic(
            lid,
            fixture(lid)["name"],
            search_text=normalize_text(fixture(lid)["text"]),
        )
        for lid in IDS
    ]
    # The deprecated ID that shares GPL-2.0-only's name, as on the list.
    rows.append(
        Lic(
            "GPL-2.0",
            "GNU General Public License v2.0 only",
            is_deprecated=True,
            search_text=normalize_text(fixture("GPL-2.0-only")["text"]),
        )
    )
    yield from seeded_db("test_shorttext_evidence", rows)


def detect(db_path: str, text: str) -> list[Detection]:
    return LicenseDetector(db_path).detect(text=text)


def answers(db_path: str, text: str) -> list[str]:
    """The answers at the CLI's default threshold."""
    return [r["expression"] for r in detect(db_path, text) if r["score"] >= 0.85]


# Words and phrases that occur in a licence text, none a licence.
TEXT_WORDS = [
    ("Foo", "PHP-3.0"),
    ("copyright notice", "GPL-2.0-only"),
    ("This program is free software", "GPL-2.0-only"),
    ("the software is provided as is", "0BSD"),
    ("日本語", "CC-BY-SA-2.1-JP"),
    ("许可证", "MulanPSL-1.0"),
]


@pytest.mark.parametrize(("text", "top"), TEXT_WORDS)
def test_a_word_inside_a_licence_text_scores_1(
    db_path: str, text: str, top: str
) -> None:
    # BUG: the word is aligned with the one window of a long licence that
    # holds it, a perfect similarity, and a fragment has no coverage
    # penalty: the answer is a licence by text at 1.0.
    results = detect(db_path, text)
    assert results[0]["expression"] == top
    assert results[0]["method"] == "text"
    assert results[0]["score"] == 1.0
    assert results[0]["coverage"] is not None and results[0]["coverage"] < 0.06


# Words of a licence name that name no licence.
NAME_WORDS = [
    ("the", "MirOS"),
    ("GPL", "CNRI-Python-GPL-Compatible"),
    ("license", "0BSD"),
    ("software", "MulanPSL-1.0"),
    ("GNU General Public License", "AGPL-3.0-only"),
    ("Apache License", "Apache-1.0"),
]


@pytest.mark.parametrize(("text", "top"), NAME_WORDS)
def test_a_word_of_a_name_scores_1(db_path: str, text: str, top: str) -> None:
    # BUG: a name that holds every word of the input scores 100 by token
    # set, plus the flex bonus: a definitive Tier 0 hit.
    results = detect(db_path, text)
    assert results[0]["expression"] == top
    assert results[0]["method"] == "name"
    assert results[0]["score"] == 1.0


def test_a_name_that_holds_the_input_is_shown_at_1(db_path: str) -> None:
    # BUG: beside the exact name, a name that holds the words of "MIT
    # License" is listed at 1.0 too (on 3.29.0, AML and 16 more).
    results = detect(db_path, "MIT License")
    assert [(r["expression"], r["exact"], r["score"]) for r in results] == [
        ("MIT", True, 1.0),
        ("AML", False, 1.0),
    ]


def test_the_predicates_judge_a_word(db_path: str) -> None:
    # BUG: is_spdx() answers True for Foo: it judges PHP-3.0.
    assert LicenseDetector(db_path).is_spdx(text="Foo") is True


@pytest.mark.parametrize(("command", "status"), [("detect", 0), ("is-osi", 1)])
def test_the_cli_judges_a_word(db_path: str, command: str, status: int) -> None:
    # BUG: a word that names no licence is judged as PHP-3.0 (not OSI
    # approved: is-osi's "no" is about PHP-3.0).
    result = CliRunner().invoke(cli, ["--db", db_path, command, "Foo"])
    assert result.exit_code == status
    assert result.stdout.startswith("EXPRESSION=PHP-3.0\t")


# A short input that names a licence, or is the start of one: the top
# answer, how it was found, and that it passes the CLI's threshold.
KEPT = [
    ("MIT", "MIT", "id"),
    ("Apache 2", "Apache-2.0", "id"),
    ("MIT License", "MIT", "name"),
    ("Licensed under the MIT License", "MIT", "name"),
    # A name with a word left out, which only one name holds.
    ("GNU Public License v2.0 only", "GPL-2.0-only", "name"),
    ("Interbase License v1.0", "Interbase-1.0", "name"),
    # The two title lines of GPL-3.0: 49 characters.
    (head("GPL-3.0-only", 2), "GPL-3.0-only", "text"),
    (head("GPL-3.0-only", 5), "GPL-3.0-only", "text"),
    (head("Apache-2.0", 10), "Apache-2.0", "text"),
    (head("BSD-3-Clause", 5), "BSD-3-Clause", "text"),
    # Japanese and Chinese: no spaces, and few characters say much.
    (head("CC-BY-SA-2.1-JP", 1), "CC-BY-SA-2.1-JP", "text"),
    (head("CC-BY-SA-2.1-JP", 2), "CC-BY-SA-2.1-JP", "text"),
    (head("MulanPSL-2.0", 2), "MulanPSL-2.0", "text"),
]


@pytest.mark.parametrize(("text", "top", "method"), KEPT, ids=lambda v: ascii(v)[:30])
def test_a_short_licence_input_keeps_its_answer(
    db_path: str, text: str, top: str, method: str
) -> None:
    results = detect(db_path, text)
    assert (results[0]["expression"], results[0]["method"]) == (top, method)
    assert results[0]["score"] >= 0.85


@pytest.mark.parametrize(
    "license_id", ["ISC", "0BSD", "MIT-0", "Unlicense", "WTFPL", "FSFAP"]
)
def test_a_one_paragraph_licence_is_exact(db_path: str, license_id: str) -> None:
    results = detect(db_path, fixture(license_id)["text"])
    assert (results[0]["expression"], results[0]["exact"]) == (license_id, True)
    assert results[0]["score"] == 1.0


def test_a_common_licence_phrase_answers_its_licences(db_path: str) -> None:
    """Eight words that open many BSD-style licences: a licence text, though
    not one licence. (The ties among them are in the order of the list.)"""
    assert "BSD-2-Clause" in answers(
        db_path, "Redistribution and use in source and binary forms"
    )

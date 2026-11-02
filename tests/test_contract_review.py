# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterisation pins for the review of the contract batch of 0.7.0
(findings R1 to R10, 2026-11-02).

Each pin records what the branch did when the review found it. A later
commit flips the pin to the new answer and names the decision (P159 on), so
this file is the before-and-after record of every changed behaviour.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import predicate_line
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import GPL2_ROWS, Lic, seeded_db

import licenseid
from licenseid import DatabaseNotReadyError, match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector

FRESH = "UPDATE db_metadata SET value = ? WHERE key = 'last_check_datetime'"
WITH_IDS = {
    "GPL-2.0-with-autoconf-exception": "GPL-2.0-only WITH Autoconf-exception-2.0",
    "GPL-2.0-with-bison-exception": "GPL-2.0-only WITH Bison-exception-2.2",
    "GPL-2.0-with-classpath-exception": "GPL-2.0-only WITH Classpath-exception-2.0",
    "GPL-2.0-with-font-exception": "GPL-2.0-only WITH Font-exception-2.0",
    "GPL-2.0-with-GCC-exception": "GPL-2.0-only WITH GCC-exception-2.0",
    "GPL-3.0-with-autoconf-exception": "GPL-3.0-only WITH Autoconf-exception-3.0",
    "GPL-3.0-with-GCC-exception": "GPL-3.0-only WITH GCC-exception-3.1",
}
EXCEPTIONS = sorted({value.split(" WITH ")[1] for value in WITH_IDS.values()})
ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text="mit licence text"),
    Lic("ISC", "ISC License", True, True, True),
    *GPL2_ROWS,
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only", True, True, True),
    Lic("GPL-3.0-or-later", "GNU General Public License v3.0 or later", True, True),
    *(Lic(lid, lid, True, is_deprecated=True) for lid in WITH_IDS),
)
COMMANDS = ("is-osi", "is-fsf", "is-spdx")


@pytest.fixture
def db() -> Generator[str, None, None]:
    for path in seeded_db("contract_review", ROWS, EXCEPTIONS):
        with sqlite3.connect(path, uri=True) as conn:  # no staleness warning
            conn.execute(FRESH, (datetime.now(timezone.utc).isoformat(),))
        yield path


def run(db: str, *args: str, stdin: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["--db", db, *args], input=stdin)


# --- R1: no record is no answer --------------------------------------------


def _inputs(tmp_path: Path, value: str) -> list[list[str]]:
    """*value* as an argument, ``--text`` and a file."""
    path = tmp_path / "LICENSE"
    path.write_text(value + "\n", encoding="utf-8")
    return [[value], ["--text", value], [str(path)]]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "value",
    [
        "MIT OR ISC",  # a bare compound: matched as text, no licence found
        "SPDX-License-Identifier: MIT WITH AdditionRef-x",  # no reader takes it
        "Not a licence at all",
    ],
)
def test_r1_no_record_answers_false(
    db: str, tmp_path: Path, command: str, value: str
) -> None:
    """R1, BUG: no record printed ``false``, a false "no"."""
    for args in _inputs(tmp_path, value):
        result = run(db, command, *args)
        assert (result.exit_code, result.stdout) == (
            1,
            predicate_line(command, "", False),
        ), args


@pytest.mark.parametrize("command", COMMANDS)
def test_r1_an_unknown_id_answers_false(db: str, command: str) -> None:
    """R1, BUG: ``--id Zzz-Unknown-1.0`` said ``false``."""
    result = run(db, command, "--id", "Zzz-Unknown-1.0")
    assert (result.exit_code, result.stdout) == (1, predicate_line(command, "", False))


@pytest.mark.parametrize("method", ["is_osi", "is_fsf", "is_spdx"])
def test_r1_the_api_answers_false(db: str, tmp_path: Path, method: str) -> None:
    """R1, BUG: the methods said False for no record."""
    path = tmp_path / "LICENSE"
    path.write_text("MIT OR ISC\n", encoding="utf-8")
    detector = LicenseDetector(db)
    assert getattr(detector, method)("MIT OR ISC") is False
    assert getattr(detector, method)(file_path=str(path)) is False
    assert getattr(detector, method)(license_id="Zzz-Unknown-1.0") is False


# --- R2: the deprecated -with- IDs are narrowed unsaid -----------------------


@pytest.mark.parametrize(("deprecated", "reading"), sorted(WITH_IDS.items()))
def test_r2_a_with_id_is_narrowed_unsaid(
    db: str, tmp_path: Path, deprecated: str, reading: str
) -> None:
    """R2, BUG: ``GPL-2.0-with-classpath-exception`` read as ``GPL-2.0-only
    WITH Classpath-exception-2.0``, exact and with no warning."""
    field = tmp_path / "package.json"
    field.write_text(f'{{"license": "{deprecated}"}}\n', encoding="utf-8")
    for args in (
        [deprecated],
        ["--id", deprecated],
        ["--text", f"SPDX-License-Identifier: {deprecated}"],
        [str(field)],
    ):
        result = run(db, "detect", "--json", *args)
        assert result.exit_code == 0, args
        assert f'"expression":"{reading}"' in result.stdout, args
        assert '"exact":true' in result.stdout, args
        assert result.stderr == "", args


# --- R3: a deprecated row without text loses its flags ------------------------
# Pinned in tests/test_records.py, which builds the rows.


# --- R4: clear-cache deletes what is not its own ------------------------------


def test_r4_clear_cache_deletes_files_beside_a_missing_database(
    tmp_path: Path,
) -> None:
    """R4, BUG: ``--db proj/typo.db clear-cache`` deleted the user's own
    ``licenses.json`` and ``popularity.csv`` in ``proj`` and said
    ``STATUS=cleared``."""
    proj = tmp_path / "proj"
    proj.mkdir()
    for name in ("licenses.json", "popularity.csv", "notes.txt"):
        (proj / name).write_text("mine\n", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", str(proj / "typo.db"), "clear-cache"])
    assert result.exit_code == 0
    assert "STATUS=cleared" in result.stdout
    assert sorted(path.name for path in proj.iterdir()) == ["notes.txt"]


# --- R5: a "+" read as a bare ID ------------------------------------------------


def test_r5_plus_or_only_drops_the_or_later_operand(db: str) -> None:
    """R5, BUG: the tag ``GPL-2.0+ OR GPL-2.0-only`` answered ``GPL-2.0-only``
    (the prose reader took ``GPL-2.0`` as bare and ``-only`` as its word)
    and warned that ``GPL-2.0`` was narrowed."""
    result = run(
        db,
        "detect",
        "--json",
        "--text",
        "SPDX-License-Identifier: GPL-2.0+ OR GPL-2.0-only",
    )
    assert '"expression":"GPL-2.0-only"' in result.stdout
    assert "variant not stated" in result.stderr


# --- R10: the Font-exception candidate of an unknown GPL version ------------

FONT_TEXT = (
    "This font is free software; you can redistribute it under the terms of"
    " the GNU General Public License version 4 as published by the Free"
    " Software Foundation. As a special exception, if you create a document"
    " which uses this font, and embed this font or unaltered portions of this"
    " font into the document, this font does not by itself cause the"
    " resulting document to be covered by the GNU General Public License."
)


def test_r10_an_unknown_gpl_version_gets_a_font_candidate(db: str) -> None:
    """R10, BUG: "version 4" with the font exception gave the candidate
    ``GPL-4.0-only WITH Font-exception-2.0``, an ID the List does not
    have, at the top of ``detect()``."""
    top = LicenseDetector(db).detect(FONT_TEXT)[0]
    assert top["expression"] == "GPL-4.0-only WITH Font-exception-2.0"
    assert (top["is_spdx"], top["is_osi_approved"]) == (False, None)


# --- R6: a warning on exit 1 -----------------------------------------------------


def test_r6_exit_1_can_carry_a_warning(db: str) -> None:
    """R6: ``detect --exact GPL-2.0`` exits 1 with the warning of its guess."""
    result = run(db, "detect", "--exact", "GPL-2.0")
    assert result.exit_code == 1
    assert result.stderr == (
        "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only\n"
    )


# --- R7: the inputs of licenseid.detect() ------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [{"text": 3}, {}, {"text": "MIT", "license_id": "MIT"}, {"text": "MIT", "x": 1}],
    ids=["not-str", "none", "two", "option"],
)
def test_r7_detect_reports_the_database_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object]
) -> None:
    """R7, BUG: with no default database, a wrong call raised
    DatabaseNotReadyError, not its own error."""
    monkeypatch.setenv("LICENSEID_DB", str(tmp_path / "none.db"))
    monkeypatch.setattr(
        "licenseid.keptdetector.get_default_db_path", lambda: str(tmp_path / "none.db")
    )
    with pytest.raises(DatabaseNotReadyError):
        licenseid.detect(**kwargs)  # type: ignore[arg-type]


# --- R9: a blank db ------------------------------------------------------------------


def test_r9_a_blank_db_is_read_as_a_path() -> None:
    """R9, BUG: ``match(value, db="")`` said ``database: unreadable: :
    disk I/O error``."""
    with pytest.raises(DatabaseNotReadyError, match="unreadable"):
        match("MIT", db="")

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

import re
import sqlite3
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import predicate_json, predicate_line
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db
from matcher_db import GPL2_ROWS, Lic, seeded_db
from packaged_list import database_of, synthetic_bundle

import licenseid
from licenseid import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseDatabase,
    keptdetector,
    match,
)
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.identifiers import disambiguate_deprecated_id
from licenseid.markers import MarkerDetector
from licenseid.types import SpdxLicenseEntry

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


# --- R1: no record is no answer (P159) ---------------------------------------


def _inputs(tmp_path: Path, value: str) -> list[tuple[list[str], str | None]]:
    """*value* as an argument, ``--text``, a file and standard input."""
    path = tmp_path / "LICENSE"
    path.write_text(value + "\n", encoding="utf-8")
    return [([value], None), (["--text", value], None), ([str(path)], None)] + [
        (["-"], value),
    ]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "value",
    [
        "MIT OR ISC",  # a bare compound: matched as text, no licence found
        "SPDX-License-Identifier: MIT WITH AdditionRef-x",  # no reader takes it
        "Not a licence at all",
    ],
)
def test_r1_no_record_is_no_answer(
    db: str, tmp_path: Path, command: str, value: str
) -> None:
    """R1 (was: ``EXPRESSION=\tIS_OSI_APPROVED=false``, a false "no"): no
    licence found leaves the flag empty, ``null`` in JSON, exit 1."""
    for args, stdin in _inputs(tmp_path, value):
        result = run(db, command, *args, stdin=stdin)
        assert (result.exit_code, result.stdout, result.stderr) == (
            1,
            predicate_line(command, "", None),
            "",
        ), args
        result = run(db, command, "--json", *args, stdin=stdin)
        assert result.stdout == predicate_json(command, None, None), args


@pytest.mark.parametrize("command", COMMANDS)
def test_r1_an_unknown_id_is_no_answer(db: str, command: str) -> None:
    """R1 (was: ``--id Zzz-Unknown-1.0`` said ``false``)."""
    result = run(db, command, "--id", "Zzz-Unknown-1.0")
    assert (result.exit_code, result.stdout) == (1, predicate_line(command, "", None))


@pytest.mark.parametrize(
    ("command", "args", "line"),
    [
        # A licence found keeps its "no".
        ("is-fsf", ["--id", "GPL-3.0-or-later"], ("GPL-3.0-or-later", False)),
        ("is-osi", ["--id", "MIT"], ("MIT", True)),
        # An operand that cannot be judged: the expression, an empty flag.
        (
            "is-osi",
            ["--text", "SPDX-License-Identifier: MIT AND LicenseRef-x"],
            ("MIT AND LicenseRef-x", None),
        ),
        (
            "is-spdx",
            ["--text", "SPDX-License-Identifier: MIT AND LicenseRef-x"],
            ("MIT AND LicenseRef-x", False),
        ),
    ],
)
def test_r1_a_licence_found_keeps_its_answer(
    db: str, command: str, args: list[str], line: tuple[str, bool | None]
) -> None:
    """R1, adversarial: only "not found" moved; a found licence says ``false``
    where the List says no."""
    result = run(db, command, *args)
    assert result.stdout == predicate_line(command, *line)
    assert result.exit_code == (0 if line[1] is True else 1)


@pytest.mark.parametrize("method", ["is_osi", "is_fsf", "is_spdx"])
def test_r1_the_api_says_none_for_no_licence(
    db: str, tmp_path: Path, method: str
) -> None:
    """R1 (was: False for no record): None, as the CLI's empty flag."""
    path = tmp_path / "LICENSE"
    path.write_text("MIT OR ISC\n", encoding="utf-8")
    detector = LicenseDetector(db)
    assert getattr(detector, method)("MIT OR ISC") is None
    assert getattr(detector, method)(file_path=str(path)) is None
    assert getattr(detector, method)(license_id="Zzz-Unknown-1.0") is None
    assert getattr(detector, method)(license_id="MIT") is True


# --- R2: the deprecated -with- IDs are a guess too (P160) --------------------


@pytest.mark.parametrize(("deprecated", "reading"), sorted(WITH_IDS.items()))
def test_r2_a_with_id_is_a_narrowed_guess_on_every_path(
    db: str, tmp_path: Path, deprecated: str, reading: str
) -> None:
    """R2 (was: ``GPL-2.0-with-classpath-exception`` read as ``GPL-2.0-only
    WITH Classpath-exception-2.0``, exact and with no warning): not exact,
    and the warning of every narrowed ID, from an argument, ``--id``, a tag,
    a manifest field and ``is-*`` alike."""
    field = tmp_path / "package.json"
    field.write_text(f'{{"license": "{deprecated}"}}\n', encoding="utf-8")
    warning = f"WARNING: input: variant not stated: {deprecated}; using {reading}\n"
    for args in (
        [deprecated],
        ["--id", deprecated],
        ["--text", f"SPDX-License-Identifier: {deprecated}"],
        [str(field)],
    ):
        result = run(db, "detect", "--json", *args)
        assert result.exit_code == 0, args
        assert f'"expression":"{reading}"' in result.stdout, args
        assert '"exact":false' in result.stdout, args
        assert result.stderr == warning, args
    result = run(db, "is-osi", "--id", deprecated)
    assert (result.stdout, result.stderr) == (
        predicate_line("is-osi", reading, True),
        warning,
    )


def test_r2_the_api_reads_a_with_id_as_not_exact(db: str) -> None:
    """R2: ``detect(license_id=...)`` says the guess too."""
    (top,) = LicenseDetector(db).detect(license_id="GPL-2.0-with-GCC-exception")
    assert (top["expression"], top["exact"]) == (
        "GPL-2.0-only WITH GCC-exception-2.0",
        False,
    )


# --- R3: a deprecated row without text keeps its flags (P162) -----------------
# The rows themselves: tests/test_records_rules.py.


def _entry(license_id: str, deprecated: bool, osi: bool, fsf: bool) -> SpdxLicenseEntry:
    return {
        "licenseId": license_id,
        "name": license_id,
        "isDeprecatedLicenseId": deprecated,
        "isOsiApproved": osi,
        "isFsfLibre": fsf,
    }


@pytest.mark.parametrize(
    ("command", "license_id", "answer"),
    [
        ("is-osi", "wxWindows", True),
        ("is-fsf", "wxWindows", True),
        ("is-osi", "eCos-2.0", False),
        ("is-fsf", "eCos-2.0", True),
        ("is-osi", "Nunit", False),
    ],
)
def test_r3_a_deprecated_id_without_text_has_its_flags(
    tmp_path: Path, command: str, license_id: str, answer: bool
) -> None:
    """R3 (was: ``is-osi --id wxWindows`` false, ``is-fsf --id eCos-2.0``
    false, though the List says true): a database built by ``update``
    answers with the List's flags."""
    entries = [
        _entry("MIT", False, True, True),
        _entry("wxWindows", True, True, True),
        _entry("eCos-2.0", True, False, True),
        _entry("Nunit", True, False, False),
    ]
    raw = synthetic_bundle(entries, {"MIT": "MIT licence text"})
    path = database_of(raw, tmp_path / "licenses.db").db_path
    result = run(str(path), command, "--id", license_id)
    assert result.stdout == predicate_line(command, license_id, answer)


# --- R4: clear-cache deletes only its own cache (P163) -------------------------
# Every shape: tests/test_clear_cache.py.


def test_r4_clear_cache_keeps_the_files_beside_a_missing_database(
    tmp_path: Path,
) -> None:
    """R4 (was: ``--db proj/typo.db clear-cache`` deleted the user's own
    ``licenses.json`` and ``popularity.csv`` in ``proj`` and said
    ``STATUS=cleared``): the reviewer's reproducer."""
    proj = tmp_path / "proj"
    proj.mkdir()
    for name in ("licenses.json", "popularity.csv", "notes.txt"):
        (proj / name).write_text("mine\n", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", str(proj / "typo.db"), "clear-cache"])
    assert result.exit_code == 0
    assert result.stdout == f"STATUS=nothing\tPATH={proj / 'typo.db'}\n"
    assert sorted(path.name for path in proj.iterdir()) == [
        "licenses.json",
        "notes.txt",
        "popularity.csv",
    ]


# --- R5: a "+" is no bare ID (P161) --------------------------------------------


@pytest.mark.parametrize(
    ("value", "expression", "warned"),
    [
        ("GPL-2.0+ OR GPL-2.0-only", "GPL-2.0-only OR GPL-2.0-or-later", False),
        ("GPL-2.0-only OR GPL-2.0+", "GPL-2.0-only OR GPL-2.0-or-later", False),
        ("GPL-2.0+ AND GPL-2.0-only", "GPL-2.0-only AND GPL-2.0-or-later", False),
        ("GPL-2.0 OR GPL-2.0-or-later", "GPL-2.0-only OR GPL-2.0-or-later", True),
        ("GPL-2.0+ OR GPL-2.0", "GPL-2.0-only OR GPL-2.0-or-later", True),
    ],
)
def test_r5_a_plus_keeps_its_operand(
    db: str, value: str, expression: str, warned: bool
) -> None:
    """R5 (was: the tag ``GPL-2.0+ OR GPL-2.0-only`` answered ``GPL-2.0-only``,
    the prose reader taking ``GPL-2.0`` as bare and the ``-only`` of the
    next ID as its word, and warned that ``GPL-2.0`` was narrowed): every
    operand is kept, and only a bare ID warns."""
    result = run(db, "detect", "--json", "--text", f"SPDX-License-Identifier: {value}")
    assert f'"expression":"{expression}"' in result.stdout
    assert f'"exact":{str(not warned).lower()}' in result.stdout
    assert ("variant not stated" in result.stderr) is warned


def test_r5_a_bare_compound_argument_is_no_id(db: str) -> None:
    """R5 (was: the argument ``GPL-2.0+ OR GPL-2.0-only`` answered
    ``GPL-2.0-only``, METHOD=id, exact): a compound given as text is no
    declaration (P141), so no licence is found."""
    result = run(db, "detect", "GPL-2.0+ OR GPL-2.0-only")
    assert result.exit_code == 1


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("GPL-2.0 only", "GPL-2.0-only"),
        ("licensed under GPL-2.0. This version only.", "GPL-2.0-only"),
        ("GPL-2.0+ or later", None),
        ("GPL-2.0+ OR GPL-2.0-only", None),
        ("GPL-2.0-only", None),
        ("GPL-2.0 OR GPL-2.0-only", None),
    ],
)
def test_r5_the_prose_reader_skips_what_an_id_states(
    text: str, answer: str | None
) -> None:
    """R5: ``disambiguate_deprecated_id`` reads a bare ID and a phrase; the
    "+" and the "-only" of an ID are not prose."""
    assert disambiguate_deprecated_id(text) == answer


# --- R6: exit 1 prints no ERROR line, and may warn (P164) ----------------------


@pytest.mark.parametrize(
    ("args", "stderr"),
    [
        (
            ["detect", "--exact", "GPL-2.0"],
            "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only\n",
        ),
        (["detect", "Not a licence at all"], ""),
        (["is-osi", "Not a licence at all"], ""),
        (["match", "Foo"], ""),
    ],
)
def test_r6_exit_1_carries_no_error_line(db: str, args: list[str], stderr: str) -> None:
    """R6: "no" is an answer, so exit 1 prints no ERROR line; the warning
    of a guess (``GPL-2.0`` read as ``GPL-2.0-only``) is said as with an
    answer."""
    result = run(db, *args)
    assert (result.exit_code, result.stderr) == (1, stderr)


# --- R7: licenseid.detect() checks the call before the database (P165) --------


@pytest.mark.parametrize(
    "case",
    [
        ({"text": 3}, TypeError, "text must be str, not int"),
        ({"license_id": b"MIT"}, TypeError, "license_id must be str, not bytes"),
        ({}, InvalidInputError, "input: missing"),
        ({"text": "MIT", "license_id": "MIT"}, InvalidInputError, "with license_id"),
        ({"text": "MIT", "x": 1}, InvalidInputError, "option: invalid: 'x'"),
        ({"x": 1}, InvalidInputError, "option: invalid: 'x'"),  # the option first
    ],
    ids=["not-str", "bytes-id", "none", "two", "option", "option-first"],
)
@pytest.mark.parametrize("database", [False, True], ids=["no-db", "db"])
def test_r7_detect_checks_the_call_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[dict[str, object], type[Exception], str],
    database: bool,
) -> None:
    """R7 (was: with no default database, a wrong call raised
    DatabaseNotReadyError, not its own error): the call is checked as
    ``match()`` checks its value, before any database is opened."""
    path = tmp_path / "licenses.db"
    if database:
        make_ready_file_db(path)
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: str(path))
    keptdetector.reset()
    kwargs, error, message = case
    with pytest.raises(error, match=re.escape(message)):
        licenseid.detect(**kwargs)  # type: ignore[arg-type]


def test_r7_a_good_call_still_needs_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R7, adversarial: the check moved, the database is still asked for."""
    monkeypatch.setattr(
        "licenseid.keptdetector.get_default_db_path", lambda: str(tmp_path / "x.db")
    )
    keptdetector.reset()
    with pytest.raises(DatabaseNotReadyError, match="not found"):
        licenseid.detect("MIT")


# --- R9: a blank db is refused (P166) -------------------------------------------


@pytest.mark.parametrize("blank", ["", "  ", "\t\n"], ids=["empty", "spaces", "ws"])
def test_r9_match_refuses_a_blank_db(blank: str) -> None:
    """R9 (was: ``match(value, db="")`` said ``database: unreadable: :
    disk I/O error``): a usage error, worded as the CLI's ``--db ""``."""
    with pytest.raises(
        InvalidInputError, match="^database: missing: db; pass a path or drop db$"
    ):
        match("MIT", db=blank)


def test_r9_the_detector_refuses_a_blank_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R9: ``LicenseDetector("")`` read the default database, a file the
    caller did not name; None still means the default."""
    with pytest.raises(InvalidInputError, match="^database: missing: db_path;"):
        LicenseDetector("")
    path = make_ready_file_db(tmp_path / "licenses.db")
    monkeypatch.setattr("licenseid.detector.get_default_db_path", lambda: str(path))
    assert LicenseDetector(None).db.db_path == path


def test_r9_the_cli_refuses_a_blank_db_as_before() -> None:
    result = CliRunner().invoke(cli, ["--db", "", "match", "MIT"])
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: database: missing: --db; pass a path or drop --db\n",
    )


# --- R10: the Font-exception candidate of an unknown GPL version ------------

FONT_TEXT = (
    "This font is free software; you can redistribute it under the terms of"
    " the GNU General Public License version 4 as published by the Free"
    " Software Foundation. As a special exception, if you create a document"
    " which uses this font, and embed this font or unaltered portions of this"
    " font into the document, this font does not by itself cause the"
    " resulting document to be covered by the GNU General Public License."
)


def test_r10_an_unknown_gpl_version_gets_no_font_candidate(db: str) -> None:
    """R10 (P167; was: "version 4" with the font exception gave
    ``GPL-4.0-only WITH Font-exception-2.0``, an ID the List does not have,
    at the top of ``detect()``): no licence, as without the exception."""
    found = LicenseDetector(db).detect(FONT_TEXT)
    assert all("GPL-4.0" not in r["expression"] for r in found)
    markers = MarkerDetector(LicenseDatabase(db, create=False))
    assert [c["license_id"] for c in markers.detect(FONT_TEXT)] == []


@pytest.mark.parametrize(
    ("exceptions", "flags"),
    [
        (EXCEPTIONS, (True, True, True)),
        ([], (False, True, True)),  # the exception is not on this List
    ],
    ids=["listed", "unlisted"],
)
def test_r10_a_font_candidate_takes_the_flags_of_its_expression(
    exceptions: list[str], flags: tuple[bool, bool, bool]
) -> None:
    """R10: the candidate's flags are those ``license_flags`` gives the
    expression (``exprflags``): the licence's, on the List only when the
    exception is too."""
    text = FONT_TEXT.replace("version 4", "version 2")
    for path in seeded_db("contract_review_font", ROWS, exceptions):
        markers = MarkerDetector(LicenseDatabase(path, create=False))
        (found,) = [c for c in markers.detect(text) if "Font" in c["license_id"]]
        assert found["license_id"] == "GPL-2.0-only WITH Font-exception-2.0"
        assert (
            found["is_spdx"],
            found["is_osi_approved"],
            found["is_fsf_libre"],
        ) == flags

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The warnings licenseid gives, as the CLI prints them and as the library
gives them, and the lists a detection carries."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import invoke_match
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db, writer
from matcher_db import Lic, seeded_db
from resolve_states import OUTDATED_WARNING

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.textinput import decode_input

ROWS = [
    Lic("GPL-2.0", "GNU General Public License v2.0 only", is_deprecated=True),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("LGPL-2.1", "GNU Lesser General Public License v2.1 only", is_deprecated=True),
    Lic("LGPL-2.1-only", "GNU Lesser General Public License v2.1 only"),
    Lic("LGPL-2.1-or-later", "GNU Lesser General Public License v2.1 or later"),
    Lic("MIT", "MIT License"),
]
TWO_TAGS = (
    "SPDX-License-Identifier: GPL-2.0\n/* x */\nSPDX-License-Identifier: LGPL-2.1\n"
)
STALE = re.compile(r"WARNING: database: \d+ days old; run 'licenseid update'")
NARROWED = "WARNING: input: variant not stated: {}; using {}\n"
DETECTION_KEYS = {
    "coverage",
    "exact",
    "expression",
    "is_fsf_libre",
    "is_osi_approved",
    "is_spdx",
    "method",
    "score",
    "similarity",
}


@pytest.fixture
def memory_db() -> Generator[str, None, None]:
    yield from seeded_db("test_library_warnings", ROWS)


@pytest.fixture
def outdated_db(tmp_path: Path) -> Path:
    """A ready file database stamped with an older build."""
    path = make_ready_file_db(tmp_path / "old.db")
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '1' WHERE key = 'build_version'")
    return path


# --- The CLI: one line per warning, as before -------------------------------


def test_cli_prints_two_tag_warnings_in_one_run(memory_db: str, tmp_path: Path) -> None:
    source = tmp_path / "two.c"
    source.write_text(TWO_TAGS, encoding="utf-8")
    result = invoke_match(memory_db, str(source))
    assert result.exit_code == 0
    # The CLI's own warning first (the seeded database was checked long ago),
    # then the library's, in the order they were given.
    stale, rest = result.stderr.split("\n", 1)
    assert STALE.fullmatch(stale)
    assert rest == NARROWED.format("GPL-2.0", "GPL-2.0-only") + NARROWED.format(
        "LGPL-2.1", "LGPL-2.1-only"
    )


def test_cli_prints_the_outdated_database(outdated_db: Path) -> None:
    for command in (["detect", "--id", "MIT"], ["match", "MIT"]):
        result = CliRunner().invoke(cli, ["--db", str(outdated_db), *command])
        assert result.exit_code == 0, result.output
        assert result.stderr == OUTDATED_WARNING


def test_cli_prints_latin1_input(memory_db: str, tmp_path: Path) -> None:
    source = tmp_path / "latin.txt"
    source.write_bytes(b"MIT caf\xe9\n")
    result = invoke_match(memory_db, str(source))
    stale, rest = result.stderr.split("\n", 1)
    assert STALE.fullmatch(stale)
    assert rest == f"WARNING: input: not UTF-8, read as Latin-1: {source}\n"


def test_cli_detect_json_keys(memory_db: str) -> None:
    result = invoke_match(memory_db, "--json", "--id", "MIT")
    assert set(json.loads(result.stdout)) == DETECTION_KEYS
    result = invoke_match(memory_db, "--json", "--text", "nothing at all here")
    assert result.exit_code == 1
    assert json.loads(result.stdout) == dict.fromkeys(DETECTION_KEYS)


# --- The library: pins of 0.7.0's C0, where a warning went to stderr --------


def test_pin_the_library_writes_an_outdated_database_to_stderr(
    outdated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    LicenseDetector(str(outdated_db))
    assert capsys.readouterr().err == OUTDATED_WARNING


def test_pin_report_collects_the_database_warning(outdated_db: Path) -> None:
    said: list[str] = []
    LicenseDatabase(str(outdated_db), create=False, report=said.append)
    assert said == [OUTDATED_WARNING.removeprefix("WARNING: ").rstrip("\n")]


def test_pin_the_library_writes_a_narrowed_tag_to_stderr(
    memory_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    results = LicenseDetector(memory_db).detect(text=TWO_TAGS)
    assert [r["expression"] for r in results] == ["GPL-2.0-only", "LGPL-2.1-only"]
    assert capsys.readouterr().err == NARROWED.format(
        "GPL-2.0", "GPL-2.0-only"
    ) + NARROWED.format("LGPL-2.1", "LGPL-2.1-only")


def test_pin_the_library_writes_latin1_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert decode_input(b"caf\xe9", "LICENSE") == "caf\xe9"
    assert capsys.readouterr().err == (
        "WARNING: input: not UTF-8, read as Latin-1: LICENSE\n"
    )


def test_pin_a_detection_has_no_lists(memory_db: str) -> None:
    (result,) = LicenseDetector(memory_db).detect(license_id="MIT")
    assert set(result) == DETECTION_KEYS

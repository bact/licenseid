# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The commands and a ``/`` between licence IDs (roadmap item 43)."""
# pylint: disable=missing-function-docstring

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from matcher_db import Lic, seeded_db

from licenseid.cli import cli

ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text="mit license"),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True, search_text="apache"),
    Lic("ISC", "ISC License", True, True, True, search_text="isc license"),
)


@pytest.fixture(name="db_path")
def _db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_slash_cli", ROWS)


def run(db_path: str, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["--db", db_path, *args])
    return result.exit_code, result.stdout, result.stderr


@pytest.mark.terse_cli
@pytest.mark.parametrize("command", ["detect", "resolve"])
@pytest.mark.parametrize("value", ["MIT/Apache-2.0", "Apache-2.0/MIT"])
def test_the_expression_is_the_answer(db_path: str, command: str, value: str) -> None:
    code, out, _ = run(db_path, command, value)
    assert (code, out) == (0, "Apache-2.0 OR MIT\n")


def test_the_record_says_why(db_path: str) -> None:
    code, out, _ = run(db_path, "resolve", "--verbose", "MIT/Apache-2.0")
    assert code == 0
    assert out.splitlines()[0].startswith("EXPRESSION=Apache-2.0 OR MIT\t")
    assert "STEP=separator\tFROM=MIT/Apache-2.0\tTO=MIT OR Apache-2.0\n" in out


def test_detect_agrees_with_resolve(db_path: str) -> None:
    code, out, _ = run(db_path, "detect", "--json", "MIT/ISC")
    assert code == 0
    assert '"expression":"ISC OR MIT"' in out


def test_a_predicate_answers_for_the_expression(db_path: str) -> None:
    assert run(db_path, "is-osi", "MIT/Apache-2.0")[0] == 0
    assert run(db_path, "is-spdx", "MIT/Apache-2.0")[0] == 0


@pytest.mark.terse_cli
@pytest.mark.parametrize("value", ["zlib/libpng", "mit/apache-2.0", "MIT/X11"])
def test_a_value_that_is_refused_answers_no_licence(db_path: str, value: str) -> None:
    assert run(db_path, "resolve", value)[:2] == (1, "\n")


def test_id_declares_one_licence(db_path: str) -> None:
    code, out, err = run(db_path, "detect", "--id", "MIT/Apache-2.0")
    assert (code, out) == (2, "")
    assert err.splitlines()[-1].startswith("ERROR: ")


@pytest.mark.parametrize("command", ["detect", "is-osi"])
def test_a_path_shaped_value_is_still_refused(db_path: str, command: str) -> None:
    code, out, err = run(db_path, command, "LICENSE/MIT")
    assert (code, out) == (2, "")
    assert err.splitlines()[-1] == "ERROR: input: not found: LICENSE/MIT; pass --text"


def test_a_file_named_like_the_value_is_read_as_a_file(
    db_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "MIT").mkdir()
    (tmp_path / "MIT" / "ISC").write_text("SPDX-License-Identifier: Apache-2.0\n")
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(db_path, "detect", "-v", "MIT/ISC")
    assert code == 0
    assert out.startswith("EXPRESSION=Apache-2.0\t")

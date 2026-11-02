# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A home variable set to nothing is no home, on every Python version."""

# pylint: disable=missing-function-docstring

import types
from pathlib import Path

import pytest
from click.testing import CliRunner

from licenseid import datadir
from licenseid.cli import cli
from licenseid.errors import DatabaseNotReadyError

NO_HOME = "ERROR: database: not found: no home directory; pass --db\n"
BLANKS = ["", " ", "\t \t"]


@pytest.mark.parametrize("value", BLANKS)
def test_a_blank_home_is_no_home_with_the_real_path_home(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Python 3.10 reads an empty HOME as '/', which is absolute."""
    monkeypatch.setenv("HOME", value)
    monkeypatch.setenv("USERPROFILE", value)
    with pytest.raises(DatabaseNotReadyError, match="no home directory") as raised:
        datadir.get_default_db_path()
    assert (raised.value.condition, raised.value.detail) == (
        "not found",
        "no home directory",
    )


@pytest.mark.parametrize("value", BLANKS)
def test_the_cli_reports_a_blank_home_as_a_usage_line(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("HOME", value)
    monkeypatch.setenv("USERPROFILE", value)
    result = CliRunner().invoke(cli, ["detect", "MIT"])
    assert (result.exit_code, result.stdout, result.stderr) == (2, "", NO_HOME)


@pytest.mark.parametrize(
    ("platform", "blank", "set_to"),
    [("linux", "HOME", "USERPROFILE"), ("win32", "USERPROFILE", "HOME")],
)
def test_only_the_variable_this_platform_reads_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    blank: str,
    set_to: str,
) -> None:
    """Windows ignores HOME, so a blank HOME there is not a missing home."""
    monkeypatch.setattr(datadir, "sys", types.SimpleNamespace(platform=platform))
    monkeypatch.setenv(blank, "")
    monkeypatch.setenv(set_to, "")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    with pytest.raises(DatabaseNotReadyError):
        datadir.get_default_db_path()
    monkeypatch.setenv(blank, str(tmp_path))
    assert datadir.get_default_db_path().startswith(str(tmp_path))


def test_an_unset_home_variable_is_left_to_path_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert datadir.get_default_db_path().startswith(str(tmp_path))

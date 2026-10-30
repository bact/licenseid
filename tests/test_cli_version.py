# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid --version``: the version on standard output, before any
database is looked up."""
# pylint: disable=missing-function-docstring

from unittest import mock

import pytest
from click.testing import CliRunner

import licenseid
from licenseid import console, output
from licenseid.cli import cli
from licenseid.cli import main as cli_main


@pytest.mark.parametrize(
    "argv",
    [
        ["--version"],
        ["--db", "/nonexistent/x.db", "--version"],
        ["--version", "match"],
        ["--version", "--help"],  # eager, as click's own: first one wins
    ],
    ids=["bare", "db", "before-command", "before-help"],
)
def test_version_prints_and_opens_nothing(argv: list[str]) -> None:
    with mock.patch("licenseid.cli.get_default_db_path", autospec=True) as default:
        result = CliRunner().invoke(cli, argv)
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        f"licenseid {licenseid.__version__}\n",
        "",
    )
    default.assert_not_called()


def test_version_that_cannot_be_written_is_exit_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Through ``cli.main()``: the option runs before any command, as
    ``--help`` does."""
    failing = mock.create_autospec(console.emit, side_effect=OSError(28, "No space"))
    with (
        mock.patch.object(output, "emit", failing),
        mock.patch("sys.argv", ["licenseid", "--version"]),
        pytest.raises(SystemExit) as exited,
    ):
        cli_main()
    assert (exited.value.code, capsys.readouterr().err) == (
        2,
        "ERROR: output: write failed: No space\n",
    )


def test_version_says_nothing_while_the_shell_completes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Shell completion parses with resilient_parsing: no output, no exit."""
    with cli.make_context("licenseid", ["--version"], resilient_parsing=True):
        pass
    assert capsys.readouterr() == ("", "")

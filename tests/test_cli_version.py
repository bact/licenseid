# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid --version``: the version on standard output, before any
database is looked up."""
# pylint: disable=missing-function-docstring

from unittest import mock

import click
import pytest
from click.testing import CliRunner

import licenseid
from licenseid.cli import cli
from licenseid.cli import main as cli_main


@pytest.mark.parametrize(
    "argv",
    [["--version"], ["--db", "/nonexistent/x.db", "--version"], ["--version", "match"]],
    ids=["bare", "db", "before-command"],
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
    failing = mock.create_autospec(click.echo, side_effect=OSError(28, "No space"))
    with (
        mock.patch.object(click, "echo", failing),
        mock.patch("sys.argv", ["licenseid", "--version"]),
        pytest.raises(SystemExit) as exited,
    ):
        cli_main()
    assert (exited.value.code, capsys.readouterr().err) == (
        2,
        "ERROR: output: write failed: No space\n",
    )

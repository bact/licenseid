# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""click's usage errors in licenseid's grammar (roadmap item 12).

click printed ``Usage: … / Try '…' for help. / Error: …`` on standard
error; every other diagnostic is one line,
``ERROR: SUBJECT: CONDITION[: DETAIL][; ACTION]``. ``CliRunner`` runs click
in standalone mode, where click shows the error itself, so these tests see
what the reworded error prints there; ``test_cli_streams`` sees it through
``cli.main()``.
"""
# pylint: disable=missing-function-docstring

from unittest import mock

import click
import pytest
from click.testing import CliRunner

from licenseid.cli import cli
from licenseid.cli import main as cli_main
from licenseid.usage import (
    UsageLineCommand,
    UsageLineError,
    UsageLineGroup,
    usage_line,
)

# CliRunner names the program after the function, "cli".
CASES = [
    (["match", "--bogus"], "option: not found: --bogus; did you mean --bold"),
    (["is-osi", "--bold", "MIT"], "option: not found: --bold; did you mean --id"),
    (["--nope"], "option: not found: --nope; run 'cli --help'"),
    (["-h"], "option: not found: -h; run 'cli --help'"),
    (["--version"], "option: not found: --version; run 'cli --help'"),
    (["frob"], "command: not found: frob; run 'cli --help'"),
    (["mat", "MIT"], "command: not found: mat; did you mean match"),
    (["match", "--top"], "option: missing: --top; pass a value"),
    (
        ["match", "--top", "x", "MIT"],
        "option: invalid: --top: 'x' is not a valid integer",
    ),
    (
        ["match", "--threshold", "1,5", "MIT"],
        "option: invalid: --threshold: '1,5' is not a valid float",
    ),
    (["match", "--json=true", "MIT"], "option: invalid: --json: does not take a value"),
    (
        ["match", "MIT", "GPL-2.0"],
        "input: invalid: extra argument: GPL-2.0; run 'cli match --help'",
    ),
    # A newline or ";" in a value would split the line or start an ACTION.
    (
        ["match", "--top", "1\n2;x", "MIT"],
        "option: invalid: --top: '1\\n2,x' is not a valid integer",
    ),
    (["match", "--b\nx;y"], "option: not found: --b x,y; run 'cli match --help'"),
]


@pytest.mark.parametrize(("argv", "line"), CASES)
def test_a_usage_error_is_one_line(argv: list[str], line: str) -> None:
    result = CliRunner().invoke(cli, ["--db", "unused.db", *argv])
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        f"ERROR: {line}\n",
    )


@pytest.mark.parametrize("argv", [[], ["--db", "unused.db"]], ids=["bare", "db"])
def test_no_subcommand_prints_the_help_on_standard_error(argv: list[str]) -> None:
    """Exit 2: a usage error, so its text is no result on standard output."""
    result = CliRunner().invoke(cli, argv)
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith("Usage: cli [OPTIONS] [COMMAND] [ARGS]...")
    assert "\nCommands:\n" in result.stderr


def _ctx() -> click.Context:
    return click.Context(click.Command("licenseid"), info_name="licenseid")


@pytest.mark.parametrize(
    ("exc", "line"),
    [
        (
            click.NoSuchOption("--jsn", possibilities=["--json", "--jso"]),
            "option: not found: --jsn; did you mean --json or --jso",  # closest first
        ),
        (
            click.MissingParameter(ctx=_ctx(), param=click.Option(["--name", "-n"])),
            "option: missing: --name; pass a value",
        ),
        (
            click.MissingParameter(ctx=_ctx(), param=click.Argument(["path"])),
            "input: missing; run 'licenseid --help'",
        ),
        (
            click.BadParameter("No such file", param=click.Argument(["path"])),
            "input: invalid: no such file",
        ),
        (
            click.BadOptionUsage("--pair", "Option '--pair' requires 2 arguments."),
            "option: missing: --pair; pass a value",
        ),
        (
            click.UsageError("Something new. Again", _ctx()),
            "usage: invalid: something new. Again; run 'licenseid --help'",
        ),
        (
            click.ClickException("File 'x' unreadable."),
            "usage: invalid: file 'x' unreadable; run 'licenseid --help'",
        ),
    ],
    ids=[
        "possibilities",
        "missing-option",
        "missing-argument",
        "bad-argument",
        "nargs",
        "fallback",
        "not-usage",
    ],
)
def test_usage_line(exc: click.ClickException, line: str) -> None:
    assert usage_line(exc) == line
    assert usage_line(UsageLineError(exc)) == line  # wrapped twice: unchanged


def test_main_words_any_click_error(capsys: pytest.CaptureFixture[str]) -> None:
    """One raised outside parsing (none today) keeps its own exit code."""
    with (
        mock.patch.object(
            cli, "main", autospec=True, side_effect=click.ClickException("Boom.")
        ),
        pytest.raises(SystemExit) as exit_info,
    ):
        cli_main()
    assert exit_info.value.code == 1
    assert capsys.readouterr().err == (
        "ERROR: usage: invalid: boom; run 'licenseid --help'\n"
    )


# A group built as the CLI's is, with what the CLI has none of today.
@click.group(cls=UsageLineGroup)
def group() -> None:
    """Commands."""


@group.command(cls=UsageLineCommand)
@click.option("--n", type=int, callback=lambda _ctx, _param, n: _odd(n))
def callback(n: int) -> None:  # pylint: disable=unused-argument
    """An option whose callback refuses a value."""


def _odd(n: int | None) -> int | None:
    if n == 3:
        raise click.BadParameter("odd value")
    return n


@group.command(cls=UsageLineCommand)
def body() -> None:
    """A command whose own check fails after parsing."""
    raise click.BadParameter("bad in body", param_hint=["'--x'", "'-x'"])


@group.command(cls=UsageLineCommand, no_args_is_help=True)
@click.argument("name")
def needs(name: str) -> None:  # pylint: disable=unused-argument
    """A command that shows its help when given nothing."""


@pytest.mark.parametrize(
    ("argv", "stderr"),
    [
        (["callback", "--n", "3"], "ERROR: option: invalid: --n: odd value\n"),
        (["body"], "ERROR: option: invalid: --x / -x: bad in body\n"),
    ],
    ids=["callback", "body"],
)
def test_an_error_after_parsing_is_one_line(argv: list[str], stderr: str) -> None:
    result = CliRunner().invoke(group, argv)
    assert (result.exit_code, result.stderr) == (2, stderr)


def test_no_args_is_help_shows_the_help() -> None:
    """A help, not an error: never squeezed into one line."""
    result = CliRunner().invoke(group, ["needs"])
    assert result.exit_code == 2
    assert result.stderr.startswith("Usage: group needs [OPTIONS] NAME\n")


def test_a_long_value_keeps_what_is_wrong() -> None:
    result = CliRunner().invoke(cli, ["--db", "x.db", "match", "--top", "z" * 300])
    line = result.stderr
    assert line.startswith("ERROR: option: invalid: --top: 'zzz")
    assert line.endswith("...zzzzzzzzzzzzz' is not a valid integer\n")
    assert len(line) < 160

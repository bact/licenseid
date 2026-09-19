# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CLI output paths the option matrix does not reach: the word diff, running
without a subcommand, a terminal or text-only stdin, and the entry points."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import io
import runpy
import sys
import warnings
from collections.abc import Generator
from datetime import datetime, timezone

import click
import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT, make_mit_db_path

from licenseid import cli as cli_module
from licenseid.cli import cli, get_input_content, read_input, show_diff

GREEN, RED, RESET = "\x1b[32m", "\x1b[31m", "\x1b[0m"


@pytest.fixture
def mit_db() -> Generator[str, None, None]:
    db_path, keep_alive = make_mit_db_path(
        "test_cli_output", datetime.now(timezone.utc).isoformat()
    )
    yield db_path
    keep_alive.close()


# --- show_diff ---


def test_show_diff_marks_added_removed_and_context_words(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A unified diff of DATABASE -> INPUT. The three lines of context are
    difflib's default: current behaviour, not a documented contract."""
    show_diff("one two THREE four five", "one two three four")
    assert capsys.readouterr().out == (
        "\nWORD DIFF:\n--- DATABASE\n+++ INPUT\n@@ -2,3 +2,4 @@\n"
        " two\n three\n four\n+five\n\n"
    )
    show_diff("one two four", "one two three four")
    assert capsys.readouterr().out == (
        "\nWORD DIFF:\n--- DATABASE\n+++ INPUT\n@@ -1,4 +1,3 @@\n"
        " one\n two\n-three\n four\n\n"
    )


@pytest.mark.parametrize(
    ("text", "window"),
    [
        ("Permission is hereby granted.", "permission is hereby granted"),
        ("", ""),
        ("   \n", ""),
    ],
    ids=["equal_after_normalising", "both_empty", "input_blank"],
)
def test_show_diff_prints_nothing_without_a_difference(
    capsys: pytest.CaptureFixture[str], text: str, window: str
) -> None:
    show_diff(text, window)
    assert capsys.readouterr().out == ""


def test_show_diff_with_empty_window_marks_every_word_added(
    capsys: pytest.CaptureFixture[str],
) -> None:
    show_diff("alpha beta", "")
    out = capsys.readouterr().out
    assert "+alpha\n+beta\n" in out
    assert "\n-" not in out.replace("--- DATABASE", "")


# --- match --diff, end to end ---


def _match(db: str, *args: str, color: bool = False) -> click.testing.Result:
    return CliRunner().invoke(cli, ["--db", db, "match", *args], color=color)


def test_match_diff_shows_word_diff_after_the_result_line(mit_db: str) -> None:
    result = _match(mit_db, "--diff", "--text", MIT_SEARCH_TEXT + " and more words")
    assert result.exit_code == 0
    assert result.stderr == ""
    first, rest = result.stdout.split("\n", 1)
    assert first.startswith("LICENSE_ID=MIT SIMILARITY=0.9")
    assert rest.startswith("\nWORD DIFF:\n--- DATABASE\n+++ INPUT\n@@")
    assert rest.endswith(" copy\n+and\n+more\n+words\n\n")


def test_match_diff_colours_added_green_and_removed_red(mit_db: str) -> None:
    """Added words are green, removed words red. (How the ---/+++ header lines
    are coloured is not asserted: it is incidental, not a stated contract.)"""
    added = _match(
        mit_db, "--diff", "--text", MIT_SEARCH_TEXT + " and more", color=True
    )
    assert f"{GREEN}+and{RESET}\n{GREEN}+more{RESET}\n" in added.stdout
    replaced = _match(
        mit_db,
        "--diff",
        "--text",
        "permission is hereby granted free of charge to any human obtaining a copy",
        color=True,
    )
    assert replaced.exit_code == 0
    assert f"{RED}-person{RESET}\n{GREEN}+human{RESET}\n" in replaced.stdout
    # Words that did not change are context lines: no colour.
    assert "\n obtaining\n" in replaced.stdout


def test_match_diff_is_plain_text_when_not_a_terminal(mit_db: str) -> None:
    result = _match(mit_db, "--diff", "--text", MIT_SEARCH_TEXT + " and more")
    assert "\x1b[" not in result.stdout


def test_match_diff_of_an_exact_match_prints_no_diff(mit_db: str) -> None:
    result = _match(mit_db, "--diff", "--text", MIT_SEARCH_TEXT)
    assert result.stdout == "LICENSE_ID=MIT SIMILARITY=1.0000 COVERAGE=1.0000\n"


def test_match_diff_of_a_fragment_prints_no_diff(mit_db: str) -> None:
    """The input is a piece of the license (similarity 1.0, coverage below
    1.0). The window it aligned to equals the input, so there is nothing to
    show."""
    result = _match(
        mit_db, "--diff", "--text", "permission is hereby granted free of charge"
    )
    assert result.stdout.startswith("LICENSE_ID=MIT SIMILARITY=1.0000 COVERAGE=0.")
    assert result.stdout.count("\n") == 1


@pytest.mark.parametrize("other", ["--json", "--bold"])
def test_match_diff_is_dropped_for_json_and_bold(mit_db: str, other: str) -> None:
    """Current behaviour, not a documented contract: --diff has no effect with
    --json or --bold, and nothing says so (roadmap: conflicting options are
    resolved silently). Pinned so a change is deliberate."""
    result = _match(
        mit_db, "--diff", other, "--text", MIT_SEARCH_TEXT + " and more words"
    )
    assert "WORD DIFF" not in result.stdout
    assert "@@" not in result.stdout


# --- no subcommand ---


@pytest.mark.parametrize("args", [[], ["--db", "unused.db"]])
def test_no_subcommand_shows_usage_and_exits_2(args: list[str]) -> None:
    """README: a missing subcommand is a usage error (exit 2). Which stream
    carries the usage text is not asserted."""
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    assert "[OPTIONS] [COMMAND] [ARGS]..." in result.stdout + result.stderr


# --- stdin variants ---


def _ctx() -> click.Context:
    return click.Context(cli)


def test_read_input_from_text_only_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """stdin replaced by an object with no .buffer (an io.StringIO)."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("Permission is\r\nhereby granted\n"))
    assert read_input(_ctx(), None) == "Permission is\nhereby granted\n"


def test_read_input_from_text_only_stdin_with_lone_surrogate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A lone surrogate cannot be UTF-8: it takes the Latin-1 path with the
    usual warning instead of crashing on the encode."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("MIT \ud800 license"))
    text = read_input(_ctx(), None)
    assert text.startswith("MIT ") and text.endswith(" license")
    assert capsys.readouterr().err == (
        "WARNING: input: not UTF-8, read as Latin-1: stdin\n"
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("MIT\x00", "ERROR: input: binary file: stdin\n"),
        ("  \n", "ERROR: input: empty: stdin\n"),
    ],
    ids=["nul", "blank"],
)
def test_read_input_from_text_only_stdin_rejects_bad_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str,
    message: str,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(content))
    with pytest.raises(click.exceptions.Exit) as info:
        read_input(_ctx(), None)
    assert info.value.exit_code == 2
    assert capsys.readouterr().err == message


def test_read_input_from_text_only_stdin_keeps_non_ascii(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("Copyright © Zoë"))
    assert read_input(_ctx(), None) == "Copyright © Zoë"
    assert capsys.readouterr().err == ""


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_terminal_stdin_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no argument and a terminal on stdin the command must not block
    waiting for input: no content, so the caller reports it as missing."""
    monkeypatch.setattr(sys, "stdin", _Tty("this must not be read"))
    assert get_input_content(_ctx(), None, None) == ("", False)


def test_piped_stdin_is_read_when_no_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("MIT"))
    assert get_input_content(_ctx(), None, None) == ("MIT", True)


# --- entry points ---


def test_main_runs_the_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["licenseid", "--help"])
    with pytest.raises(SystemExit) as info:
        cli_module.main()
    assert info.value.code == 0
    # The program name in "Usage:" depends on how the tests are launched.
    assert "[OPTIONS] [COMMAND] [ARGS]..." in capsys.readouterr().out


def test_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`python -m licenseid.cli` reaches main() through the __main__ guard."""
    monkeypatch.setattr(sys, "argv", ["licenseid", "--help"])
    with warnings.catch_warnings():
        # runpy warns that the module is already imported; that is expected.
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(SystemExit) as info:
            runpy.run_module("licenseid.cli", run_name="__main__")
    assert info.value.code == 0
    assert "[OPTIONS] [COMMAND] [ARGS]..." in capsys.readouterr().out

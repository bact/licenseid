# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect`` and ``resolve`` print the expression alone, ``-v`` (or
``--verbose``) the full record; ``-V`` is ``--version``; ``--id-only`` is
gone. The tests here see the command line as written (``terse_cli``)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner
from conftest import NO_DETECTION, make_mit_db_path
from packaged_list import fixture_bundle
from release_fakes import ship

import licenseid
from licenseid.cli import cli

pytestmark = pytest.mark.terse_cli


@pytest.fixture
def db() -> Generator[str, None, None]:
    path, keep_alive = make_mit_db_path(
        "test_terse", datetime.now(timezone.utc).isoformat()
    )
    yield path
    keep_alive.close()


def run(db_path: str, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["--db", db_path, *args])
    return result.exit_code, result.stdout, result.stderr


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_the_short_and_long_version_flags_print_the_version(flag: str) -> None:
    result = CliRunner().invoke(cli, [flag])
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        f"licenseid {licenseid.__version__}\n",
        "",
    )


def test_detect_prints_the_expression_alone(db: str) -> None:
    assert run(db, "detect", "MIT") == (0, "MIT\n", "")


@pytest.mark.parametrize("flag", ["-v", "--verbose"])
def test_detect_verbose_prints_the_record(db: str, flag: str) -> None:
    code, out, err = run(db, "detect", flag, "MIT")
    assert (code, err) == (0, "")
    assert out.startswith("EXPRESSION=MIT\tMETHOD=id\tEXACT=true\t")


def test_detect_with_no_answer_prints_an_empty_line(db: str) -> None:
    assert run(db, "detect", "--id", "No-Such-1.0") == (1, "\n", "")
    assert run(db, "detect", "-v", "--id", "No-Such-1.0") == (1, NO_DETECTION, "")


def test_detect_prints_one_expression_per_result_in_rank_order(db: str) -> None:
    text = "permission is hereby granted free of charge to any person"
    args = ("detect", "--top", "3", "--threshold", "0", "--text", text)
    _, terse, _ = run(db, *args)
    _, full, _ = run(db, args[0], "-v", *args[1:])
    assert terse.splitlines() == [
        line.split("\t")[0].removeprefix("EXPRESSION=") for line in full.splitlines()
    ]


@pytest.mark.parametrize("flag", ["-v", "--verbose"])
def test_json_is_the_same_with_or_without_verbose(db: str, flag: str) -> None:
    plain = run(db, "detect", "--json", "MIT")
    assert plain == run(db, "detect", "--json", flag, "MIT")
    assert set(json.loads(plain[1])) >= {"expression", "method", "score", "lists"}


def test_id_only_is_not_an_option(db: str) -> None:
    code, out, err = run(db, "detect", "--id-only", "MIT")
    assert (code, out) == (2, "")
    assert err.startswith("ERROR: option: not found: --id-only; did you mean --id")


def test_diff_still_conflicts_with_json(db: str) -> None:
    code, out, err = run(db, "detect", "--json", "--diff", "MIT")
    assert (code, out) == (2, "")
    assert err == "ERROR: option: invalid: --diff: with --json; pass one of them\n"


def test_a_warning_stays_on_standard_error(db: str) -> None:
    text = "lorem ipsum dolor"
    assert run(db, "detect", "--text", text) == (
        1,
        "\n",
        f"WARNING: input: too few words for text: not found: {text}\n",
    )


@pytest.mark.parametrize("command", ["is-osi", "is-fsf", "is-spdx", "update"])
def test_other_commands_take_no_verbose(db: str, command: str) -> None:
    code, out, err = run(db, command, "-v", "MIT")
    assert (code, out) == (2, "")
    assert err.startswith("ERROR: option: not found: -v")


def test_resolve_prints_the_expression_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["resolve", "GPLv2+ or MIT"])
    assert (result.exit_code, result.stdout) == (0, "GPL-2.0-or-later OR MIT\n")


def test_resolve_verbose_prints_the_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["resolve", "-v", "MIT ; Apache 2"])
    assert result.exit_code == 1
    assert result.stdout.startswith("EXPRESSION=\tCATEGORY=unresolved\tTRUST=none\n")
    assert "REASON=" in result.stdout


def test_a_refused_resolve_prints_an_empty_line_without_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["resolve", "MIT ; Apache 2"])
    assert (result.exit_code, result.stdout, result.stderr) == (1, "\n", "")


def test_resolve_json_is_the_same_with_or_without_verbose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, fixture_bundle())
    plain = CliRunner().invoke(cli, ["resolve", "--json", "MIT"]).stdout
    full = CliRunner().invoke(cli, ["resolve", "--json", "-v", "MIT"]).stdout
    assert plain == full
    assert json.loads(plain)["expression"] == "MIT"


def test_help_names_verbose_and_the_short_version_flag() -> None:
    top = CliRunner().invoke(cli, ["--help"]).stdout
    assert "-V, --version" in top
    for command in ("detect", "resolve"):
        text = CliRunner().invoke(cli, [command, "--help"]).stdout
        assert "-v, --verbose" in text
        assert "--id-only" not in text

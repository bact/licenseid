# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden snapshot of every CLI command (``tests/fixtures/golden/cli.jsonl``)
and the invariants of its records. Each case of ``harness_cli.CASES`` runs as
text and with ``--json``; a record keeps the exit status and both streams.
A record that moved must be listed in ``harness_changes.CLI_CHANGES`` by
digest (``python -m tools.golden cli`` prints it) with the reason."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
from pathlib import Path

import harness_cli as hcli
import harness_golden as hg
import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_changes import CLI_CHANGES
from harness_checks import canonical, line_matches_json, match_lines_agree
from test_output_pattern import TEXT_LINE

from licenseid.result import read_text_field
from tools.golden.__main__ import CLI_FILE, digest, read_cli_golden


@pytest.fixture(scope="module")
def records(tmp_path_factory: pytest.TempPathFactory) -> dict[str, hcli.Record]:
    """Every case run once, by ``case#mode``."""
    base = tmp_path_factory.mktemp("harness_cli")
    with hcli.cli_env(base) as env:
        return {
            f"{record.case}#{record.mode}": record
            for case in hcli.CASES
            for record in env.run(case)
        }


def test_the_cli_is_the_golden(records: dict[str, hcli.Record]) -> None:
    current = {key: hcli.record_line(record) for key, record in records.items()}
    report = hg.diff_report(
        read_cli_golden(), current, CLI_CHANGES, view=digest, complete=True
    )
    assert not report, "\n" + report


def test_the_cli_golden_is_short_and_in_order() -> None:
    lines = CLI_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 800
    keys = [f"{r.case}#{r.mode}" for r in map(hcli.read_record, lines)]
    assert keys == sorted(keys)
    assert all(canonical(line) is None for line in lines)


def test_every_command_and_every_kind_of_outcome_is_run(
    records: dict[str, hcli.Record],
) -> None:
    commands = {case.args[0] for case in hcli.CASES}
    assert commands == {
        "detect",
        "resolve",
        "update",
        "clear-cache",
        "is-osi",
        "is-fsf",
        "is-spdx",
    }
    assert {record.exit for record in records.values()} == {0, 1, 2}
    assert any("WARNING:" in record.stderr for record in records.values())


def test_the_names_of_the_cases_are_unique() -> None:
    names = [case.name for case in hcli.CASES]
    assert len(set(names)) == len(names)


def _head(record: hcli.Record) -> dict[str, str]:
    """The fields of the first stdout line, read back."""
    line = record.stdout.split("\n")[0]
    return {
        key: read_text_field(value)
        for key, _, value in (field.partition("=") for field in line.split("\t"))
    }


def test_the_exit_status_agrees_with_the_answer(
    records: dict[str, hcli.Record],
) -> None:
    """0 an answer (yes), 1 none (no), 2 no result at all; ``--json`` gives
    the status of the text run, bar the one usage error it adds."""
    for key, record in records.items():
        if record.exit == 2:
            assert record.stdout == "", key
        elif key.endswith("#json"):
            assert record.exit == records[key.replace("#json", "#text")].exit, key
        elif key.startswith(("update", "clear-cache")):
            assert record.exit == 0, key
        elif "id-only" in key:
            assert (record.exit, record.stdout.endswith("\n")) == (0, True), key
        else:
            head = _head(record)
            flag = next((v for k, v in head.items() if k.startswith("IS_")), None)
            if flag is not None:  # is-*: 0 yes, 1 no or no answer
                assert record.exit == (0 if flag == "true" else 1), key
            else:
                assert record.exit == (0 if head["EXPRESSION"] else 1), key


def test_every_text_line_reads_back_to_its_json(
    records: dict[str, hcli.Record],
) -> None:
    for key, record in records.items():
        if not key.endswith("#text") or record.exit == 2 or "id-only" in key:
            continue
        other = records[key.replace("#text", "#json")]
        text_lines = record.stdout.split("\n")[:-1]
        json_lines = other.stdout.split("\n")[:-1]
        assert text_lines and json_lines, key
        for line in text_lines:
            assert TEXT_LINE.fullmatch(line), (key, line)
        if key.startswith("resolve"):  # one record; the lines are parts of it
            assert len(json_lines) == 1, key
            assert canonical(json_lines[0]) is None, key
            why = match_lines_agree(text_lines, json.loads(json_lines[0]))
            assert why is None, (key, why)
            continue
        for text, js in zip(text_lines, json_lines):
            assert canonical(js) is None, (key, js)
            assert line_matches_json(text, json.loads(js)) is None, (key, text, js)


def test_the_streams_follow_the_grammar(records: dict[str, hcli.Record]) -> None:
    for key, record in records.items():
        assert record.stdout == "" or record.stdout.endswith("\n"), key
        assert "\r" not in record.stderr, key
        assert "Traceback" not in record.stderr, key
        if record.exit == 2:
            assert record.stderr.startswith("ERROR: "), key


def test_the_golden_path_is_inside_the_fixtures() -> None:
    assert CLI_FILE == Path(hg.GOLDEN) / "cli.jsonl"


@pytest.mark.parametrize(
    "raw",
    [
        "a <TMP>/home/x/y.db; run",
        "a <TMP>\\home\\x\\y.db; run",
        "a <TMP>\\\\home\\\\x\\\\y.db; run",
    ],
    ids=["posix", "windows", "windows escaped"],
)
def test_the_rest_of_a_scratch_path_has_one_separator(raw: str) -> None:
    assert hcli.slash_the_tails(raw) == "a <TMP>/home/x/y.db; run"

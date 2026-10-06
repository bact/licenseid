# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for the CLI matrix verdicts in ``tools/cli_matrix/judge``.

One test per rule, each written so that deleting the rule makes it
fail: a judge that silently stopped checking something would otherwise
look exactly like a clean tree.
"""

from __future__ import annotations

import os
import runpy
import sys
from typing import Any

import pytest
from cli_matrix_env import make_cell, make_result
from conftest import public_match

from licenseid.result import json_line, text_line
from tools.cli_matrix import judge as judge_mod
from tools.cli_matrix.model import Cell

CLEAN_PREDICATE = {"rc": 0, "out": "true\n", "err": "", "files": []}
CLEAN_MATCH = {"rc": 0, "out": "MIT\n", "err": "", "files": []}

# --------------------------------------------------------------- judging

FLAG_CASES: list[tuple[str, dict[str, Any], dict[str, Any], str]] = [
    (
        "traceback on stderr",
        {"kind": "other"},
        {"rc": 1, "err": "Traceback (most recent call last):\n  File x\n"},
        "traceback/crash",
    ),
    (
        "stderr line outside the grammar",
        {"kind": "other", "exp_exit": 0},
        {"rc": 0, "err": "something went wrong\n"},
        "stderr line outside grammar",
    ),
    (
        "diagnostic on stdout",
        {"kind": "other", "exp_exit": 0},
        {"rc": 0, "out": "ERROR: input: missing\n"},
        "diagnostic on stdout",
    ),
    (
        "predicate contract violated",
        {"kind": "predicate"},
        {"rc": 0, "out": "yes\n"},
        "predicate contract",
    ),
    (
        "match exit 1 without the documented diagnostic",
        {"kind": "match"},
        {"rc": 1, "err": "ERROR: match: something else\n"},
        "match exit 1 without empty stdout",
    ),
    (
        "expected exit not met",
        {"kind": "other", "exp_exit": 0},
        {"rc": 2},
        "expected exit 0, got 2",
    ),
    (
        "exit status outside 0/1/2",
        {"kind": "other"},
        {"rc": 7},
        "exit code 7 outside 0/1/2",
    ),
    (
        "--top not honoured",
        {"kind": "match", "top": 1, "outflags": frozenset({"json"})},
        {
            "rc": 0,
            "out": '{"license_id":"MIT","method":"text","score":1}\n'
            '{"license_id":"X","method":"text","score":0.5}\n',
        },
        "--top 1 returned 2",
    ),
    (
        "temporary files left behind",
        {"fam": "D1", "kind": "update", "exp_exit": 0},
        {"rc": 0, "out": "Database updated at x\n", "files": ["licenses.json.1.tmp"]},
        "leftover tmp files",
    ),
    (
        "update chatters on stdout",
        {"fam": "D1", "kind": "update", "exp_exit": 0, "progress": True},
        {"rc": 0, "out": "working...\nDone\n"},
        "update stdout not a single result line",
    ),
    (
        "stdout does not match the expectation",
        {"kind": "other", "exp_out": r"MIT\n"},
        {"rc": 0, "out": "Apache-2.0\n"},
        "!~",
    ),
    (
        "required diagnostic absent",
        {"kind": "other", "exp_err": "no license found"},
        {"rc": 1},
        "stderr lacks",
    ),
    (
        "the command hung",
        {"kind": "other"},
        {"rc": -999},
        "TIMEOUT",
    ),
    (
        "--bold printed more than an identifier",
        {"kind": "match", "outflags": frozenset({"bold"}), "exp_exit": 0},
        {
            "rc": 0,
            "out": "LICENSE_ID=MIT METHOD=id EXACT=true SCORE=1.0000 SIMILARITY="
            " COVERAGE=\n",
        },
        "--bold not a single id",
    ),
]


MIT_JSON = '{"exact":true,"license_id":"MIT","method":"id","score":1}'
BSD_JSON = '{"exact":false,"license_id":"0BSD","method":"name","score":0.9}'
ISC_JSON = '{"exact":false,"license_id":"ISC","method":"name","score":0.9}'


@pytest.mark.parametrize(
    ("cell_kwargs", "result_kwargs", "expected_note"),
    [pytest.param(c, r, n, id=i) for i, c, r, n in FLAG_CASES],
)
def test_judge_flags(
    cell_kwargs: dict[str, Any],
    result_kwargs: dict[str, Any],
    expected_note: str,
) -> None:
    """Each violated invariant produces a FLAG naming what went wrong."""
    verdict, notes = judge_mod.judge(
        make_cell(**cell_kwargs), make_result(**result_kwargs)
    )
    assert verdict == "FLAG"
    assert any(expected_note in note for note in notes), notes


def test_judge_passes_a_clean_run() -> None:
    """A documented expectation that holds is a PASS, not an OBSERVE."""
    cell = make_cell(kind="predicate", exp_exit=0, exp_out=r"true\n")
    verdict, notes = judge_mod.judge(cell, make_result(**CLEAN_PREDICATE))
    assert (verdict, notes) == ("PASS", [])


def test_judge_observes_unspecified_behaviour() -> None:
    """With nothing documented there is no contract to pass."""
    verdict, _ = judge_mod.judge(make_cell(kind="other"), make_result(**CLEAN_MATCH))
    assert verdict == "OBSERVE"


def test_judge_allows_progress_lines_when_declared() -> None:
    """A command that prints progress is not flagged for it."""
    cell = make_cell(kind="other", progress=True, exp_exit=0)
    result = make_result(rc=0, err="Fetching latest license list info...\n")
    assert judge_mod.judge(cell, result)[0] == "PASS"


def test_judge_ignores_streams_on_a_terminal() -> None:
    """On a tty the two streams are one, so neither can be judged."""
    cell = make_cell(kind="predicate", tty=True)
    result = make_result(rc=0, out="ERROR: input: missing\nfalse\n")
    assert judge_mod.judge(cell, result)[0] == "OBSERVE"


def test_judge_accepts_the_documented_diagnostic_grammar() -> None:
    """LEVEL: SUBJECT: CONDITION on stderr is exactly what is expected."""
    cell = make_cell(kind="match", exp_exit=1)
    result = make_result(rc=1, err="ERROR: match: no license found\n")
    assert judge_mod.judge(cell, result)[0] == "PASS"


# ----------------------------------------------------- differential rules


def test_differential_flags_a_shell_dependent_answer() -> None:
    """The same command must answer the same in every shell."""
    cells = {"X1-001": make_cell()}
    results = [
        make_result(shell="bash", rc=0, out="MIT\n"),
        make_result(shell="zsh", rc=1, out=""),
    ]
    bad = judge_mod.differential(cells, results, "/out")
    assert ("X1-001", "zsh", "310") in bad


def test_differential_respects_xenv_false() -> None:
    """A cell that is allowed to vary is not compared across shells."""
    cells = {"X1-001": make_cell(xenv=False)}
    results = [
        make_result(shell="bash", rc=0, out="MIT\n"),
        make_result(shell="zsh", rc=1, out=""),
    ]
    assert not judge_mod.differential(cells, results, "/out")


def test_differential_normalises_work_directory_paths() -> None:
    """A path that differs only by work directory is not a difference."""
    cells = {"X1-001": make_cell()}
    results = [
        make_result(shell="bash", work="/w/a", err="ERROR: database: x: /w/a/db"),
        make_result(shell="zsh", work="/w/b", err="ERROR: database: x: /w/b/db"),
    ]
    assert not judge_mod.differential(cells, results, "/out")


def test_differential_flags_a_group_outlier() -> None:
    """Sources in one group must give one answer; the minority is flagged."""
    cells = {
        "G-001": make_cell(id="G-001", group="g"),
        "G-002": make_cell(id="G-002", group="g"),
        "G-003": make_cell(id="G-003", group="g"),
    }
    results = [
        make_result(id="G-001", rc=0, out="MIT\n"),
        make_result(id="G-002", rc=0, out="MIT\n"),
        make_result(id="G-003", rc=1, out="\n"),
    ]
    bad = judge_mod.differential(cells, results, "/out")
    assert list(bad) == [("G-003", "bash", "310")]


def test_group_compares_a_json_answer_whole() -> None:
    """A JSON answer is compared whole, every line, not by its top result."""
    flags = frozenset({"json"})
    cells = {
        "A1-001": make_cell(id="A1-001", group="A1-x", outflags=flags),
        "A1-002": make_cell(id="A1-002", group="A1-x", outflags=flags),
        "A1-003": make_cell(id="A1-003", group="A1-x", outflags=flags),
    }
    results = [
        make_result(id="A1-001", out=f"{MIT_JSON}\n{BSD_JSON}\n"),
        make_result(id="A1-002", out=f"{MIT_JSON}\n{BSD_JSON}\n"),
        make_result(id="A1-003", out=f"{MIT_JSON}\n{ISC_JSON}\n"),
    ]
    assert list(judge_mod.differential(cells, results, "/out")) == [
        ("A1-003", "bash", "310")
    ]


def test_group_compares_plain_output_by_its_first_line_only() -> None:
    """Ties may reorder later lines of plain output; the top answer decides."""
    cells = {f"A1-00{n}": make_cell(id=f"A1-00{n}", group="A1-y") for n in (1, 2, 3)}
    results = [
        make_result(id="A1-001", out="MIT 1\nBSD 1\n"),
        make_result(id="A1-002", out="MIT 1\nISC 1\n"),
        make_result(id="A1-003", out="GPL 1\nMIT 1\n"),
    ]
    assert list(judge_mod.differential(cells, results, "/out")) == [
        ("A1-003", "bash", "310")
    ]


def test_bold_text_groups_are_not_exempt_from_the_group_check() -> None:
    """File, text and stdin read the same bytes and must agree, ``--bold`` too."""
    cells = {
        f"A1-00{n}": make_cell(id=f"A1-00{n}", group="A1-text-True-bold")
        for n in (1, 2, 3)
    }
    results = [
        make_result(id="A1-001", out="MIT\n"),
        make_result(id="A1-002", out="MIT\n"),
        make_result(id="A1-003", out="GPL-2.0-only\n"),
    ]
    assert list(judge_mod.differential(cells, results, "/out")) == [
        ("A1-003", "bash", "310")
    ]


def test_relational_flags_contradicting_predicates() -> None:
    """is-open must agree with is-osi or is-fsf; is-free with is-open."""
    cells, rows = _relational_fixture(is_open_rc=1)
    judge_mod.relational(rows, cells)
    assert all(row["verdict"] == "FLAG" for row in rows)
    assert any("relational:" in note for note in rows[0]["notes"])


def test_relational_passes_consistent_predicates() -> None:
    """Consistent answers are annotated but not flagged."""
    cells, rows = _relational_fixture(is_open_rc=0)
    judge_mod.relational(rows, cells)
    assert all(row["verdict"] == "OBSERVE" for row in rows)


def _relational_fixture(is_open_rc: int) -> tuple[dict[str, Cell], list[Any]]:
    """Five B5 cells for one identifier, with is-open set as asked."""
    codes = {
        "is-osi": 0,
        "is-fsf": 0,
        "is-open": is_open_rc,
        "is-free": is_open_rc,
        "is-spdx": 0,
    }
    cells: dict[str, Cell] = {}
    rows: list[Any] = []
    for index, (name, rc) in enumerate(codes.items()):
        cell_id = f"B5-{index:03d}"
        cells[cell_id] = make_cell(
            id=cell_id,
            fam="B5",
            desc=f"{name} --id 'MIT' (consistency group)",
            cmd=f"$L --db $DB {name} --id MIT",
        )
        rows.append(make_result(id=cell_id, rc=rc, verdict="OBSERVE", notes=[]))
    return cells, rows


# What match prints, from the code that prints it.
# Coverage, input words over licence words, can reach two digits.
RESULT = public_match(
    "GPL-2.0-only WITH Classpath-exception-2.0",
    method="text",
    exact=False,
    score=0.9908,
    similarity=1.0,
    coverage=13.0,
)
PLAIN_LINE = text_line(RESULT)
TEXT: frozenset[str] = frozenset()
JSON = frozenset({"json"})


@pytest.mark.parametrize(
    ("flags", "out", "ok"),
    [
        (TEXT, PLAIN_LINE, True),
        (TEXT, text_line(public_match()), True),
        (TEXT, PLAIN_LINE.replace("WITH", "OR"), True),  # an expression from a tag
        # The format before the method, exact and score keys.
        (TEXT, "LICENSE_ID=MIT SIMILARITY=1.0000 COVERAGE=1.0000", False),
        (TEXT, PLAIN_LINE.replace("EXACT=false", "EXACT=no"), False),
        (TEXT, PLAIN_LINE.replace("SCORE=0.9908", "SCORE=1.02"), False),
        (TEXT, PLAIN_LINE.replace("SCORE=0.9908", "SCORE=10.9908"), False),
        (TEXT, PLAIN_LINE.replace("SCORE=0.9908", "SCORE=1.9908"), False),
        # Two results on one line.
        (TEXT, f"{PLAIN_LINE} {text_line(public_match())}", False),
        (TEXT, PLAIN_LINE.replace("METHOD=text", "METHOD=TEXT"), False),
        (TEXT, PLAIN_LINE.replace("METHOD=text", "METHOD="), False),
        (TEXT, PLAIN_LINE.replace("COVERAGE=13.0000", "COVERAGE=1.02"), False),
        (JSON, json_line(RESULT), True),
        (JSON, f"{MIT_JSON}\n{BSD_JSON}", True),
        # The array --json printed before JSON Lines.
        (JSON, f"[{MIT_JSON},{BSD_JSON}]", False),
        (JSON, '{"license_id":"MIT","score":1}', False),  # no method
        (JSON, f"{MIT_JSON}\nnot json", False),
        (JSON, f"{MIT_JSON}\n\n{BSD_JSON}", False),
        (JSON, "[]", False),
    ],
)
def test_match_output_is_the_format_its_flags_ask_for(
    flags: frozenset[str], out: str, ok: bool
) -> None:
    """The judge accepts what match prints, and nothing else: one KEY=VALUE
    line, or one result object per JSON line (not an array, not a bare
    value)."""
    notes = judge_mod.check_match_format(make_cell(outflags=flags), out + "\n")
    assert (not notes) is ok, notes


def test_windows_is_refused_before_the_posix_only_imports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runner imports pty and termios, so on Windows the tool must say so
    before it imports anything, not die with a bare ModuleNotFoundError.

    Collected on Windows too, where the refusal is real. Elsewhere, os.name is
    patched and the modules the tool would import are made unavailable, so an
    import placed before the refusal fails the test.
    """
    for name in ("pty", "termios"):
        monkeypatch.setitem(sys.modules, name, None)
    for name in [n for n in sys.modules if n.startswith("tools.cli_matrix.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(os, "name", "nt")
    with pytest.raises(SystemExit) as info:
        runpy.run_module("tools.cli_matrix", run_name="__main__")
    monkeypatch.undo()
    assert info.value.code == 2
    assert capsys.readouterr().err.startswith("ERROR: platform: unsupported: ")

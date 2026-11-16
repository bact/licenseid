# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0
# pylint: disable=missing-function-docstring,protected-access

"""The CLI matrix cell ``E8-011`` (a FIFO with a writer) and the runner's
process group.

``licenseid detect <fifo>`` refuses a named pipe without opening it, so the
cell's writer blocks in ``open()``. It must hold none of the cell's streams
and be freed by the cell, and the runner must end whatever a cell left
behind (roadmap item 56).
"""

from __future__ import annotations

import os
import shlex
import time
from pathlib import Path
from typing import Any

import pytest
from cli_matrix_env import make_result

from tools.cli_matrix import judge as judge_mod
from tools.cli_matrix import runner
from tools.cli_matrix.cells import build_cells
from tools.cli_matrix.cells.process_env import FIFO_CELL, FIFO_REFUSAL
from tools.cli_matrix.model import Cell

REFUSAL = "ERROR: input: unreadable: /w/ff: not a regular file\n"


def _fifo_cell() -> Cell:
    found = [c for c in build_cells().cells if c.desc == FIFO_CELL]
    assert [c.id for c in found] == ["E8-011"]
    return found[0]


def test_the_fifo_cell_writer_holds_no_stream_and_is_freed() -> None:
    cmd = _fifo_cell().cmd
    words = shlex.split(cmd, posix=True)
    # The writer drops both streams before it opens the FIFO ...
    assert "(exec >/dev/null 2>&1; printf 'MIT' > $W/ff) &" in cmd
    # ... and the cell frees it with a read-write open, after licenseid ran.
    assert cmd.index("detect $W/ff") < cmd.index(": <>$W/ff")
    assert cmd.endswith("exit $rc")
    assert "$L" in words


def test_the_fifo_cell_keeps_the_exit_and_output_checks() -> None:
    cell = _fifo_cell()
    # wait or kill would switch off the exit check and the detect contract
    assert not judge_mod.has_pipe_tail(cell)
    assert cell.exp_exit == 2
    assert cell.exp_out == ""
    assert cell.exp_err == FIFO_REFUSAL


@pytest.mark.parametrize(
    "result",
    [
        make_result(rc=2, out="", err=REFUSAL),
    ],
)
def test_the_fifo_cell_passes_its_refusal(result: dict[str, Any]) -> None:
    verdict, notes = judge_mod.judge(_fifo_cell(), result)
    assert (verdict, notes) == (judge_mod.PASS, [])


@pytest.mark.parametrize(
    "result",
    [
        make_result(rc=0, out="MIT\n", err=""),
        make_result(rc=1, out="\n", err=""),
        make_result(rc=2, out="", err="ERROR: input: empty\n"),
        make_result(rc=2, out="MIT\n", err=REFUSAL),
    ],
    ids=["answer", "no answer", "other error", "stdout on exit 2"],
)
def test_the_fifo_cell_flags_anything_else(result: dict[str, Any]) -> None:
    verdict, _ = judge_mod.judge(_fifo_cell(), result)
    assert verdict == judge_mod.FLAG


def _gone(pid: int) -> bool:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_a_timeout_ends_what_the_cell_left_holding_its_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "TIMEOUT", 2)
    pidfile = tmp_path / "pid"
    cmd = f"sleep 60 & echo $! > {pidfile}; exit 0"
    started = time.monotonic()
    rc, _, err = runner._run_plain(["bash", "-c", cmd], dict(os.environ), str(tmp_path))
    assert (rc, err) == (runner.TIMEOUT_RC, "TIMEOUT")
    assert time.monotonic() - started < 15
    assert _gone(int(pidfile.read_text()))

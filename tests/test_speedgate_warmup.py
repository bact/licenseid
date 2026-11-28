# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The warm-up of the speed gate: a set is timed after one untimed pass over
its own inputs; the one-call set stays cold. POSIX only (``resource``)."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import posix_only

from benchmarks.speedgate import runner, worker
from benchmarks.speedgate.runner import Job, Side

pytestmark = posix_only

# pylint: disable=missing-function-docstring

# A detector that remembers the texts it has seen: a first sight answers COLD.
SEEING_DETECTOR = """
class LicenseDetector:
    seen = set()

    def __init__(self, db):
        self.db = db

    def detect(self, text, **options):
        state = "WARM" if text in self.seen else "COLD"
        self.seen.add(text)
        return [{"expression": state, "score": 1.0, "method": "text",
                 "exact": True}]

    def texts(self, text, **options):
        return ["MIT"]
"""


def _side(tmp_path: Path) -> Side:
    package = tmp_path / "side" / "src" / "licenseid"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "9.9.9"\n')
    (package / "detector.py").write_text(SEEING_DETECTOR)
    home = tmp_path / "home"
    home.mkdir()
    return Side(tmp_path / "side", tmp_path / "db.sqlite", home, sys.executable)


def _job(tmp_path: Path, cases: list[dict[str, Any]]) -> Job:
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps({"digest": "d", "sets": {"core": cases}}))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return Job(inputs, scratch)


CASES: list[dict[str, Any]] = [{"key": "a", "text": "x"}, {"key": "b", "text": "y"}]


def test_the_timed_pass_of_a_set_sees_a_warm_detector(tmp_path: Path) -> None:
    out = runner.run_child(
        _side(tmp_path), _job(tmp_path, CASES), ["detect", "--set", "core"]
    )
    assert [out["cases"][k]["rows"][0][0] for k in ("a", "b")] == ["WARM", "WARM"]


def test_a_case_run_alone_gets_the_small_call_not_a_pass(tmp_path: Path) -> None:
    out = runner.run_child(
        _side(tmp_path),
        _job(tmp_path, CASES),
        ["detect", "--set", "core", "--only", "a"],
    )
    assert out["cases"]["a"]["rows"][0][0] == "COLD"


class Counting:
    """A fake detector that counts its calls and the options it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def detect(self, text: str, **options: Any) -> list[dict[str, Any]]:
        self.calls.append((text, tuple(options)))
        return [{"expression": "MIT"}]

    def texts(self, text: str) -> list[str]:
        self.calls.append((text, ("texts",)))
        return []


def test_the_warm_up_repeats_the_inputs_and_options_of_the_timed_pass() -> None:
    cases: list[dict[str, Any]] = [
        {"key": "a", "text": "x", "options": {"hint": ["MIT"]}, "texts_call": True},
        {"key": "b", "text": "y"},
    ]
    det = Counting()
    worker.warm_up(det, cases)
    first = list(det.calls)
    assert first == [("x", ("hint",)), ("x", ("texts",)), ("y", ())]
    for one in cases:
        worker.measure(det, one)
    assert det.calls == first + first


def test_the_one_call_set_stays_cold_one_fresh_process_a_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_cli(_side: Side, args: list[str]) -> tuple[float, int, str]:
        calls.append(args)
        return 1.0, 0, "MIT"

    monkeypatch.setattr(runner, "run_cli", fake_cli)
    spec = {
        "files": {},
        "values": {"id": "MIT"},
        "commands": [{"name": "c", "args": ["resolve", "@value:id"]}],
    }
    job = Job(tmp_path / "i.json", tmp_path / "scratch", runs=3)
    out = runner.run_onecall(_side(tmp_path), spec, job)
    assert len(calls) == 4 and len(out["cases"]["c"]["ms"]) == 3

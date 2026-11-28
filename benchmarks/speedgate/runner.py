# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Run one side over the sets, each in a child process of its own.

A side is a frozen copy of a tree (``git archive``), named by path. The child
runs with ``PYTHONPATH=<side>/src``, so the editable install of the checkout
never answers, and reports which ``licenseid`` it imported. The home folder of
a child is a scratch one: never unset, never the real one."""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

WORKER: Final = Path(__file__).with_name("worker.py")
BOOT: Final = (
    "import runpy, sys; sys.argv = sys.argv[1:]; "
    "runpy.run_path(sys.argv[0], run_name='__main__')"
)
CLI_BOOT: Final = "from licenseid.cli import main; main()"
LOAD_LIMIT: Final = 2.0
STRESS_LIMIT_S: Final = 180.0
NOT_INHERITED: Final = frozenset({"PYTHONHOME", "PYTHONDONTWRITEBYTECODE"})


@dataclass(frozen=True)
class Side:
    """A frozen tree and what a child of it needs."""

    path: Path
    db: Path
    home: Path
    python: str = sys.executable

    def env(self) -> dict[str, str]:
        """The environment of a child: this side's ``src`` first, a scratch
        home, no ``PYTHONHOME``, a fixed hash seed (same order every run),
        and a byte-code cache of its own under the home, as an installed
        package has one: a caller's ``PYTHONDONTWRITEBYTECODE`` would add the
        compiling of every module to each fresh process."""
        env = {k: v for k, v in os.environ.items() if k not in NOT_INHERITED}
        env["PYTHONPATH"] = str(self.path / "src")
        env["HOME"] = str(self.home)
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONPYCACHEPREFIX"] = str(self.home / "pycache")
        return env


@dataclass(frozen=True)
class Job:
    """What a run reads and writes: the inputs file, a scratch folder, the
    runs of the one-call set and the items of the threads set."""

    inputs: Path
    scratch: Path
    runs: int = 11
    items: int = 100


def load_now() -> list[float]:
    """The 1, 5 and 15 minute load averages (the ``uptime`` figures)."""
    return [round(x, 2) for x in os.getloadavg()]


def is_loaded(start: list[float], end: list[float], limit: float = LOAD_LIMIT) -> bool:
    """Whether the machine was busy at either end of a run (1 minute load
    above *limit*): such a run is a ratio only, or rerun alone."""
    return max(start[0], end[0]) > limit


def run_child(
    side: Side, job: Job, args: list[str], timeout: float | None = None
) -> dict[str, Any]:
    """Run the worker once with *args* (the mode first); its result, or
    ``{"error": ...}``."""
    out = job.scratch / "child.json"
    out.unlink(missing_ok=True)
    cmd = [side.python, "-c", BOOT, str(WORKER), args[0]]
    cmd += ["--side", str(side.path), "--db", str(side.db)]
    cmd += ["--inputs", str(job.inputs), "--out", str(out), *args[1:]]
    try:
        done = subprocess.run(
            cmd,
            env=side.env(),
            cwd=str(side.home),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"over {timeout:g} s"}
    if not out.exists():
        tail = (done.stderr.strip().splitlines() or ["no output"])[-1]
        return {"error": f"exit {done.returncode}: {tail[:200]}"}
    loaded: dict[str, Any] = json.loads(out.read_text("utf-8"))
    return loaded


def timed(side: Side, job: Job, args: list[str]) -> dict[str, Any]:
    """A child run with the machine's load before and after, and its wall
    time."""
    start_load, started = load_now(), time.perf_counter()
    result = run_child(side, job, args)
    end_load = load_now()
    result.update(
        load_start=start_load,
        load_end=end_load,
        wall_s=time.perf_counter() - started,
        loaded=is_loaded(start_load, end_load),
    )
    return result


def run_stress(side: Side, job: Job) -> dict[str, Any]:
    """The stress set: one process per case, each with a time limit."""
    cases = json.loads(job.inputs.read_text("utf-8"))["sets"]["stress"]
    start_load, merged = load_now(), {}
    first: dict[str, Any] = {}
    for case in cases:
        key = case["key"]
        one = run_child(
            side, job, ["detect", "--set", "stress", "--only", key], STRESS_LIMIT_S
        )
        if "error" in one:
            merged[key] = {"error": one["error"], "rows": [], "cpu_ms": None}
        else:
            merged[key] = one["cases"][key]
            first = {k: v for k, v in one.items() if k != "cases"}
    end_load = load_now()
    return {
        **first,
        "cases": merged,
        "load_start": start_load,
        "load_end": end_load,
        "loaded": is_loaded(start_load, end_load),
    }


def run_cli(side: Side, args: list[str]) -> tuple[float, int, str]:
    """One CLI call in a fresh process: wall milliseconds, exit code and the
    first line of standard output."""
    cmd = [side.python, "-c", CLI_BOOT, "--db", str(side.db), *args]
    started = time.perf_counter()
    done = subprocess.run(
        cmd,
        env=side.env(),
        cwd=str(side.home),
        capture_output=True,
        text=True,
        check=False,
    )
    ms = 1e3 * (time.perf_counter() - started)
    return ms, done.returncode, (done.stdout.splitlines() or [""])[0][:80]


def run_onecall(side: Side, spec: dict[str, Any], job: Job) -> dict[str, Any]:
    """Each command of the one-call set ``job.runs`` times (one warm-up first,
    so byte-code files exist): the times and the output."""
    files = job.scratch / "onecall"
    files.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, text in spec["files"].items():
        paths[name] = files / f"{name}.txt"
        paths[name].write_text(text, encoding="utf-8")
    start_load, out = load_now(), {}
    for command in spec["commands"]:
        args = [_fill(a, spec, paths) for a in command["args"]]
        run_cli(side, args)
        times, code, line = [], 0, ""
        for _ in range(job.runs):
            ms, code, line = run_cli(side, args)
            times.append(ms)
        out[command["name"]] = {
            "ms": times,
            "min_ms": min(times),
            "code": code,
            "line": line,
        }
    end_load = load_now()
    return {
        "cases": out,
        "load_start": start_load,
        "load_end": end_load,
        "loaded": is_loaded(start_load, end_load),
    }


def _fill(arg: str, spec: dict[str, Any], paths: dict[str, Path]) -> str:
    if arg.startswith("@file:"):
        return str(paths[arg[6:]])
    if arg.startswith("@value:"):
        return str(spec["values"][arg[7:]])
    return arg

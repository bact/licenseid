# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Running one cell, and running the whole catalogue.

A cell runs as ``<shell> -c <command>`` in a work directory of its own,
with an environment built from scratch: nothing of the caller's leaks in,
so a run is reproducible and cannot reach the developer's own cache.

Cells that need a terminal get one from Python's ``pty`` module rather than
from ``script(1)``, whose options differ between BSD and GNU.
"""

from __future__ import annotations

import errno
import os
import pty
import select
import subprocess
import termios
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from tools.cli_matrix.config import Interpreter, RunConfig, Workspace
from tools.cli_matrix.model import Cell

#: Longest a cell may take before it counts as a hang.
TIMEOUT = 120

#: Exit status recorded for a cell that timed out.
TIMEOUT_RC = -999

#: A local port nothing listens on, so an escaped request fails at once.
DEAD_PROXY = "http://127.0.0.1:9"

Result = dict[str, Any]


@dataclass(frozen=True)
class Skipped:
    """A cell that was not run, and why."""

    id: str
    shell: str
    py: str
    reason: str


def build_env(
    interpreter: Interpreter,
    work: str,
    workspace: Workspace,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """The complete environment one cell runs in.

    HOME is inside the cell's own work directory, not shared: cells that
    write under HOME (``--clear-cache`` with no ``--db``) would otherwise
    race each other whenever two of them run at the same time.
    """
    env = {
        "PATH": f"{interpreter.python.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": f"{work}/home",
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
        "L": str(interpreter.script),
        "LU": str(interpreter.launcher),
        "DB": str(workspace.db),
        "F": str(workspace.files),
        "W": work,
        "O": str(workspace.out),
        "HTTPS_PROXY": DEAD_PROXY,
        "HTTP_PROXY": DEAD_PROXY,
    }
    env.update(extra or {})
    return env


def run_cell(
    cell: Cell,
    shell: str,
    interpreter: Interpreter,
    workspace: Workspace,
    extra_env: dict[str, str] | None = None,
) -> Result:
    """Run one cell and return everything the judge needs."""
    work = workspace.work / f"{cell.id}-{shell}-{interpreter.label}"
    _reset_dir(work)
    (work / "home").mkdir()
    env = build_env(interpreter, str(work), workspace, extra_env)
    argv = [shell, "-c", cell.cmd]
    started = time.monotonic()
    if cell.tty:
        rc, out, err = _run_on_pty(argv, env, str(work))
    else:
        rc, out, err = _run_plain(argv, env, str(work))
    duration = time.monotonic() - started
    listing = sorted(p.name for p in work.glob("x/*")) if (work / "x").is_dir() else []
    _make_writable(work)
    return {
        "id": cell.id,
        "shell": shell,
        "py": interpreter.label,
        "rc": rc,
        "out": out.replace("\r\n", "\n"),
        "err": err.replace("\r\n", "\n"),
        "dur": round(duration, 2),
        "work": str(work),
        "files": listing,
    }


def _run_plain(argv: list[str], env: dict[str, str], cwd: str) -> tuple[int, str, str]:
    """Run with pipes on all three streams."""
    try:
        proc = subprocess.run(
            argv,
            env=env,
            capture_output=True,
            timeout=TIMEOUT,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        return TIMEOUT_RC, partial.decode("utf-8", "replace"), "TIMEOUT"
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def _run_on_pty(argv: list[str], env: dict[str, str], cwd: str) -> tuple[int, str, str]:
    """Run with a pseudo-terminal as stdin, stdout and stderr.

    ``script(1)`` would do this too, but its argument order and its handling
    of the exit status differ between the BSD and GNU versions. A pty from
    the standard library behaves the same everywhere.

    The two streams are inseparable on a terminal, so everything comes back
    as stdout and stderr is empty -- which is also how a user sees it.
    """
    controller, follower = pty.openpty()
    _disable_echo(follower)
    try:
        with subprocess.Popen(
            argv,
            env=env,
            cwd=cwd,
            stdin=follower,
            stdout=follower,
            stderr=follower,
            start_new_session=True,
            close_fds=True,
        ) as proc:
            os.close(follower)
            follower = -1
            # End-of-file for anything that reads the terminal, so a command
            # waiting on stdin finishes instead of hitting the timeout.
            _write_eof(controller)
            output, timed_out = _drain(controller, proc)
            rc = TIMEOUT_RC if timed_out else proc.returncode
            return rc, output, "TIMEOUT" if timed_out else ""
    finally:
        if follower != -1:
            os.close(follower)
        os.close(controller)


def _disable_echo(fd: int) -> None:
    """Stop the terminal echoing input, which would pollute the output."""
    try:
        attrs = termios.tcgetattr(fd)
    except termios.error:
        return
    attrs[3] = attrs[3] & ~termios.ECHO  # lflag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _write_eof(fd: int) -> None:
    """Send the end-of-file character to the terminal."""
    try:
        os.write(fd, b"\x04")
    except OSError:
        pass


def _drain(controller: int, proc: subprocess.Popen[bytes]) -> tuple[str, bool]:
    """Read the terminal until the child is gone and nothing is left.

    Returns the output and whether the deadline ran out first.
    """
    chunks: list[bytes] = []
    deadline = time.monotonic() + TIMEOUT
    timed_out = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            proc.kill()
            break
        ready, _, _ = select.select([controller], [], [], min(remaining, 1.0))
        if ready:
            try:
                data = os.read(controller, 65536)
            except OSError as exc:
                # EIO is how a pty reports that the last writer has gone.
                if exc.errno != errno.EIO:
                    raise
                break
            if not data:
                break
            chunks.append(data)
        elif proc.poll() is not None:
            break
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return b"".join(chunks).decode("utf-8", "replace"), timed_out


def _reset_dir(work: os.PathLike[str]) -> None:
    """Start from an empty work directory, however the last run left it."""
    path = os.fspath(work)
    if os.path.exists(path):
        _make_writable(work)
        subprocess.run(["rm", "-rf", path], check=False)
    os.makedirs(path)


def _make_writable(work: os.PathLike[str]) -> None:
    """Give the owner access back, so a chmod inside a cell cannot block us."""
    subprocess.run(["chmod", "-R", "u+rwx", os.fspath(work)], check=False)


def plan(
    config: RunConfig, cells: list[Cell]
) -> tuple[list[tuple[Cell, str, Interpreter]], list[Skipped]]:
    """Split the catalogue into jobs to run and cells to skip, with reasons."""
    jobs: list[tuple[Cell, str, Interpreter]] = []
    skipped: list[Skipped] = []
    for cell in cells:
        if config.families and not any(
            cell.fam.startswith(prefix) for prefix in config.families
        ):
            continue
        reason = _skip_reason(config, cell)
        wanted = _shells_for(config, cell)
        if not wanted:
            asked = " ".join(cell.shells or ())
            wanted, reason = (
                [asked or "-"],
                reason or (f"none of the shells it asks for ({asked}) is configured"),
            )
        for shell in wanted:
            for interpreter in config.interpreters:
                if reason:
                    skipped.append(Skipped(cell.id, shell, interpreter.label, reason))
                else:
                    jobs.append((cell, shell, interpreter))
    return jobs, skipped


def _shells_for(config: RunConfig, cell: Cell) -> list[str]:
    """The configured shells this cell runs in, in configured order."""
    if cell.shells is None:
        return list(config.shells)
    return [shell for shell in cell.shells if shell in config.shells]


def _skip_reason(config: RunConfig, cell: Cell) -> str | None:
    """Why this cell must not run at all, or None when it may."""
    if cell.skip:
        return cell.skip
    if cell.needs_locale and config.locales and cell.needs_locale not in config.locales:
        return f"locale {cell.needs_locale} is not installed"
    return None


def execute(
    config: RunConfig, jobs: list[tuple[Cell, str, Interpreter]]
) -> list[Result]:
    """Run every job, up to ``--jobs`` at a time, keeping the planned order."""

    def run(job: tuple[Cell, str, Interpreter]) -> Result:
        cell, shell, interpreter = job
        return run_cell(cell, shell, interpreter, config.workspace)

    with ThreadPoolExecutor(max_workers=config.jobs) as pool:
        return list(pool.map(run, jobs))

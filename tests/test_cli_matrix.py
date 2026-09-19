# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for the CLI matrix tool in ``tools/cli_matrix``.

The matrix itself needs a real licence database and several minutes.
These tests are the fast half: every judging rule, the baseline diff, the
option checks, the skip reasons and the terminal runner, plus one
end-to-end smoke run over a handful of cells against a database built
here. Nothing touches the network or the real cache.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from cli_matrix_env import (
    bash_available,
    licenseid_script,
    make_cell,
    make_config,
    make_file_db,
    make_result,
)

from tools.cli_matrix import baseline as baseline_mod
from tools.cli_matrix import config as config_mod
from tools.cli_matrix import main as main_mod
from tools.cli_matrix.cells import build_cells
from tools.cli_matrix.config import (
    ConfigError,
    build_parser,
    configure_args,
    snapshot_protected,
)
from tools.cli_matrix.main import main, run
from tools.cli_matrix.report import write_coverage
from tools.cli_matrix.runner import plan, run_cell

#: Cells the smoke run covers: one per input source for ``match`` and for
#: ``is-osi``, plus a help cell. None of them needs more than MIT.
SMOKE_IDS = (
    "A1-001",
    "A1-002",
    "A1-004",
    "A1-006",
    "B1-001",
    "B1-002",
    "B1-004",
    "B1-006",
    "C2-006",
)


# ------------------------------------------------------------- baselines


def write_baseline_file(path: Path, keys: list[tuple[str, str]]) -> Path:
    """Write a baseline file holding *keys*."""
    body = "# header\n" + "".join(" ".join(k) + "\n" for k in keys)
    path.write_text(body, encoding="utf-8")
    return path


def test_baseline_reports_new_and_fixed(tmp_path: Path) -> None:
    """A flag not in the baseline is NEW; a baseline entry gone is FIXED."""
    path = write_baseline_file(
        tmp_path / "baseline.txt", [("A1-001", "bash"), ("A1-002", "zsh")]
    )
    rows = [
        make_result(id="A1-001", verdict="PASS"),
        make_result(id="A1-002", shell="zsh", verdict="FLAG"),
        make_result(id="A1-003", verdict="FLAG"),
    ]
    new, fixed = baseline_mod.compare(rows, baseline_mod.read_baseline(path))
    assert new == [("A1-003", "bash")]
    assert fixed == [("A1-001", "bash")]


def test_baseline_never_calls_an_unrun_cell_fixed(tmp_path: Path) -> None:
    """A filtered run must not report the rest of the matrix as fixed."""
    path = write_baseline_file(tmp_path / "baseline.txt", [("E2-082", "bash")])
    rows = [make_result(id="A1-001", verdict="PASS")]
    assert baseline_mod.compare(rows, baseline_mod.read_baseline(path)) == ([], [])


def test_baseline_round_trips(tmp_path: Path) -> None:
    """What the tool writes is what it reads back."""
    rows = [
        make_result(id="A1-001", verdict="FLAG"),
        make_result(id="B1-002", shell="sh", py="314", verdict="FLAG"),
        make_result(id="C1-003", verdict="PASS"),
    ]
    path = tmp_path / "baseline.txt"
    baseline_mod.write_baseline(path, rows)
    assert baseline_mod.read_baseline(path) == {("A1-001", "bash"), ("B1-002", "sh")}
    assert "# Run: 3 executions, 1 PASS, 0 OBSERVE, 2 FLAG" in path.read_text(
        encoding="utf-8"
    )


def test_baseline_ignores_the_interpreter_label(tmp_path: Path) -> None:
    """Labels are the caller's choice: a flag on any interpreter counts."""
    path = write_baseline_file(tmp_path / "baseline.txt", [("A1-001", "bash")])
    rows = [make_result(id="A1-001", py="whatever", verdict="FLAG")]
    assert baseline_mod.compare(rows, baseline_mod.read_baseline(path)) == ([], [])
    rows = [
        make_result(id="A1-001", py="310", verdict="PASS"),
        make_result(id="A1-001", py="314", verdict="FLAG"),
    ]
    assert baseline_mod.compare(rows, baseline_mod.read_baseline(path)) == ([], [])


def test_baseline_rejects_a_malformed_line(tmp_path: Path) -> None:
    """A line that is not two fields is an error, not a silent skip."""
    path = tmp_path / "baseline.txt"
    path.write_text("A1-001 bash 310\n", encoding="utf-8")
    with pytest.raises(ValueError, match="baseline.txt: invalid"):
        baseline_mod.read_baseline(path)


def test_shipped_baseline_is_readable() -> None:
    """The checked-in baseline parses, is sorted and names real cells."""
    lines = [
        line
        for line in baseline_mod.BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert lines
    assert lines == sorted(lines)
    ids = {cell.id for cell in build_cells().cells}
    assert {line.split()[0] for line in lines} <= ids
    assert baseline_mod.read_baseline(baseline_mod.BASELINE_PATH)


# ------------------------------------------------- options and workspace


def test_list_needs_no_database(capsys: pytest.CaptureFixture[str]) -> None:
    """``--list`` prints the catalogue without a database or interpreter."""
    assert main(["--list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(build_cells().cells)
    assert lines[0].startswith("A1-001\tA1\t")


def test_missing_database_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without ``--db`` the run refuses to start."""
    assert main([]) == 2
    assert "--db: missing" in capsys.readouterr().err


def test_database_inside_the_real_cache_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one path the tool may never open is rejected outright."""
    fake_home = tmp_path / "home"
    cache = fake_home / ".local" / "share" / "licenseid"
    cache.mkdir(parents=True)
    (cache / "licenses.db").write_bytes(b"")
    monkeypatch.setenv("HOME", str(fake_home))
    with pytest.raises(ConfigError, match="inside the real licenseid cache"):
        make_config(tmp_path / "out", cache / "licenses.db")


def _fake_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for the real cache: HOME points at a temporary directory."""
    fake_home = tmp_path / "home"
    cache = fake_home / ".local" / "share" / "licenseid"
    cache.mkdir(parents=True)
    (cache / "licenses.db").write_bytes(b"db")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return cache


def test_snapshot_is_stable_when_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Taking a snapshot twice gives the same answer and changes nothing."""
    cache = _fake_cache(tmp_path, monkeypatch)
    first = snapshot_protected()
    assert snapshot_protected() == first
    assert str(cache / "licenses.db") in first


@pytest.mark.parametrize("change", ["rewrite", "create", "delete", "remove_dir"])
def test_snapshot_sees_every_kind_of_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """A rewritten, new, deleted or vanished entry all show up."""
    cache = _fake_cache(tmp_path, monkeypatch)
    before = snapshot_protected()
    if change == "rewrite":
        (cache / "licenses.db").write_bytes(b"longer than before")
    elif change == "create":
        (cache / "extra.json").write_bytes(b"")
    elif change == "delete":
        (cache / "licenses.db").unlink()
    else:
        (cache / "licenses.db").unlink()
        cache.rmdir()
    assert snapshot_protected() != before


def test_run_fails_when_a_cell_touches_the_real_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The run exits 2 whatever the verdicts say, and names the file."""
    cache = _fake_cache(tmp_path, monkeypatch)
    db = make_file_db(tmp_path / "src.db")

    def touching_run(*_args: Any) -> tuple[list[Any], list[Any]]:
        (cache / "licenses.db").unlink()
        return [], []

    monkeypatch.setattr(main_mod, "self_check", lambda _config: None)
    monkeypatch.setattr(main_mod, "run", touching_run)
    monkeypatch.setattr(main_mod, "write_outputs", lambda *_args: None)
    assert main(["--db", str(db), "--out", str(tmp_path / "out")]) == 2
    err = capsys.readouterr().err
    assert "real cache: changed during the run" in err
    assert str(cache / "licenses.db") in err


def test_run_passes_when_the_real_cache_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard does not fire on a clean run."""
    _fake_cache(tmp_path, monkeypatch)
    db = make_file_db(tmp_path / "src.db")
    monkeypatch.setattr(main_mod, "self_check", lambda _config: None)
    monkeypatch.setattr(main_mod, "run", lambda *_args: ([], []))
    monkeypatch.setattr(main_mod, "write_outputs", lambda *_args: None)
    assert main(["--db", str(db), "--out", str(tmp_path / "out")]) == 0


def test_protected_dirs_cover_xdg_and_the_password_database_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard does not trust ``$HOME``: the passwd home counts too."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    entry = pwd.struct_passwd(("u", "x", 1, 1, "", str(tmp_path / "passwd"), "sh"))
    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: entry)
    dirs = {str(d) for d in config_mod.protected_dirs()}
    expected = {
        str((tmp_path / name / sub).resolve())
        for name, sub in (
            ("home", ".local/share/licenseid"),
            ("passwd", ".local/share/licenseid"),
            ("xdg", "licenseid"),
        )
    }
    assert expected <= dirs


def test_database_inside_the_xdg_cache_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$XDG_DATA_HOME/licenseid`` is protected like the default path."""
    xdg = tmp_path / "xdg"
    (xdg / "licenseid").mkdir(parents=True)
    (xdg / "licenseid" / "licenses.db").write_bytes(b"")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    with pytest.raises(ConfigError, match="inside the real licenseid cache"):
        make_config(tmp_path / "out", xdg / "licenseid" / "licenses.db")


def test_output_directory_inside_the_real_cache_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sandbox may not be built inside the cache it protects."""
    cache = _fake_cache(tmp_path, monkeypatch)
    db = make_file_db(tmp_path / "src.db")
    with pytest.raises(ConfigError, match="real licenseid cache"):
        make_config(cache / "out", db)


def test_no_running_cell_unsets_home_without_an_explicit_db() -> None:
    """A cell that clears HOME must name its database, or it hits the cache."""
    for cell in build_cells().cells:
        clears_home = "env -u HOME" in cell.cmd or "env -i" in cell.cmd
        if clears_home and not cell.skip:
            assert "--db" in cell.cmd, cell.id


def test_signal_cells_reset_sigint_first() -> None:
    """A background job starts with SIGINT ignored; INT cells must undo it."""
    for cell in build_cells().cells:
        if "kill -INT" in cell.cmd:
            assert "SIG_DFL" in cell.cmd, cell.id


def test_python_label_must_be_a_plain_name(tmp_path: Path) -> None:
    """A label becomes a directory name, so it cannot climb out of it."""
    db = make_file_db(tmp_path / "src.db")
    with pytest.raises(ConfigError, match="--python: invalid: label"):
        make_config(tmp_path / "out", db, "--python", f"x/../..={sys.executable}")


def test_update_baseline_needs_an_unfiltered_run(tmp_path: Path) -> None:
    """A subset of the matrix must not overwrite the whole baseline."""
    db = make_file_db(tmp_path / "src.db")
    for extra in (["E2"], ["--shell", "bash"]):
        with pytest.raises(ConfigError, match="--update-baseline"):
            make_config(tmp_path / "out", db, "--update-baseline", *extra)


def test_run_refuses_to_run_as_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cells create directories under odd HOME values; root would let them."""
    db = make_file_db(tmp_path / "src.db")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert main(["--db", str(db), "--out", str(tmp_path / "out")]) == 2
    assert "user: invalid: root" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (["--shell", "definitely-not-a-shell"], "--shell: not found"),
        (["--python", "broken=/nonexistent/python"], "--python: not found"),
        (["--update-baseline", "A1"], "--update-baseline: invalid"),
    ],
)
def test_option_validation(tmp_path: Path, extra: list[str], expected: str) -> None:
    """Every option is checked before a single cell runs."""
    db = make_file_db(tmp_path / "src" / "licenses.db")
    with pytest.raises(ConfigError, match=expected):
        make_config(tmp_path / "out", db, *extra)


def test_interpreter_without_licenseid_is_refused(tmp_path: Path) -> None:
    """An interpreter that cannot run licenseid is named as such."""
    fake = tmp_path / "bin" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    db = make_file_db(tmp_path / "src" / "licenses.db")
    with pytest.raises(ConfigError, match="no 'licenseid' script next to"):
        make_config(tmp_path / "out", db, "--python", f"fake={fake}")


def test_the_database_is_copied_not_used(tmp_path: Path) -> None:
    """Cells point at the copy, so the original cannot be written to."""
    db = make_file_db(tmp_path / "src" / "licenses.db")
    config = make_config(tmp_path / "out", db)
    assert config.workspace.db != db
    assert config.workspace.db.read_bytes() == db.read_bytes()
    assert config.workspace.files.joinpath("mit.txt").is_file()


# ------------------------------------------------------------ skip rules


def test_skips_the_cell_that_would_open_the_real_cache(tmp_path: Path) -> None:
    """The HOME-unset cells never run, whatever else is configured."""
    config = make_config(
        tmp_path / "out", make_file_db(tmp_path / "src" / "licenses.db")
    )
    cells = [c for c in build_cells().cells if c.fam == "E7"]
    _, skipped = plan(config, cells)
    reasons = {item.reason for item in skipped}
    assert any("real user cache" in reason for reason in reasons)
    assert {item.id for item in skipped} == {"E7-005", "E7-006", "E7-007", "E7-008"}


def test_skips_a_cell_whose_locale_is_absent(tmp_path: Path) -> None:
    """A locale the machine lacks is a skip with a reason, not a failure."""
    config = make_config(
        tmp_path / "out", make_file_db(tmp_path / "src" / "licenses.db")
    )
    config.locales = frozenset({"C", "POSIX"})
    cells = [make_cell(id="E2-001", fam="E2", needs_locale="ja_JP.eucJP")]
    jobs, skipped = plan(config, cells)
    assert not jobs
    assert "locale ja_JP.eucJP is not installed" in skipped[0].reason


def test_skips_a_cell_whose_shell_is_not_configured(tmp_path: Path) -> None:
    """A cell asking for a shell nobody configured is skipped, not failed."""
    config = make_config(
        tmp_path / "out",
        make_file_db(tmp_path / "src" / "licenses.db"),
        "--shell",
        "sh",
    )
    jobs, skipped = plan(config, [make_cell(shells=("bash",))])
    assert not jobs
    assert "is configured" in skipped[0].reason


# ------------------------------------------------------------- reporting


def test_coverage_checklist_counts_what_ran(tmp_path: Path) -> None:
    """The checklist reports the flags the run touched, and the gaps."""
    cells = build_cells().by_id()
    rows = [
        make_result(id="A1-007", fam="A1", verdict="PASS"),
    ]
    path = tmp_path / "coverage.md"
    write_coverage(path, rows, cells)
    text = path.read_text(encoding="utf-8")
    assert "| match | --json | 1 | bash | 310 |" in text
    assert "| match | --diff | 0 |  |  |" in text
    assert "Uncovered pairs:" in text


# -------------------------------------------------------- terminal runner


@pytest.mark.skipif(not bash_available(), reason="bash is not installed")
def test_pty_runner_gives_the_child_a_terminal(tmp_path: Path) -> None:
    """A tty cell really does see a terminal on stdout, with no echo."""
    config = make_config(
        tmp_path / "out", make_file_db(tmp_path / "src" / "licenses.db")
    )
    cell = make_cell(cmd='test -t 1 && test -t 0 && echo "tty ok"', tty=True)
    result = run_cell(cell, "bash", config.interpreters[0], config.workspace)
    assert result["rc"] == 0
    assert result["out"].strip() == "tty ok"
    assert result["err"] == ""


@pytest.mark.skipif(not bash_available(), reason="bash is not installed")
def test_plain_runner_has_no_terminal(tmp_path: Path) -> None:
    """Without the tty flag the streams are pipes, as in a script."""
    config = make_config(
        tmp_path / "out", make_file_db(tmp_path / "src" / "licenses.db")
    )
    cell = make_cell(cmd='test -t 1 || echo "no tty"')
    result = run_cell(cell, "bash", config.interpreters[0], config.workspace)
    assert result["out"].strip() == "no tty"


# ---------------------------------------------------------------- end to end


def _smoke_config(tmp_path: Path) -> Any:
    """A bash-only, current-interpreter configuration for the smoke run."""
    return make_config(
        tmp_path / "out",
        make_file_db(tmp_path / "src" / "licenses.db"),
        "--shell",
        "bash",
        "--jobs",
        "4",
    )


@pytest.mark.skipif(not bash_available(), reason="bash is not installed")
@pytest.mark.skipif(
    licenseid_script() is None, reason="no licenseid script next to sys.executable"
)
def test_smoke_run_has_no_flags(tmp_path: Path) -> None:
    """A handful of real cells against a minimal database: nothing flags."""
    config = _smoke_config(tmp_path)
    cells = [c for c in build_cells().cells if c.id in SMOKE_IDS]
    assert len(cells) == len(SMOKE_IDS)
    rows, skipped = run(config, cells)
    assert not skipped
    flagged = [(r["id"], r["notes"]) for r in rows if r["verdict"] == "FLAG"]
    assert not flagged, flagged
    assert {r["id"] for r in rows} == set(SMOKE_IDS)


@pytest.mark.skipif(not bash_available(), reason="bash is not installed")
@pytest.mark.skipif(
    licenseid_script() is None, reason="no licenseid script next to sys.executable"
)
def test_a_match_cell_opens_no_socket(tmp_path: Path) -> None:
    """A plain match must not touch the network, however the env is set.

    A ``sitecustomize`` on the cell's path records every connection attempt
    before it can be made, so the proof does not depend on the attempt
    failing.
    """
    config = _smoke_config(tmp_path)
    watcher = tmp_path / "watch"
    log = tmp_path / "sockets.log"
    _write_socket_watcher(watcher, log)
    cell = make_cell(cmd="$L --db $DB match --bold $F/mit.txt", kind="match")
    result = run_cell(
        cell,
        "bash",
        config.interpreters[0],
        config.workspace,
        extra_env={"PYTHONPATH": str(watcher)},
    )
    assert result["rc"] == 0, result
    assert result["out"].strip() == "MIT"
    assert not log.exists(), log.read_text(encoding="utf-8")


def _write_socket_watcher(directory: Path, log: Path) -> None:
    """Write a sitecustomize that records any outgoing connection."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sitecustomize.py").write_text(
        "import socket\n"
        f"_LOG = {str(log)!r}\n"
        "_real = socket.socket.connect\n"
        "def connect(self, address):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(repr(address) + '\\n')\n"
        "    return _real(self, address)\n"
        "socket.socket.connect = connect\n",
        encoding="utf-8",
    )


def test_socket_watcher_would_notice_a_connection(tmp_path: Path) -> None:
    """The watcher itself works: a connection attempt is recorded.

    Without this, the test above would keep passing if the watcher ever
    stopped being installed.
    """
    log = tmp_path / "sockets.log"
    watcher = tmp_path / "watch"
    _write_socket_watcher(watcher, log)
    attempt = (
        "import socket\n"
        "s = socket.socket()\n"
        "s.settimeout(0.2)\n"
        "try:\n"
        "    s.connect(('127.0.0.1', 9))\n"
        "except OSError:\n"
        "    pass\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", attempt],
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(watcher)},
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert log.is_file()


# ------------------------------------------------------------- catalogue


def test_every_cell_id_is_unique() -> None:
    """Identifiers are the key the baseline is written in."""
    ids = [cell.id for cell in build_cells().cells]
    assert len(ids) == len(set(ids))


def test_no_cell_hard_codes_a_developer_path() -> None:
    """Cells reach their inputs through the exported environment only."""
    for cell in build_cells().cells:
        assert "/Users/" not in cell.cmd
        assert "venv" not in cell.cmd


def test_windows_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool says so instead of half-working."""
    monkeypatch.setattr("tools.cli_matrix.config.os.name", "nt")
    with pytest.raises(ConfigError, match="platform: unsupported"):
        configure_args(build_parser().parse_args(["--db", "x"]))

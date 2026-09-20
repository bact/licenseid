# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Options, the checks they have to survive, and the workspace they set up.

Nothing here is hard-coded to one machine: every path, interpreter and
shell comes from an option with a sensible default. The checks are the
safety guarantee -- they run before a single cell does, so a run either
starts from a workspace that cannot reach the real cache or does not start.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tools.cli_matrix.fixtures import make_files
from tools.cli_matrix.model import KNOWN_SHELLS

#: Where the tool writes everything, relative to the repository root.
DEFAULT_OUT = ".cli-matrix"

#: Environment variable read when ``--db`` is not given.
DB_ENV = "LICENSEID_MATRIX_DB"

DEFAULT_JOBS = 6

#: The launcher, as an absolute path, for the generated wrapper scripts.
LAUNCHER_PATH = Path(__file__).resolve().parent / "launcher.py"

REPO_ROOT = Path(__file__).resolve().parents[2]

#: An interpreter label becomes part of a directory name.
_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class ConfigError(Exception):
    """A usage error: the run cannot start."""


@dataclass(frozen=True)
class Interpreter:
    """One Python installation with licenseid available next to it."""

    label: str
    python: Path
    script: Path
    launcher: Path


@dataclass
class Workspace:
    """The directories a run owns. Nothing outside these is written to."""

    out: Path
    work: Path
    home: Path
    files: Path
    bin: Path
    db: Path


@dataclass
class RunConfig:
    """Everything a run needs, after validation."""

    workspace: Workspace
    interpreters: list[Interpreter]
    shells: list[str]
    jobs: int = DEFAULT_JOBS
    families: list[str] = field(default_factory=list)
    locales: frozenset[str] = frozenset()
    missing_shells: list[str] = field(default_factory=list)
    list_only: bool = False
    compare: bool = False
    check: bool = False
    update_baseline: bool = False


def protected_dirs() -> list[Path]:
    """Directories the tool must never open: the real licenseid cache.

    Computed from the environment rather than by calling licenseid, so that
    the tool depends on nothing it is meant to test.
    """
    import pwd  # POSIX only; imported here so Windows reaches the refusal first

    homes = [Path.home()]
    try:
        # With HOME unset, Python falls back to the password database, which
        # is how an earlier harness reached the real cache.
        homes.append(Path(pwd.getpwuid(os.getuid()).pw_dir))
    except KeyError:
        pass
    dirs = [home / ".local" / "share" / "licenseid" for home in homes]
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        dirs.append(Path(xdg).expanduser() / "licenseid")
    return [_resolve(d) for d in dirs]


def snapshot_protected() -> dict[str, tuple[int, int]]:
    """Name -> (size, mtime in ns) of every entry in the protected directories.

    Taken before and after a run: any difference means a cell reached the
    real cache, and the run fails whatever the cell verdicts say. Only
    ``stat`` is used, so taking the snapshot never opens or changes a file.
    """
    entries: dict[str, tuple[int, int]] = {}
    for directory in protected_dirs():
        if not directory.is_dir():
            entries[str(directory)] = (-1, -1)
            continue
        for path in sorted(directory.rglob("*")):
            info = path.lstat()
            entries[str(path)] = (info.st_size, info.st_mtime_ns)
    return entries


def _resolve(path: Path) -> Path:
    """*path* made absolute, resolving symlinks where they exist."""
    return Path(os.path.abspath(path.expanduser())).resolve()


def _absolute(path: Path) -> Path:
    """*path* made absolute, keeping symlinks intact.

    A virtual environment's ``bin/python`` is a symlink to the interpreter
    it was built from, and its ``licenseid`` script sits next to the
    *symlink*, not next to the target.
    """
    return Path(os.path.abspath(path.expanduser()))


def _is_within(path: Path, parent: Path) -> bool:
    """True when *path* is *parent* or lies underneath it."""
    return path == parent or parent in path.parents


def build_parser() -> argparse.ArgumentParser:
    """The command-line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.cli_matrix",
        description="Run the licenseid CLI matrix and judge every cell.",
    )
    parser.add_argument(
        "family",
        nargs="*",
        help="only run cells whose family starts with this prefix (e.g. E2)",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get(DB_ENV),
        help=(
            "a real licence database to test against (or set "
            f"{DB_ENV}). It is copied into the work directory; the "
            "original is never opened by a cell."
        ),
    )
    parser.add_argument(
        "--python",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="an interpreter to test, repeatable (default: current=<sys.executable>)",
    )
    parser.add_argument(
        "--shell",
        action="append",
        default=[],
        metavar="NAME",
        help=f"a shell to test, repeatable (default: those of {' '.join(KNOWN_SHELLS)})",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="DIR",
        help=f"output directory (default: <repo>/{DEFAULT_OUT})",
    )
    parser.add_argument(
        "--jobs", type=int, default=DEFAULT_JOBS, help="cells to run at once"
    )
    parser.add_argument(
        "--list", action="store_true", help="print cell ids and descriptions only"
    )
    parser.add_argument(
        "--compare", action="store_true", help="report new and fixed flags"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="like --compare, but exit 1 when there are new flags",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite baseline.txt from this run (full runs only)",
    )
    return parser


def configure(argv: list[str] | None = None) -> RunConfig:
    """Parse *argv*, check everything, and prepare the workspace."""
    return configure_args(build_parser().parse_args(argv))


def configure_args(args: argparse.Namespace) -> RunConfig:
    """Check already-parsed options, and prepare the workspace."""
    if os.name == "nt":
        raise ConfigError(
            "platform: unsupported: Windows has no POSIX shells, signals or"
            " file modes to exercise; run this tool on macOS or Linux"
        )
    if args.update_baseline and (args.family or args.shell):
        raise ConfigError(
            "--update-baseline: invalid: only a full run, without a family"
            " or --shell filter, may rewrite the baseline"
        )
    workspace = _prepare_workspace(args.out, args.db)
    config = RunConfig(
        workspace=workspace,
        interpreters=_interpreters(args.python, workspace),
        shells=_shells(args.shell),
        jobs=max(1, args.jobs),
        families=list(args.family),
        locales=available_locales(),
        missing_shells=_missing_shells(args.shell),
        list_only=args.list,
        compare=args.compare or args.check,
        check=args.check,
        update_baseline=args.update_baseline,
    )
    _write_wrappers(config)
    return config


def _prepare_workspace(out_arg: str | None, db_arg: str | None) -> Workspace:
    """Create the output directories and copy the database into them."""
    if not db_arg:
        raise ConfigError(
            f"--db: missing; pass a licence database path or set {DB_ENV}"
        )
    source = _resolve(Path(db_arg))
    if not source.is_file():
        raise ConfigError(f"--db: not found: {db_arg}")
    for guarded in protected_dirs():
        if _is_within(source, guarded):
            raise ConfigError(
                f"--db: invalid: {db_arg} is inside the real licenseid cache"
                f" ({guarded}); copy it elsewhere first"
            )
    out = _resolve(Path(out_arg) if out_arg else REPO_ROOT / DEFAULT_OUT)
    for guarded in protected_dirs():
        if _is_within(out, guarded):
            raise ConfigError(
                f"--out: invalid: {out} is inside the real licenseid cache"
            )
    workspace = Workspace(
        out=out,
        work=out / "work",
        home=out / "home",
        files=out / "files",
        bin=out / "bin",
        db=out / "db" / "licenses.db",
    )
    for directory in (
        workspace.work,
        workspace.home,
        workspace.bin,
        workspace.db.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    make_files(workspace.files)
    shutil.copyfile(source, workspace.db)
    return workspace


def _interpreters(specs: list[str], workspace: Workspace) -> list[Interpreter]:
    """Resolve ``LABEL=PATH`` specifications, checking each installation."""
    if not specs:
        specs = [f"current={sys.executable}"]
    interpreters: list[Interpreter] = []
    seen: set[str] = set()
    for spec in specs:
        label, _, raw = spec.partition("=")
        if not raw:
            raise ConfigError(f"--python: invalid: {spec!r}; expected LABEL=PATH")
        if not _LABEL_RE.fullmatch(label):
            raise ConfigError(
                f"--python: invalid: label {label!r}; use letters, digits,"
                " '.', '_' or '-'"
            )
        if label in seen:
            raise ConfigError(f"--python: invalid: duplicate label {label!r}")
        seen.add(label)
        python = _absolute(Path(raw))
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ConfigError(f"--python: not found: {raw}")
        script = python.parent / "licenseid"
        if not script.is_file():
            raise ConfigError(
                f"--python: invalid: no 'licenseid' script next to {python};"
                " install licenseid into that environment"
            )
        interpreters.append(
            Interpreter(
                label=label,
                python=python,
                script=script,
                launcher=workspace.bin / f"offline-{label}",
            )
        )
    return interpreters


def _shells(requested: list[str]) -> list[str]:
    """The shells to run in, defaulting to those of ``KNOWN_SHELLS`` present."""
    if not requested:
        found = [name for name in KNOWN_SHELLS if shutil.which(name)]
        if not found:
            raise ConfigError(
                f"--shell: not found: none of {' '.join(KNOWN_SHELLS)} is on PATH"
            )
        return found
    for name in requested:
        if not shutil.which(name):
            raise ConfigError(f"--shell: not found: {name}")
    return list(dict.fromkeys(requested))


def _missing_shells(requested: list[str]) -> list[str]:
    """Known shells not present, when the default set is used."""
    if requested:
        return []
    return [name for name in KNOWN_SHELLS if not shutil.which(name)]


def available_locales() -> frozenset[str]:
    """Locale names ``locale -a`` reports, or empty when it cannot be run."""
    try:
        proc = subprocess.run(
            ["locale", "-a"],
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    text = proc.stdout.decode("utf-8", "replace")
    return frozenset(line.strip() for line in text.splitlines() if line.strip())


def _write_wrappers(config: RunConfig) -> None:
    """Write one ``offline-<label>`` wrapper per interpreter into ``bin/``."""
    for interpreter in config.interpreters:
        interpreter.launcher.write_text(
            f'#!/bin/sh\nexec {interpreter.python} {LAUNCHER_PATH} "$@"\n',
            encoding="utf-8",
        )
        interpreter.launcher.chmod(0o755)

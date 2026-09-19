# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Families E1 to E6: how the command is attached to the world.

``E1`` shell x interpreter, ``E2`` locale and encoding, ``E3`` stdin,
``E4`` stdout and colour, ``E5`` stderr, ``E6`` working directory.

Families E7 to E11, which vary the process's own resources rather than
its streams, live in ``process_env``.
"""

from __future__ import annotations

import re

from tools.cli_matrix.cells.core_commands import CORE
from tools.cli_matrix.model import EVERY_SHELL, CellSet, licenseid

LOCALES = [
    ("LC_ALL=C LANG=C", "C"),
    ("LC_ALL=POSIX", "POSIX"),
    ("LC_ALL=en_US.UTF-8", "en_US.UTF-8"),
    ("LC_ALL=C.UTF-8", "C.UTF-8 (may not exist)"),
    ("env -u LC_ALL -u LANG -u LC_CTYPE", "unset"),
    ("LC_ALL=C PYTHONUTF8=1", "C + UTF-8 mode"),
    ("PYTHONIOENCODING=ascii", "io ascii"),
    ("PYTHONIOENCODING=latin-1", "io latin-1"),
    ("LC_ALL=en_US.ISO8859-1", "latin1 locale"),
    ("LC_ALL=ja_JP.eucJP", "eucJP locale"),
    ("PYTHONIOENCODING=utf-8:surrogateescape", "surrogateescape"),
]

STDIN_KINDS = {
    "devnull": "< /dev/null",
    "file": "< $F/mit.txt",
    "pipe": "cat $F/mit.txt |",
    "empty pipe": "printf '' |",
    "closed": "<&-",
    "ws pipe": "printf ' \\n' |",
    "large 2MB pipe": "head -c 2000000 /dev/zero | tr '\\0' 'a' |",
    "binary pipe": "cat $F/logo.png |",
}

STDOUT_KINDS = {
    "file": "> $W/out.txt; cat $W/out.txt",
    "closed": ">&-",
    "head -c 0 (SIGPIPE)": "| (exec 0<&-; sleep 1)",
    "head -n 1": "| head -n 1",
    "| true": "| true",
    "/dev/null": '> /dev/null; echo "rc=$?"',
    "ulimit -f 0 to file": "> $W/o.txt",
}

STDERR_KINDS = {
    "file": '2> $W/err.txt; echo "[stderr]"; cat $W/err.txt',
    "closed": "2>&-",
    "merged": "2>&1",
    "/dev/null": "2> /dev/null",
    "swapped": "3>&1 1>&2 2>&3",
}

_DEEP = "/".join(["d"] * 60)

CWD_KINDS = {
    "relative dot": "cd $F && ",
    "other dir": "cd / && ",
    "spaces dir": 'mkdir -p "$W/s p/d" && cd "$W/s p/d" && ',
    "deleted cwd": "mkdir $W/gone && cd $W/gone && rmdir $W/gone && ",
    "very deep": f"mkdir -p $W/{_DEEP} && cd $W/{_DEEP} && ",
}

#: HOME shapes the default database path has to cope with. ``env -u HOME``
#: is present but permanently skipped: with HOME unset, Python falls back

_COLOUR_ENVS = (
    "TERM=dumb",
    "TERM=xterm-256color",
    "NO_COLOR=1 TERM=xterm",
    "FORCE_COLOR=1",
    "CLICOLOR_FORCE=1 TERM=dumb",
)

_LOCALE_RE = re.compile(r"LC_ALL=([A-Za-z][\w.@-]*)")


def add_cells(cells: CellSet) -> None:
    """Add families E1 to E6 to *cells*."""
    _add_shell_and_python(cells)
    _add_locales(cells)
    _add_stdin(cells)
    _add_stdout(cells)
    _add_stderr(cells)
    _add_cwd(cells)


def _add_shell_and_python(cells: CellSet) -> None:
    """E1: every core command in every configured shell and interpreter."""
    for desc, cmd, kind, exit_code in CORE:
        cells.add(
            "E1",
            f"shell x python: {desc}",
            cmd,
            kind=kind,
            exp_exit=exit_code,
            shells=EVERY_SHELL,
            progress=kind == "update",
            outflags=_out_flags(cmd),
        )


def _out_flags(cmd: str) -> frozenset[str]:
    """The output flag a core command carries, if any."""
    if "--json" in cmd:
        return frozenset({"json"})
    if "--bold" in cmd:
        return frozenset({"bold"})
    return frozenset()


def _add_locales(cells: CellSet) -> None:
    """E2: the same answers under every locale and I/O encoding."""
    for env, name in LOCALES:
        match = _LOCALE_RE.search(env)
        needs = match.group(1) if match else None
        for desc, cmd, kind, exit_code in CORE[:6]:
            cells.add(
                "E2",
                f"locale {name}: {desc}",
                f"{env} {cmd}" if not cmd.startswith("mkdir") else cmd,
                kind=kind,
                exp_exit=exit_code,
                group=f"E2-{desc}",
                needs_locale=needs,
            )
        cells.add(
            "E2",
            f"locale {name}: non-ASCII file name",
            f"{env} " + licenseid('match --bold "$F/\u00fcn\u00ef.txt"'),
            kind="match",
            exp_exit=0,
            group="E2-nonascii-name",
            needs_locale=needs,
        )
        cells.add(
            "E2",
            f"locale {name}: non-ASCII --text",
            f"{env} "
            + licenseid(
                "match --bold --text 'Copyright \u00a9 Zo\u00eb Permission is"
                " hereby granted, free of charge, to any person obtaining a copy'"
            ),
            kind="match",
            exp_exit=None,
            group="E2-nonascii-text",
            needs_locale=needs,
        )
        cells.add(
            "E2",
            f"locale {name}: non-ASCII --id",
            f"{env} " + licenseid("match --id 'MIT\u00e9'"),
            kind="match",
            group="E2-nonascii-id",
            needs_locale=needs,
        )


def _add_stdin(cells: CellSet) -> None:
    """E3: every shape stdin can have, with and without other input."""
    for name, redirect in STDIN_KINDS.items():
        for desc, cmd, kind, _ in (CORE[0], CORE[4], CORE[6]):
            piped = redirect.endswith("|")
            given = "given" if "no input" not in desc else "absent"
            cells.add(
                "E3",
                f"stdin={name}: {desc} (with input {given})",
                f"{redirect} {cmd}" if piped else f"{cmd} {redirect}",
                kind=kind,
                xenv=name not in ("closed",),
            )
        for sub, kind in (("match", "match"), ("is-osi", "predicate")):
            cells.add(
                "E3",
                f"stdin={name}: {sub} (no input given at all)",
                _bare(redirect, licenseid(sub)),
                kind=kind,
            )
    for desc, cmd, kind, _ in CORE[:7]:
        cells.add("E3", f"stdin=tty: {desc}", cmd, kind=kind, tty=True, xenv=False)


def _bare(redirect: str, cmd: str) -> str:
    """*cmd* with no input at all beyond *redirect* on stdin."""
    if redirect.endswith("|"):
        return f"{redirect} {cmd}"
    return f"{cmd} {redirect}"


def _add_stdout(cells: CellSet) -> None:
    """E4: every shape stdout can have, and every colour hint."""
    for name, redirect in STDOUT_KINDS.items():
        for desc, cmd, kind, _ in (CORE[0], CORE[2], CORE[3], CORE[4]):
            # ulimit -f 0 forbids writing any file at all; POSIX, and the
            # limit applies to the redirect, not to the CLI's own writes.
            pre = "ulimit -f 0; " if name.startswith("ulimit") else ""
            cells.add(
                "E4",
                f"stdout={name}: {desc}",
                f"{pre}{cmd} {redirect}",
                kind=kind,
                xenv=name in ("file", "/dev/null"),
                group=f"E4-{desc}" if name == "file" else None,
            )
    for desc, cmd, kind, _ in (CORE[0], CORE[2], CORE[3], CORE[4]):
        cells.add("E4", f"stdout=tty: {desc}", cmd, kind=kind, tty=True, xenv=False)
        for colour in _COLOUR_ENVS:
            if "diff" in desc:
                cells.add(
                    "E4",
                    f"stdout=tty colour env {colour}: {desc}",
                    f"{colour} {cmd}",
                    kind=kind,
                    tty=True,
                    xenv=False,
                )


def _add_stderr(cells: CellSet) -> None:
    """E5: every shape stderr can have, including closed."""
    for name, redirect in STDERR_KINDS.items():
        for desc, cmd, kind, _ in (CORE[1], CORE[6], CORE[7], CORE[5]):
            cells.add(
                "E5",
                f"stderr={name}: {desc}",
                f"{cmd} {redirect}",
                kind=kind,
                merged=name in ("merged", "swapped", "file"),
                xenv=name not in ("closed",),
            )
    for desc, cmd, kind, _ in (CORE[1], CORE[6]):
        cells.add(
            "E5",
            f"stdout+stderr closed: {desc}",
            f"{cmd} >&- 2>&-",
            kind=kind,
            xenv=False,
        )
        cells.add(
            "E5",
            f"all three closed: {desc}",
            f"{cmd} <&- >&- 2>&-",
            kind=kind,
            xenv=False,
        )


def _add_cwd(cells: CellSet) -> None:
    """E6: relative and absolute paths from unusual working directories."""
    for name, pre in CWD_KINDS.items():
        cells.add(
            "E6",
            f"cwd={name}: relative file + relative db",
            f"{pre}$L --db $DB match --bold ../mit.txt 2>&1 | head -c 300; true",
            kind="other",
            xenv=False,
        )
        cells.add(
            "E6",
            f"cwd={name}: absolute file",
            f"{pre}{licenseid('match --bold $F/mit.txt')}",
            kind="match",
            exp_exit=0 if name != "deleted cwd" else None,
            xenv=name != "deleted cwd",
        )

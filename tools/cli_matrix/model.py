# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The cell model and the vocabulary every cell family is built from.

A *cell* is one command line plus what the matrix expects of it. Cells are
declarative: they hold no state and never run anything themselves, so the
whole catalogue can be listed, filtered and counted without touching a
shell.

Every cell command is a shell string on purpose. Building an argument list
would hide exactly the quoting, globbing and word-splitting differences
between shells that this tool exists to find.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Any

#: Shell a cell runs in unless it asks for more.
DEFAULT_SHELL = "bash"

#: Shells the matrix looks for, in the order results are compared in.
KNOWN_SHELLS = ("bash", "zsh", "sh", "dash", "ksh")

#: ``Cell.shells`` set to this means "every shell configured for the run".
EVERY_SHELL: tuple[str, ...] | None = None

#: Subcommands of the CLI, and the predicate subset of them.
CMDS = ["update", "match", "is-osi", "is-fsf", "is-open", "is-free", "is-spdx"]
PREDS = CMDS[2:]

#: A fragment of the MIT licence: enough text for a confident match.
FRAG = "Permission is hereby granted, free of charge, to any person obtaining a copy"

#: Text that matches no licence.
OTHER = "The quick brown fox jumps over the lazy dog near the river bank"

#: The diagnostic a command must print when no input reaches it at all.
MISSING = r"ERROR: input: missing; pass a file, an ID, --text, --id or stdin"

#: Input sources a command can be fed from.
SRC = ["arg_id", "arg_file", "text", "id", "stdin", "none"]

#: Every combination of the three output-shaping flags.
OUTS: list[tuple[str, ...]] = [
    (),
    ("json",),
    ("bold",),
    ("diff",),
    ("json", "bold"),
    ("json", "diff"),
    ("bold", "diff"),
    ("json", "bold", "diff"),
]

#: Licence identifiers the predicate consistency family asks about.
IDS = [
    "MIT",
    "Apache-2.0",
    "GPL-3.0-only",
    "GPL-2.0-only",
    "GPL-2.0+",
    "CC0-1.0",
    "Unlicense",
    "BSD-3-Clause",
    "MIT WITH Font-exception-2.0",
    "AGPL-3.0-or-later",
    "Zlib",
    "LicenseRef-x",
    "mit",
    "Nope-1.0",
]

_SUBCOMMAND_RE = re.compile(
    r"\$L(?: --db \S+)? ?(update|match|is-osi|is-fsf|is-open|is-free|is-spdx)?"
)
_FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)")


@dataclass
class Cell:
    """One command line and everything the matrix knows about it.

    ``cmd`` is a shell fragment. It may use the environment the runner
    exports: ``$L`` (the ``licenseid`` script of the interpreter under
    test), ``$LU`` (its offline launcher wrapper), ``$DB`` (the database
    copy), ``$F`` (the fixture directory), ``$W`` (this cell's own work
    directory) and ``$HOME`` (a per-run home inside the output directory).
    """

    id: str
    fam: str
    desc: str
    cmd: str
    #: match | predicate | update | help | other -- picks the contract judged.
    kind: str = "other"
    #: Which of json / bold / diff the command was asked for.
    outflags: frozenset[str] = frozenset()
    #: Exit status required, or None when the behaviour is unspecified.
    exp_exit: int | frozenset[int] | None = None
    #: Regex that must fullmatch stdout, when the shape is specified.
    exp_out: str | None = None
    #: Regex that must be found in stderr, when a diagnostic is required.
    exp_err: str | None = None
    #: Shells to run in; ``EVERY_SHELL`` (None) means all configured ones.
    shells: tuple[str, ...] | None = (DEFAULT_SHELL,)
    #: Cells sharing a group must agree on (exit status, stdout).
    group: str | None = None
    #: Run with a pseudo-terminal as stdin, stdout and stderr.
    tty: bool = False
    #: The command itself merges stderr into stdout, so streams cannot be judged.
    merged: bool = False
    #: Free-text progress lines are expected on stderr.
    progress: bool = False
    #: Result must agree across shells and interpreters.
    xenv: bool = True
    #: A valid ``--top`` value, used to bound the number of results.
    top: int | None = None
    #: Locale this cell needs; skipped when ``locale -a`` does not list it.
    needs_locale: str | None = None
    #: Non-empty when the cell must never run, with the reason why.
    skip: str | None = None
    #: ``subcommand:flag`` and ``src:...`` labels, for the coverage checklist.
    tags: set[str] = field(default_factory=set)


class CellSet:
    """An ordered catalogue of cells, numbered per family as they are added."""

    def __init__(self) -> None:
        self.cells: list[Cell] = []

    def add(self, fam: str, desc: str, cmd: str, **kw: Any) -> Cell:
        """Append a cell to family *fam* and return it.

        The identifier is ``<family>-<n>``, counted within the family, so a
        cell keeps its identifier as long as nothing is inserted before it.
        """
        seq = sum(1 for c in self.cells if c.fam == fam) + 1
        cell = Cell(id=f"{fam}-{seq:03d}", fam=fam, desc=desc, cmd=cmd, **kw)
        cell.tags.update(_command_tags(cmd))
        self.cells.append(cell)
        return cell

    def by_id(self) -> dict[str, Cell]:
        """The catalogue keyed by cell identifier."""
        return {c.id: c for c in self.cells}


def _command_tags(cmd: str) -> set[str]:
    """``subcommand:flag`` labels read off a command string."""
    match = _SUBCOMMAND_RE.search(cmd)
    sub = (match.group(1) if match else None) or "global"
    tags = {f"{sub}:{flag}" for flag in _FLAG_RE.findall(cmd.split("$L", 1)[-1])}
    if match and not match.group(1):
        tags.add("global:(no subcommand)")
    return tags


#: Prefix that gives a background job a default SIGINT. A non-interactive
#: shell starts ``&`` jobs with SIGINT ignored, and Python then never installs
#: its handler, so a plain ``kill -INT`` would test nothing.
RESET_SIGINT = (
    'python3 -c "import os, signal, sys;'
    " signal.signal(signal.SIGINT, signal.SIG_DFL);"
    ' os.execvp(sys.argv[1], sys.argv[1:])"'
)


def licenseid(args: str, db: str = "$DB") -> str:
    """A ``licenseid`` command line against the database copy."""
    return f"$L --db {db} {args}".strip()


def source(name: str, found: bool) -> tuple[str, str, str]:
    """``(pipeline prefix, arguments, tag)`` for one input source.

    *found* picks text that matches a licence or text that matches none.
    """
    text = FRAG if found else OTHER
    ident = "MIT" if found else "Nope-1.0"
    file_ = "$F/mit.txt" if found else "$F/other.txt"
    quoted = shlex.quote(text)
    sources: dict[str, tuple[str, str, str]] = {
        "arg_id": ("", ident, "arg-id"),
        "arg_file": ("", file_, "arg-file"),
        "text": (
            "",
            f'--text "$(cat {file_})"' if found else f"--text {quoted}",
            "--text",
        ),
        "id": ("", f"--id {ident}", "--id"),
        "stdin": (f"cat {file_} | ", "", "stdin"),
        "none": ("", "", "none"),
    }
    return sources[name]

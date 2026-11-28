# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The commands of the CLI, loaded at use.

``COMMANDS`` names each command, the module that defines it, and the first
paragraph of its help (the only part the group's ``--help`` shows, cut as
click cuts it). ``cli.cli.commands`` is a ``LazyCommands``: it lists the names
from this table and imports a command's module only when that command is
asked for. A run of ``--version``, ``--help`` or ``resolve`` then loads no
detector, no database code and no RapidFuzz (start-up).

A new command goes in this table (the group lists them sorted by name).
``tests/test_startup.py`` compares the table
with the commands the modules define, names and short helps.
"""

import importlib
from collections.abc import Iterator, MutableMapping
from typing import Final, NamedTuple

import click


class CommandEntry(NamedTuple):
    """Where a command is defined and what the group's help says of it."""

    module: str
    help: str  # the first paragraph of its help, white space collapsed


COMMANDS: Final[dict[str, CommandEntry]] = {
    "detect": CommandEntry(
        "clidetect",
        "Identify license text and return the closest matched SPDX License ID.",
    ),
    "resolve": CommandEntry(
        "cliresolve", "Resolve one declared licence value to an SPDX expression."
    ),
    "is-osi": CommandEntry(
        "clidetect",
        "True if the license is OSI-approved: every operand of an AND, any of "
        "an OR. Empty, exit 1, when no license is found or an operand cannot "
        "be judged.",
    ),
    "is-fsf": CommandEntry(
        "clidetect", "True if the license is FSF-libre, judged as is-osi judges."
    ),
    "is-spdx": CommandEntry(
        "clidetect",
        "True if every licence and exception ID is on the SPDX License List "
        "(a LicenseRef-* is not).",
    ),
    "update": CommandEntry(
        "cliupdate", "Update the license database from remote sources."
    ),
    "clear-cache": CommandEntry(
        "cliupdate", "Delete the database and the cache files beside it."
    ),
}


def short_help(name: str, limit: int) -> str:
    """The line the group's help shows for *name*, cut to *limit* characters
    as click cuts a command's help (``click.Command.get_short_help_str``)."""
    return click.Command(name, help=COMMANDS[name].help).get_short_help_str(limit)


class LazyCommands(MutableMapping[str, click.Command]):
    """The commands of a group: every name of ``COMMANDS`` is a key, and a
    command's module is imported at the first lookup of its name. The group
    reads them as it reads a dict: a name's presence, the sorted names, the
    names offered for "did you mean"."""

    def __init__(self) -> None:
        self._loaded: dict[str, click.Command] = {}

    def __getitem__(self, name: str) -> click.Command:
        if name not in self._loaded:
            if name not in COMMANDS:
                raise KeyError(name)
            module = importlib.import_module(f"licenseid.{COMMANDS[name].module}")
            self._loaded.update((c.name, c) for c in module.COMMANDS if c.name)
        return self._loaded[name]

    def __setitem__(self, name: str, command: click.Command) -> None:
        self._loaded[name] = command

    def __delitem__(self, name: str) -> None:
        del self._loaded[name]

    def __iter__(self) -> Iterator[str]:
        yield from COMMANDS
        yield from (name for name in self._loaded if name not in COMMANDS)

    def __len__(self) -> int:
        return len(COMMANDS) + sum(name not in COMMANDS for name in self._loaded)

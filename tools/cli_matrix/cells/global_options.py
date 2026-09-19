# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Family C: global options, help, and ``--clear-cache``.

``C1`` the group-level options, above all the many shapes ``--db`` can take,
``C2`` ``--help`` wherever it can appear, ``C3`` ``--clear-cache`` against a
cache directory the launcher has just filled.
"""

from __future__ import annotations

from tools.cli_matrix.model import CMDS, CellSet

#: (description, command, expected exit or None) for the global options.
GLOBAL: list[tuple[str, str, int | None]] = [
    ("no args", "$L", 2),
    ("--help", "$L --help", 0),
    ("-h", "$L -h", 2),
    ("--version (not an option)", "$L --version", 2),
    ("unknown subcommand", "$L frobnicate", 2),
    ("unknown global flag", "$L --nope", 2),
    ("subcommand prefix 'mat'", "$L mat MIT", 2),
    ("--db only", "$L --db $DB", 2),
    ("--db no value", "$L --db", 2),
    ("--db= empty", "$L --db= match MIT", None),
    (
        "--db twice (last wins?)",
        "$L --db /nonexistent/a.db --db $DB match --bold MIT",
        None,
    ),
    ("--db after subcommand", "$L match --db $DB MIT", 2),
    ("--db=path form", "$L --db=$DB match --bold MIT", 0),
    ("--db missing file", "$L --db /nonexistent/x.db match MIT", 2),
    ("--db directory", "$L --db $F/adir match MIT", None),
    ("--db text file", "$L --db $F/mit.txt match MIT", None),
    ("--db empty file", "$L --db $F/empty.txt match MIT", None),
    (
        "--db sqlite URI in-memory",
        "$L --db 'file:m?mode=memory&cache=shared' match MIT",
        None,
    ),
    ("--db :memory:", "$L --db :memory: match MIT", None),
    ("--db relative", "cd $F/.. && $L --db db/licenses.db match --bold MIT", 0),
    (
        "--db with space",
        (
            'mkdir -p "$W/a b" && cp $DB "$W/a b/l.db"'
            ' && $L --db "$W/a b/l.db" match --bold MIT'
        ),
        0,
    ),
    (
        "--db unicode",
        (
            'mkdir -p "$W/ü" && cp $DB "$W/ü/l.db"'
            ' && $L --db "$W/ü/l.db" match --bold MIT'
        ),
        0,
    ),
    (
        "--db symlink",
        "ln -s $DB $W/link.db && $L --db $W/link.db match --bold MIT",
        0,
    ),
    (
        "--db read-only file",
        ("cp $DB $W/ro.db && chmod 444 $W/ro.db && $L --db $W/ro.db match --bold MIT"),
        None,
    ),
    (
        "--db unreadable file",
        ("cp $DB $W/nr.db && chmod 000 $W/nr.db && $L --db $W/nr.db match --bold MIT"),
        None,
    ),
    (
        "--db in read-only dir",
        (
            "mkdir $W/rd && cp $DB $W/rd/l.db && chmod 555 $W/rd"
            " && $L --db $W/rd/l.db match --bold MIT; rc=$?; chmod 755 $W/rd; exit $rc"
        ),
        None,
    ),
]

#: Places ``--help`` can be written on a command line.
HELP_POSITIONS = (
    "$L {s} --help",
    "$L --help {s}",
    "$L {s} MIT --help",
    "$L {s} --help --json",
    "$L --db $DB {s} --help",
)

#: (description, command, expected exit or None) for ``--clear-cache``.
#: ``prep`` is replaced by a launcher run that fills a scratch cache.
CLEAR_CACHE: list[tuple[str, str, int | None]] = [
    (
        "--clear-cache alone (scratch DB)",
        "prep && $L --db $W/x/licenses.db --clear-cache && ls $W/x",
        0,
    ),
    (
        "--clear-cache twice",
        "prep && $L --db $W/x/licenses.db --clear-cache --clear-cache && ls $W/x",
        0,
    ),
    (
        "--clear-cache + match (ignored?)",
        (
            "prep && $L --db $W/x/licenses.db --clear-cache match MIT;"
            " echo \"db-left: $(ls $W/x | tr '\\n' ' ')\""
        ),
        None,
    ),
    (
        "--clear-cache + --help",
        (
            "prep && $L --db $W/x/licenses.db --clear-cache --help;"
            " echo \"left: $(ls $W/x | tr '\\n' ' ')\""
        ),
        None,
    ),
    (
        "--clear-cache on missing dir",
        "$L --db $W/nodir/licenses.db --clear-cache",
        None,
    ),
    (
        "--clear-cache with foreign files kept",
        (
            "prep && touch $W/x/keep.txt"
            " && $L --db $W/x/licenses.db --clear-cache && ls $W/x"
        ),
        0,
    ),
    (
        "--clear-cache with tmp orphans",
        (
            "prep && touch $W/x/licenses.json.1.tmp $W/x/spdx-data-v1.tar.gz.9.tmp"
            " && $L --db $W/x/licenses.db --clear-cache && ls $W/x"
        ),
        0,
    ),
    (
        "--clear-cache stdout closed",
        "prep && $L --db $W/x/licenses.db --clear-cache >&-",
        None,
    ),
    (
        "--clear-cache read-only dir",
        (
            "prep && chmod 555 $W/x && $L --db $W/x/licenses.db --clear-cache;"
            " rc=$?; chmod 755 $W/x; exit $rc"
        ),
        None,
    ),
    (
        "--clear-cache no --db (default path in scratch HOME)",
        (
            "mkdir -p $HOME/.local/share/licenseid && $L --clear-cache;"
            " ls $HOME/.local/share/licenseid"
        ),
        0,
    ),
]

_PREP = "mkdir -p $W/x && $LU --db $W/x/licenses.db update >/dev/null 2>&1"


def add_cells(cells: CellSet) -> None:
    """Add families C1 to C3 to *cells*."""
    for desc, cmd, exit_code in GLOBAL:
        cells.add(
            "C1",
            f"global: {desc}",
            cmd,
            kind="help" if "--help" in cmd else "other",
            exp_exit=exit_code,
        )
    for sub in CMDS:
        for position in HELP_POSITIONS:
            # click parses every option before honouring --help, so
            # `--help --json` is a usage error on commands without --json
            # (exit 2): that combination is left unspecified.
            strict = "--json" not in position or sub == "match"
            cells.add(
                "C2",
                f"help: {position.format(s=sub)}",
                position.format(s=sub),
                kind="help",
                exp_exit=0 if strict else None,
            )
    for desc, cmd, exit_code in CLEAR_CACHE:
        cells.add(
            "C3",
            f"clear-cache: {desc}",
            cmd.replace("prep", _PREP),
            exp_exit=exit_code,
            progress=True,
        )

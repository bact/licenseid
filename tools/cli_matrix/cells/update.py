# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Family D: the ``update`` subcommand, through the offline launcher.

``D1`` every failure mode against every starting cache state, ``D2`` the
option space, ``D3`` an all-pairs sweep over both, ``D4`` the real requests
stack against a dead proxy, ``D5`` signals mid-download, ``D6`` two updates
racing, ``D7`` what the database is like afterwards.

Every cell here runs ``$LU``, the offline launcher, except family D4, which
deliberately uses the real stack to prove that a blocked network fails the
documented way.
"""

from __future__ import annotations

import itertools

from tools.cli_matrix.model import RESET_SIGINT, CellSet, licenseid
from tools.cli_matrix.pairwise import pairwise

#: ``FAKE_NET`` modes the launcher understands; see ``launcher``.
NETS = [
    "ok",
    "down",
    "http503",
    "garbage_json",
    "bad_version",
    "pop_down",
    "pop_garbage",
    "tar_down",
    "tar_corrupt",
    "tar_truncated",
]

#: Shell fragments that put the cache into a given state before the update.
STATES = {
    "fresh": "",
    "same_version": "$LU --db $W/x/licenses.db update >/dev/null 2>&1; ",
    "older_version": (
        "FAKE_VER=9.98 $LU --db $W/x/licenses.db update >/dev/null 2>&1; "
    ),
    "stale_cache": (
        "$LU --db $W/x/licenses.db update >/dev/null 2>&1;"
        " touch -t 202001010000 $W/x/licenses.json $W/x/popularity.csv; "
    ),
    "corrupt_cache": (
        "$LU --db $W/x/licenses.db update >/dev/null 2>&1;"
        " printf 'garbage' > $W/x/licenses.json;"
        " printf 'garbage' > $W/x/popularity.csv; "
    ),
    "cache_only": (
        "$LU --db $W/x/licenses.db update >/dev/null 2>&1; rm $W/x/licenses.db; "
    ),
}

VERSIONS = ["", "9.99", "9.98", "''", "../x", "abc", "3.28.0", "9.99 ", "1"]
FORCES = ["", "--force"]
CACHES = ["", "--cache", "--no-cache"]

_DEAD_PROXY = "HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9"


def add_cells(cells: CellSet) -> None:
    """Add families D1 to D7 to *cells*."""
    for net in NETS:
        for state in STATES:
            _add_update(cells, "D1", net, state, "", "", "")
    for version, force, cache in itertools.product(VERSIONS, FORCES, CACHES):
        _add_update(cells, "D2", "ok", "fresh", version, force, cache)
    factors = {
        "net": NETS,
        "state": list(STATES),
        "ver": VERSIONS,
        "force": FORCES,
        "cache": CACHES,
    }
    for row in pairwise(factors, seed=11):
        _add_update(
            cells,
            "D3",
            row["net"],
            row["state"],
            row["ver"],
            row["force"],
            row["cache"],
        )
    _add_real_stack(cells)
    _add_signals(cells)
    _add_race(cells)
    _add_afterwards(cells)


def _add_update(
    cells: CellSet,
    fam: str,
    net: str,
    state: str,
    version: str,
    force: str,
    cache: str,
) -> None:
    """One ``update`` cell: put the cache in *state*, then update under *net*.

    The trailing marker lists what the cache directory holds afterwards, so
    the judge can see leftover temporary files.
    """
    args = " ".join(
        x for x in (f"--version {version}" if version else "", force, cache) if x
    )
    cmd = (
        f"mkdir -p $W/x && {STATES[state]}FAKE_NET={net}"
        f" $LU --db $W/x/licenses.db update {args};"
        " rc=$?; echo \"[files: $(ls $W/x 2>/dev/null | tr '\\n' ' ')]\" >&2;"
        " exit $rc"
    )
    cells.add(
        fam,
        f"update net={net} state={state} version={version or '-'}"
        f" {force or '-'} {cache or '-'}",
        cmd,
        kind="update",
        progress=True,
    )


def _add_real_stack(cells: CellSet) -> None:
    """D4: the real requests stack, with every proxy pointing nowhere."""
    variants = (
        ("update via the REAL requests stack against a dead proxy (no fake)", ""),
        ("update via the REAL requests stack, --no-cache, dead proxy", " --no-cache"),
    )
    for desc, extra in variants:
        cells.add(
            "D4",
            desc,
            f"mkdir -p $W/x && {_DEAD_PROXY} $L --db $W/x/licenses.db update{extra}",
            kind="update",
            progress=True,
            exp_exit=1,
        )


def _add_signals(cells: CellSet) -> None:
    """D5: a signal during a download that never finishes."""
    for sig in ("INT", "TERM"):
        cells.add(
            "D5",
            f"update interrupted by SIG{sig} during a slow download",
            f"mkdir -p $W/x && (FAKE_NET=slow {RESET_SIGINT} $LU"
            " --db $W/x/licenses.db update &"
            f' p=$!; sleep 2; kill -{sig} $p; wait $p; echo "rc=$?";'
            " echo \"[files: $(ls $W/x | tr '\\n' ' ')]\")",
            kind="update",
            progress=True,
            xenv=False,
        )


def _add_race(cells: CellSet) -> None:
    """D6: two updates writing the same cache directory at once."""
    cells.add(
        "D6",
        "two updates racing in one directory",
        "mkdir -p $W/x && ($LU --db $W/x/licenses.db update >/dev/null 2>$W/e1 &"
        " $LU --db $W/x/licenses.db update >/dev/null 2>$W/e2 & wait);"
        " cat $W/e1 $W/e2 | grep -E '^(ERROR|WARNING)' ;"
        ' $L --db $W/x/licenses.db is-osi MIT; echo "rc=$?"; ls $W/x',
        kind="other",
        # The cell prints the two captured stderr streams on stdout, so the
        # streams cannot be told apart here: observation only, never a FLAG.
        merged=True,
        progress=True,
        xenv=False,
    )


def _add_afterwards(cells: CellSet) -> None:
    """D7: the database an update leaves behind is usable."""
    cells.add(
        "D7",
        "update then match uses the new database",
        "mkdir -p $W/x && $LU --db $W/x/licenses.db update >/dev/null 2>&1"
        " && $L --db $W/x/licenses.db match --bold MIT",
        kind="match",
        exp_exit=0,
        exp_out=r"MIT\n",
    )
    cells.add(
        "D7",
        "update --force rebuilds, match still works",
        "mkdir -p $W/x && $LU --db $W/x/licenses.db update >/dev/null 2>&1"
        " && $LU --db $W/x/licenses.db update --force >/dev/null 2>&1"
        " && $L --db $W/x/licenses.db is-osi Apache-2.0",
        kind="predicate",
        exp_exit=0,
    )
    cells.add(
        "D7",
        "update on top of a real (46 MB) database copy: same-version skip",
        "cp $DB $W/real.db && FAKE_NET=down $LU --db $W/real.db update;"
        f" echo rc=$?; {licenseid('is-osi MIT', db='$W/real.db')}",
        kind="other",
        progress=True,
    )

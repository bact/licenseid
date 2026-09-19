# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Families E7 to E11: the process's own resources.

``E7`` ``HOME`` and the default database path, ``E8`` input size and
content, ``E9`` concurrency, ``E10`` signals, ``E11`` the process
environment it inherits.

Families E1 to E6, which vary the streams around the process, live in
``environment``.
"""

from __future__ import annotations

from tools.cli_matrix.model import RESET_SIGINT, CellSet, licenseid

#: to the password database, which resolves to the real user cache. A cell
#: that did that once deleted the developer's own licenses.db.
HOME_KINDS: list[tuple[str, str, str | None]] = [
    ("HOME absent dir (default db path)", "HOME=$W/nohome", None),
    (
        "HOME unset",
        "env -u HOME",
        (
            "HOME unset resolves the default database path to the real user"
            " cache (~/.local/share/licenseid), which this tool must never open"
        ),
    ),
    ("HOME=/nonexistent", "HOME=/nonexistent", None),
    (
        "HOME read-only",
        "mkdir -p $W/rohome && chmod 555 $W/rohome && HOME=$W/rohome",
        None,
    ),
    ("HOME is a file", "touch $W/homefile && HOME=$W/homefile", None),
    ("HOME with spaces", 'mkdir -p "$W/h h" && HOME="$W/h h"', None),
    ("HOME empty string", "HOME=", None),
    ("XDG_DATA_HOME set (ignored?)", "XDG_DATA_HOME=$W/xdg HOME=$W/xhome", None),
]


def add_cells(cells: CellSet) -> None:
    """Add families E7 to E11 to *cells*."""
    _add_home(cells)
    _add_input_size(cells)
    _add_concurrency(cells)
    _add_signals(cells)
    _add_process_env(cells)


def _add_home(cells: CellSet) -> None:
    """E7: the default database path, under every shape of HOME."""
    for name, pre, unsafe in HOME_KINDS:
        for sub in ("match MIT", "is-osi MIT", "--clear-cache", "update"):
            cells.add(
                "E7",
                f"default db path, {name}: {sub}",
                f"{pre} $L {sub}",
                kind="update" if sub == "update" else "other",
                progress=True,
                xenv=False,
                skip=unsafe,
            )


def _add_input_size(cells: CellSet) -> None:
    """E8: inputs that are very large, very odd, or not files at all."""
    big = "python3 -c \"import sys; sys.stdout.write('x'*300000)\""
    cells.add(
        "E8",
        "300 KB --text argument",
        licenseid('match --bold --text "$(' + big + ')"'),
        kind="match",
    )
    cells.add(
        "E8",
        "2 MB --text argument (over ARG_MAX)",
        'python3 -c "import os,subprocess,sys;'
        " sys.exit(subprocess.run([os.environ['L'],'--db',os.environ['DB'],"
        "'match','--text','x'*2000000]).returncode)\" 2>&1 | tail -c 200; true",
        kind="other",
        xenv=False,
    )
    sized: list[tuple[str, str, str, int | None]] = [
        (
            "3 MB file",
            "head -c 3000000 /dev/zero | tr '\\0' 'a' > $W/big.txt; ",
            licenseid("match $W/big.txt"),
            None,
        ),
        (
            "3 MB file of license text repeated",
            "for i in $(seq 1 30); do cat $F/mit.txt; done > $W/rep.txt; ",
            licenseid("match --bold $W/rep.txt"),
            None,
        ),
        (
            "one 1 MB line",
            "python3 -c \"print('word '*200000)\" > $W/line.txt; ",
            licenseid("match $W/line.txt"),
            None,
        ),
        (
            "many short lines",
            "python3 -c \"print('\\n'.join(['a']*300000))\" > $W/lines.txt; ",
            licenseid("match $W/lines.txt"),
            None,
        ),
        (
            "text of NUL-free control chars",
            "printf '\\001\\002\\003\\033[31mMIT\\033[0m' > $W/ctl.txt; ",
            licenseid("match $W/ctl.txt"),
            None,
        ),
        (
            "text of only newlines/tabs (blank)",
            "printf '\\n\\n\\t\\t\\r\\n' > $W/nl.txt; ",
            licenseid("match $W/nl.txt"),
            2,
        ),
        (
            "text: emoji / astral / RTL",
            (
                "printf 'Permission \\xf0\\x9f\\x98\\x80"
                " \\xd7\\xa9\\xd7\\x9c\\xd7\\x95\\xd7\\x9d granted' > $W/emoji.txt; "
            ),
            licenseid("match $W/emoji.txt"),
            None,
        ),
        (
            "text: invalid UTF-8 with high bytes only",
            "printf '\\xff\\xfe\\xfd' > $W/hi.txt; ",
            licenseid("match $W/hi.txt"),
            None,
        ),
        (
            "file is a FIFO with writer",
            "mkfifo $W/ff; (printf 'MIT' > $W/ff &) ; ",
            licenseid("match $W/ff"),
            None,
        ),
        (
            "file is /etc/passwd (unrelated text)",
            "",
            licenseid("match /etc/passwd"),
            None,
        ),
        (
            "file path is a directory symlink loop",
            "ln -s $W/loop $W/loop; ",
            licenseid("match $W/loop"),
            None,
        ),
    ]
    for desc, prep, cmd, exit_code in sized:
        cells.add(
            "E8",
            desc,
            f"{prep}{cmd}",
            kind="match",
            exp_exit=exit_code,
            xenv=desc == "text of only newlines/tabs (blank)",
        )


def _add_concurrency(cells: CellSet) -> None:
    """E9: several processes on one database file at once."""
    match_bold = licenseid("match --bold $F/mit.txt")
    cells.add(
        "E9",
        "4 concurrent matches on one DB",
        f"for i in 1 2 3 4; do {match_bold} & done; wait",
        kind="other",
        xenv=False,
    )
    cells.add(
        "E9",
        "8 concurrent is-osi on one DB",
        f"for i in 1 2 3 4 5 6 7 8; do {licenseid('is-osi MIT')} & done; wait",
        kind="other",
        xenv=False,
    )
    cells.add(
        "E9",
        "match while db replaced by cp",
        f"cp $DB $W/c.db; {licenseid('match --bold $F/mit.txt', db='$W/c.db')} &"
        " p=$!; cp $DB $W/c.db; wait $p",
        kind="other",
        xenv=False,
    )


def _add_signals(cells: CellSet) -> None:
    """E10: a signal during a match that takes a while."""
    slow = "python3 -c \"print('a'*400000)\" > $W/slow.txt; "
    run = f"{RESET_SIGINT} {licenseid('match $W/slow.txt')}"
    for sig in ("INT", "TERM"):
        # The tail prints the captured stderr on stdout, so the two streams
        # cannot be told apart here: observation only, never a FLAG.
        cells.add(
            "E10",
            f"SIG{sig} during a slow match (400 KB input)",
            f"{slow}({run} > $W/o 2> $W/e & p=$!; sleep 1.5; kill -{sig} $p;"
            ' wait $p; echo "rc=$?"; cat $W/e | head -5)',
            kind="other",
            merged=True,
            xenv=False,
        )
    cells.add(
        "E10",
        "SIGHUP during a slow match (400 KB input)",
        f"{slow}({run} > $W/o 2> $W/e & p=$!; sleep 1.5; kill -HUP $p;"
        ' wait $p; echo "rc=$?")',
        kind="other",
        xenv=False,
    )
    cells.add(
        "E10",
        "nohup / background with closed stdio",
        f"nohup {licenseid('match --bold $F/mit.txt')}"
        " < /dev/null > $W/o 2>&1; cat $W/o",
        kind="other",
        xenv=False,
    )


def _add_process_env(cells: CellSet) -> None:
    """E11: interpreter and resource settings inherited from the parent."""
    match_bold = licenseid("match --bold $F/mit.txt")
    for desc, prefix in (
        ("env: PYTHONWARNINGS=error", "PYTHONWARNINGS=error "),
        ("env: PYTHONDEVMODE=1", "PYTHONDEVMODE=1 "),
        ("env: PYTHONOPTIMIZE=2", "PYTHONOPTIMIZE=2 "),
    ):
        cells.add("E11", desc, prefix + match_bold, kind="match", exp_exit=0)
    # cksum, not md5: md5 is BSD-only and md5sum is GNU-only.
    cells.add(
        "E11",
        "env: PYTHONHASHSEED variations agree",
        "for s in 0 1 2 3; do PYTHONHASHSEED=$s"
        f" {licenseid('match --json $F/mit.txt')} | cksum; done | sort -u | wc -l",
        kind="other",
        exp_out=r"\s*1\n",
        xenv=False,
    )
    for desc, prefix in (
        ("env: PYTHONPATH junk", "PYTHONPATH=/nonexistent:$W "),
        (
            "env: http proxy vars set (match makes no request)",
            "HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 ",
        ),
    ):
        cells.add("E11", desc, prefix + match_bold, kind="match", exp_exit=0)
    cells.add(
        "E11",
        "env: TMPDIR unwritable",
        f"mkdir -p $W/t && chmod 555 $W/t && TMPDIR=$W/t {match_bold}; chmod 755 $W/t",
        kind="match",
        exp_exit=0,
    )
    cells.add(
        "E11",
        "env: empty PATH after start (binary by abs path)",
        "env -i $L --db $DB match --bold $F/mit.txt",
        kind="match",
        exp_exit=0,
    )
    cells.add(
        "E11",
        "env: umask 777",
        f"umask 777; {match_bold}",
        kind="match",
        exp_exit=0,
    )
    cells.add(
        "E11",
        "env: ulimit -n 8 (few fds)",
        f"ulimit -n 8; {match_bold}",
        kind="match",
    )
    # ulimit -v is a Linux extension; on macOS the shell rejects it and the
    # command simply runs unlimited. Kind "other" keeps the cell an
    # observation on both, so a Linux run cannot FLAG on a starved process.
    cells.add(
        "E11",
        "env: ulimit -v small (memory)",
        f"ulimit -v 200000 2>/dev/null; {match_bold}",
        kind="other",
    )

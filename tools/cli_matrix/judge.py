# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Turning one run of one cell into a verdict.

The invariants come from ``AGENTS.md`` ("CLI output"): stdout carries only
the result, every diagnostic goes to stderr in one grammar, a predicate
answers ``true``/``false``/usage error, ``match`` prints one of three
documented shapes, and nothing ever shows a traceback.

Anything the documentation does not settle is ``OBSERVE``, never ``PASS``:
a verdict is a claim about the contract, and there is no contract to claim.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tools.cli_matrix.model import Cell

#: LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION] -- the diagnostic grammar.
GRAMMAR = re.compile(r"(ERROR|WARNING): [a-z][a-z0-9._-]*: [a-z0-9].*")

#: What click itself is allowed to print. The empty alternative at the end
#: lets blank lines through.
CLICK = re.compile(r"(Usage: .*|Try '.*' for help\.|Error: .*|Aborted!|)")

#: The default one-line result of ``match``.
PLAIN = re.compile(
    r"LICENSE_ID=\S+( WITH \S+)? SIMILARITY=-?\d+\.\d{4} COVERAGE=-?\d+\.\d{4}"
)

#: The whole result of ``match --bold``: an identifier and nothing else.
BOLD = re.compile(r"\S+( WITH \S+)?")

CRASH = re.compile(
    r"Traceback \(most recent call last\)|Exception ignored"
    r"|Segmentation fault|Bus error|core dumped"
)

_SHELL_MESSAGE = re.compile(r"(sh|bash|zsh|dash|ksh)[:0-9 ]")

#: A command whose stdout ends in a pipeline or an echo is reporting on
#: itself, so neither the exit status nor the stream contract is the CLI's.
_PIPE_TAIL = re.compile(r"\| *(head|true|tail|\(|cut|sort|cksum|md5|wc)")

#: Families where a signal or a race decides the exit status.
_SIGNAL_FAMILIES = ("E10", "D5", "D6")

#: Anything slower than this is worth a human's attention on its own.
SLOW_SECONDS = 20

Result = dict[str, Any]

PASS = "PASS"
OBSERVE = "OBSERVE"
FLAG = "FLAG"


def judge(cell: Cell, result: Result) -> tuple[str, list[str]]:
    """The verdict for one run, and the notes that explain it."""
    if result["rc"] == -999:
        return FLAG, ["TIMEOUT (hang)"]
    flags: list[str] = []
    flags += _crash_flags(result)
    flags += _stream_flags(cell, result)
    flags += _exit_range_flags(cell, result)
    flags += _contract_flags(cell, result)
    flags += _update_flags(cell, result)
    flags += _expectation_flags(cell, result)
    flags += _leftover_flags(cell, result)
    if flags:
        return FLAG, flags
    if _is_unspecified(cell):
        return OBSERVE, []
    return PASS, []


def _is_unspecified(cell: Cell) -> bool:
    """True when nothing documented pins this cell's behaviour down."""
    return (
        cell.exp_exit is None
        and cell.exp_out is None
        and cell.exp_err is None
        and cell.kind in ("other", "update", "match", "predicate", "help")
    )


def has_pipe_tail(cell: Cell) -> bool:
    """True when the cell post-processes or reports its own result."""
    return (
        bool(_PIPE_TAIL.search(cell.cmd))
        or cell.cmd.endswith("; true")
        or "echo" in cell.cmd
        or "wait" in cell.cmd
        or "; ls" in cell.cmd
        or "&& ls" in cell.cmd
        or "cat $W" in cell.cmd
    )


def _crash_flags(result: Result) -> list[str]:
    """A traceback or a fatal signal message, on either stream."""
    if CRASH.search(result["out"] + result["err"]):
        return ["traceback/crash"]
    return []


def _stream_flags(cell: Cell, result: Result) -> list[str]:
    """stdout carries only results; stderr only the diagnostic grammar."""
    if cell.tty or cell.merged:
        return []
    flags: list[str] = []
    if re.search(r"(?m)^(ERROR|WARNING):", result["out"]):
        flags.append("diagnostic on stdout")
    for line in result["err"].splitlines():
        if cell.progress:
            # Free-text progress is allowed, but a diagnostic is not exempt.
            if re.match(r"(ERROR|WARNING):", line) and not GRAMMAR.fullmatch(line):
                flags.append(f"bad grammar: {line[:70]}")
            continue
        if GRAMMAR.fullmatch(line) or CLICK.fullmatch(line):
            continue
        # The shell's own messages, and the markers cells print themselves.
        if _SHELL_MESSAGE.match(line) or line.startswith("["):
            continue
        flags.append(f"stderr line outside grammar: {line[:70]}")
    return flags


def _exit_range_flags(cell: Cell, result: Result) -> list[str]:
    """Only 0, 1 and 2 are documented exit statuses."""
    rc = result["rc"]
    if rc in (0, 1, 2) or cell.fam in _SIGNAL_FAMILIES:
        return []
    if cell.kind == "other" and ("ulimit" in cell.cmd or "kill" in cell.cmd):
        return []
    return [f"exit code {rc} outside 0/1/2"]


def _contract_flags(cell: Cell, result: Result) -> list[str]:
    """The per-subcommand output contract."""
    if cell.tty or cell.merged or has_pipe_tail(cell):
        return []
    rc, out, err = result["rc"], result["out"], result["err"]
    if cell.kind == "predicate":
        if (rc, out) not in ((0, "true\n"), (1, "false\n"), (2, "")):
            return [f"predicate contract: exit={rc} stdout={out[:30]!r}"]
        return []
    if cell.kind != "match":
        return []
    if rc == 0:
        return check_match_format(cell, out)
    if rc == 1:
        if out != "" or "ERROR: match: no license found" not in err:
            return ["match exit 1 without empty stdout + 'no license found'"]
        return []
    if rc == 2 and out != "" and "--help" not in cell.cmd:
        return ["exit 2 with stdout output"]
    return []


def check_match_format(cell: Cell, out: str) -> list[str]:
    """Whether ``match`` printed the shape its flags asked for."""
    flags = cell.outflags
    if not out:
        return ["exit 0 but empty stdout"] if "--help" not in cell.cmd else []
    lines = out.splitlines()
    ok_bold = (
        len(lines) == 1
        and BOLD.fullmatch(lines[0]) is not None
        and not lines[0].startswith("LICENSE_ID=")
    )
    ok_json = _is_result_json(out)
    ok_plain = bool(lines) and PLAIN.fullmatch(lines[0]) is not None
    if "bold" in flags and "json" in flags:
        return [] if (ok_bold or ok_json) else ["--bold --json output is neither"]
    if "bold" in flags:
        return [] if ok_bold else [f"--bold not a single id: {out[:40]!r}"]
    if "json" in flags:
        return [] if ok_json else [f"--json invalid: {out[:40]!r}"]
    if not ok_plain and not ok_bold and not ok_json:
        return [f"plain output malformed: {out[:60]!r}"]
    return []


def _is_result_json(out: str) -> bool:
    """True when *out* is a JSON list of result objects."""
    try:
        parsed = json.loads(out)
    except ValueError:
        return False
    return isinstance(parsed, list) and all(
        isinstance(item, dict) and {"license_id", "score"} <= set(item)
        for item in parsed
    )


def json_count(out: str) -> int | None:
    """How many results *out* holds, when it is a JSON list."""
    try:
        parsed = json.loads(out)
    except ValueError:
        return None
    return len(parsed) if isinstance(parsed, list) else None


def _update_flags(cell: Cell, result: Result) -> list[str]:
    """``update`` prints one result line on success and nothing on failure."""
    if cell.kind != "update":
        return []
    rc, out = result["rc"], result["out"]
    if (
        rc == 0
        and not cell.merged
        and "\nDatabase" not in "\n" + out
        and cell.fam not in ("D5", "D4")
        and out.strip()
        and not re.fullmatch(
            r"Database (updated at|remains at version \S+ at) .*\n", out
        )
    ):
        return [f"update stdout not a single result line: {out[:60]!r}"]
    if rc != 0 and out.strip() and cell.fam not in ("D5", "D6", "D7"):
        return [f"update failed but stdout not empty: {out[:60]!r}"]
    return []


def _expectation_flags(cell: Cell, result: Result) -> list[str]:
    """What this particular cell was documented to do."""
    flags: list[str] = []
    rc, out, err = result["rc"], result["out"], result["err"]
    if cell.exp_exit is not None and not cell.tty:
        expected = cell.exp_exit
        ok = rc in expected if isinstance(expected, frozenset) else rc == expected
        if not ok and not has_pipe_tail(cell):
            flags.append(f"expected exit {cell.exp_exit}, got {rc}")
    if cell.exp_out is not None and not re.fullmatch(cell.exp_out, out, re.DOTALL):
        flags.append(f"stdout {out[:40]!r} !~ {cell.exp_out!r}")
    if cell.exp_err is not None and not re.search(cell.exp_err, err):
        flags.append(f"stderr lacks {cell.exp_err!r}")
    if cell.top and rc == 0 and not cell.tty:
        count = json_count(out) if "json" in cell.outflags else len(PLAIN.findall(out))
        if count is not None and count > cell.top:
            flags.append(f"--top {cell.top} returned {count}")
    return flags


def _leftover_flags(cell: Cell, result: Result) -> list[str]:
    """An update must not leave its temporary files behind."""
    if not cell.fam.startswith("D") or cell.tty:
        return []
    if any(".tmp" in name for name in result["files"]):
        named = [name for name in result["files"] if "tmp" in name]
        return [f"leftover tmp files: {named}"]
    return []


def norm(text: str, work: str, out_dir: str) -> str:
    """Replace run-specific paths, so ledger text is the same anywhere."""
    return text.replace(work, "$W").replace(out_dir, "$O")


def differential(
    cells: dict[str, Cell], results: list[Result], out_dir: str
) -> dict[tuple[str, str, str], list[str]]:
    """Flags for cells that disagree across shells, interpreters or groups.

    A command whose answer depends on the shell it was typed in, or on which
    Python runs it, is a defect even when every single answer looks sane.
    """
    bad: dict[tuple[str, str, str], list[str]] = {}
    by_id: dict[str, list[Result]] = {}
    for result in results:
        by_id.setdefault(result["id"], []).append(result)
    _cross_environment(cells, by_id, out_dir, bad)
    _groups(cells, results, bad)
    return bad


def _cross_environment(
    cells: dict[str, Cell],
    by_id: dict[str, list[Result]],
    out_dir: str,
    bad: dict[tuple[str, str, str], list[str]],
) -> None:
    """Every run of one cell must agree with the first one."""
    for cell_id, runs in by_id.items():
        cell = cells[cell_id]
        if not cell.xenv or cell.tty:
            continue
        base = runs[0]
        for run in runs[1:]:
            first = _signature(base, out_dir)
            other = _signature(run, out_dir)
            if first == other:
                continue
            if cell.fam.startswith("D") and cell.kind == "update":
                continue
            note = (
                f"differs from {base['shell']}/{base['py']}:"
                f" exit {base['rc']}->{run['rc']}"
                + ("" if first[1] == other[1] else " stdout")
                + ("" if first[2] == other[2] else " stderr")
            )
            bad.setdefault((cell_id, run["shell"], run["py"]), []).append(note)


def _signature(result: Result, out_dir: str) -> tuple[int, str, str]:
    """A run reduced to what must not vary with the environment."""
    return (
        result["rc"],
        norm(result["out"], result["work"], out_dir),
        norm(result["err"], result["work"], out_dir),
    )


def _groups(
    cells: dict[str, Cell],
    results: list[Result],
    bad: dict[tuple[str, str, str], list[str]],
) -> None:
    """Cells in one group must agree with the majority of the group."""
    if not results:
        return
    first_py = results[0]["py"]
    groups: dict[str, list[Result]] = {}
    for result in results:
        name = cells[result["id"]].group
        if name and result["py"] == first_py:
            groups.setdefault(name, []).append(result)
    for name, runs in groups.items():
        signatures: dict[tuple[int, str], list[str]] = {}
        for run in runs:
            # Plain output may differ after its first line (ties, order);
            # JSON is one document, so it is compared whole.
            whole = "json" in cells[run["id"]].outflags or "A1" not in name
            head = run["out"] if whole else run["out"].split("\n", 1)[0]
            signatures.setdefault((run["rc"], head), []).append(run["id"])
        if len(signatures) <= 1:
            continue
        majority = max(signatures.values(), key=len)
        for key, ids in signatures.items():
            if ids is majority:
                continue
            for cell_id in ids:
                for run in runs:
                    if run["id"] != cell_id:
                        continue
                    bad.setdefault((cell_id, run["shell"], run["py"]), []).append(
                        f"group {name}: differs from {majority[0]}"
                        f" (exit,stdout): {key[0]} {str(key[1])[:40]!r}"
                    )


_B5_ID = re.compile(r"--id '(.*)' \(")


def relational(rows: list[Result], cells: dict[str, Cell]) -> None:
    """Check the predicates against each other, and annotate the rows.

    For one identifier, ``is-open`` must equal ``is-osi or is-fsf``, and
    ``is-free`` must equal ``is-open`` (README). A single predicate can look
    perfectly well behaved while contradicting its neighbours.
    """
    answers: dict[tuple[str, str, str], dict[str, Result]] = {}
    for row in rows:
        cell = cells[row["id"]]
        if cell.fam != "B5":
            continue
        match = _B5_ID.search(cell.desc)
        if not match:
            continue
        ident = match.group(1)
        subcommand = cell.cmd.split("$DB ", 1)[1].split()[0]
        answers.setdefault((ident, row["shell"], row["py"]), {})[subcommand] = row
    for (ident, _shell, _py), found in answers.items():
        if len(found) < 5:
            continue
        _apply_relational(ident, found)


def _apply_relational(ident: str, found: dict[str, Result]) -> None:
    """Record the cross-predicate answer, and flag any contradiction."""
    codes = {name: row["rc"] for name, row in found.items()}
    problems: list[str] = []
    if (codes["is-open"] == 0) != (codes["is-osi"] == 0 or codes["is-fsf"] == 0):
        problems.append(
            f"is-open={codes['is-open']} but is-osi={codes['is-osi']}"
            f" is-fsf={codes['is-fsf']}"
        )
    if codes["is-free"] != codes["is-open"]:
        problems.append(f"is-free={codes['is-free']} != is-open={codes['is-open']}")
    summary = f"answers for '{ident}': " + " ".join(
        f"{name}={code}" for name, code in sorted(codes.items())
    )
    for row in found.values():
        row["notes"] = row["notes"] + [f"relational: {p}" for p in problems] + [summary]
        if problems:
            row["verdict"] = FLAG

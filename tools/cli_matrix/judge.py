# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Turning one run of one cell into a verdict.

The invariants come from ``AGENTS.md`` ("CLI output"): stdout carries only
the result, every diagnostic goes to stderr in one grammar, a predicate
answers one record whose flag is true/false (or a usage error), ``detect``
prints one of three documented shapes, ``update`` one record, and nothing
ever shows a traceback.

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

#: The help printed for a missing subcommand: stderr, exit 2, not a result.
HELP = re.compile(r"Usage: .*\n(.*\n)*Commands:\n")

#: The default one-line result of ``detect``: fields joined by one tab.
#: An expression's operators are its only spaces; a score is 0-1, and
#: coverage passes 1 when the input is longer than the licence.
PLAIN = re.compile(
    r"EXPRESSION=\S+( (AND|OR|WITH) \S+)*\tMETHOD=[a-z]+\tEXACT=(true|false)"
    r"\tSCORE=(0\.\d{4}|1\.0000)\tSIMILARITY=(\d\.\d{4})?"
    r"\tCOVERAGE=(\d+\.\d{4})?"
)

#: The lines of ``licenseid match``: fields joined by one tab, no value
#: holds one (``result.text_field``).
MATCH_HEAD = re.compile(r"EXPRESSION=([^\t]*)\tCATEGORY=[a-z_]+\tTRUST=[a-z_]+")
MATCH_LINE = re.compile(
    r"STEP=[a-z_]+\tFROM=[^\t]*\tTO=[^\t]*|REASON=[^\t]+"
    r"|OPERAND=[^\t]+\tEXPRESSION=[^\t]*\tCATEGORY=[a-z_]+"
)

#: The word diff ``detect --diff`` writes to stderr: a header, the unified
#: diff's lines (one word each, or a ``---``/``+++``/``@@`` line), and a blank
#: line to end it.
WORD_DIFF = re.compile(
    r"(?m)^\nWORD DIFF:\n(?:(?:[-+ ]\S*|@@ .*|--- \S+|\+\+\+ \S+)\n)*\n"
)

#: The one record of an ``is-*`` command, and of ``update``.
#: The flag is empty when an operand of the expression cannot be judged.
PREDICATE_LINE = re.compile(r"EXPRESSION=[^\t]*\t(IS_[A-Z_]+)=(true|false|)\n")
UPDATE_LINE = re.compile(
    r"LIST=[a-z-]+\tVERSION=[^\t]*\tSTATUS=(updated|unchanged)\tPATH=[^\t\n]+\n"
)

#: The whole result of ``detect --id-only``: an expression and nothing else.
ID_ONLY = re.compile(r"\S+( (WITH|AND|OR) \S+)*")
#: What ``detect`` prints for no answer (exit 1): one record, every field
#: empty; with ``--json`` every value null; with ``--id-only`` an empty line.
NO_ANSWER = re.compile(r"EXPRESSION=\tMETHOD=\tEXACT=\tSCORE=\tSIMILARITY=\tCOVERAGE=\n")

#: What :func:`predicate_answer` gives for an output that is not one record.
MALFORMED = "malformed"

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
        and cell.kind in ("other", "update", "detect", "predicate", "match", "help")
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
    if result["rc"] == 2 and not result["out"] and HELP.match(result["err"]):
        return flags  # the help for a missing subcommand
    err = result["err"]
    if "--diff" in cell.cmd:  # detect's word diff goes to stderr (P116)
        err = WORD_DIFF.sub("", err)
    for line in err.splitlines():
        if cell.progress:
            # Free-text progress is allowed, but a diagnostic is not exempt.
            if re.match(r"(ERROR|WARNING):", line) and not GRAMMAR.fullmatch(line):
                flags.append(f"bad grammar: {line[:70]}")
            continue
        # click's own usage error (``Usage:``, ``Try '…'``, ``Error:``) and
        # ``Aborted!`` are no longer allowed: licenseid words them in the
        # grammar (roadmap item 12) and exits 130 quietly on Ctrl-C.
        if GRAMMAR.fullmatch(line) or not line:
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
        answer = predicate_answer(out)
        if (rc, out) == (2, "") or (rc, answer) in ((0, True), (1, False), (1, None)):
            return []
        return [f"predicate contract: exit={rc} stdout={out[:40]!r}"]
    if cell.kind == "match":
        return check_match_value(cell, rc, out)
    if cell.kind != "detect":
        return []
    if rc == 0:
        return check_match_format(cell, out)
    if rc == 1:  # "no": the empty record, no ERROR line (a WARNING may be)
        if not is_no_answer(cell, out) or re.search(r"(?m)^ERROR:", err):
            return ["detect exit 1 without its empty record, or an ERROR line"]
        return []
    if rc == 2 and out != "" and "--help" not in cell.cmd:
        return ["exit 2 with stdout output"]
    return []


def check_match_value(cell: Cell, rc: int, out: str) -> list[str]:
    """``licenseid match``: exit 0 with an expression, 1 without one, 2 with
    nothing on stdout; ``--json`` one resolution object."""
    if rc == 2:
        return [] if out == "" or "--help" in cell.cmd else ["exit 2 with stdout"]
    if rc not in (0, 1) or "--help" in cell.cmd:
        return []
    if "json" in cell.outflags or "--json" in cell.cmd:
        parsed = _json_results(out)
        if not (parsed and len(parsed) == 1 and isinstance(parsed[0], dict)):
            return [f"match --json not one object: {out[:40]!r}"]
        if "schema" not in parsed[0]:  # a detection, not a resolution
            return [f"match --json not one object: {out[:40]!r}"]
        resolved = parsed[0].get("expression") is not None
    else:
        lines = out.splitlines()
        head = MATCH_HEAD.fullmatch(lines[0]) if lines else None
        if head is None or not all(MATCH_LINE.fullmatch(x) for x in lines[1:]):
            return [f"match output malformed: {out[:60]!r}"]
        resolved = head.group(1) != ""
    if resolved != (rc == 0):
        return [f"match exit {rc} but expression {'set' if resolved else 'empty'}"]
    return []


def check_match_format(cell: Cell, out: str) -> list[str]:
    """Whether ``detect`` printed the shape its flags asked for."""
    flags = cell.outflags
    if not out:
        return ["exit 0 but empty stdout"] if "--help" not in cell.cmd else []
    lines = out.splitlines()
    ok_id_only = (
        len(lines) == 1
        and ID_ONLY.fullmatch(lines[0]) is not None
        and not lines[0].startswith("EXPRESSION=")
    )
    ok_json = _is_result_json(out)
    ok_plain = bool(lines) and PLAIN.fullmatch(lines[0]) is not None
    if "id-only" in flags and "json" in flags:
        return ["--id-only --json answered: a usage error (exit 2)"]
    if "id-only" in flags:
        return [] if ok_id_only else [f"--id-only not one expression: {out[:40]!r}"]
    if "json" in flags:
        return [] if ok_json else [f"--json invalid: {out[:40]!r}"]
    if not ok_plain and not ok_id_only and not ok_json:
        return [f"plain output malformed: {out[:60]!r}"]
    return []


def is_no_answer(cell: Cell, out: str) -> bool:
    """Whether *out* is what ``detect`` prints for no answer, by the output
    flag the cell asked for (or, without one, any of the three shapes)."""
    flags = cell.outflags
    as_json = _json_results(out)
    json_ok = bool(
        as_json
        and len(as_json) == 1
        and isinstance(as_json[0], dict)
        and as_json[0]
        and set(as_json[0].values()) == {None}
    )
    if "id-only" in flags:
        return out == "\n"
    if "json" in flags:
        return json_ok
    return NO_ANSWER.fullmatch(out) is not None or json_ok or out == "\n"


def _json_results(out: str) -> list[object] | None:
    """The values *out* holds as JSON Lines (one per line), or None."""
    try:
        return [json.loads(line) for line in out.splitlines()]
    except ValueError:
        return None


def _is_result_json(out: str) -> bool:
    """True when *out* is JSON Lines of result objects, one or more."""
    parsed = _json_results(out)
    return bool(parsed) and all(
        isinstance(item, dict)
        and {"expression", "method", "score"} <= set(item)
        and "schema" not in item  # a resolution of match
        for item in parsed or ()
    )


def json_count(out: str) -> int | None:
    """How many results *out* holds, when it is JSON Lines."""
    parsed = _json_results(out)
    return None if parsed is None else len(parsed)


def predicate_answer(out: str) -> bool | str | None:
    """The flag of an ``is-*`` record, text or ``--json``: a bool, None when
    the record leaves it empty (an operand that cannot be judged), or
    ``"malformed"`` when *out* is not one record."""
    line = PREDICATE_LINE.fullmatch(out)
    if line:
        return {"true": True, "false": False}.get(line.group(2))
    parsed = _json_results(out)
    if not (parsed and len(parsed) == 1 and isinstance(parsed[0], dict)):
        return MALFORMED
    record: dict[str, Any] = parsed[0]
    flags = [key for key in record if key.startswith("is_")]
    if set(record) != {"expression", *flags} or len(flags) != 1:
        return MALFORMED
    flag = record[flags[0]]
    return flag if flag is None or isinstance(flag, bool) else MALFORMED


def is_update_record(out: str) -> bool:
    """Whether *out* is the one record of ``update``, text or ``--json``."""
    if UPDATE_LINE.fullmatch(out):
        return True
    parsed = _json_results(out)
    return bool(
        parsed
        and len(parsed) == 1
        and isinstance(parsed[0], dict)
        and set(parsed[0]) == {"list", "path", "status", "version"}
        and parsed[0]["status"] in ("updated", "unchanged")
    )


def _update_flags(cell: Cell, result: Result) -> list[str]:
    """``update`` prints one result line on success and nothing on failure."""
    if cell.kind != "update":
        return []
    rc, out = result["rc"], result["out"]
    if (
        rc == 0
        and not cell.merged
        and cell.fam not in ("D5", "D4")
        and out.strip()
        and not is_update_record(out)
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
            # JSON Lines are compared whole, every line, not by the top one.
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


#: Each predicate, by the flag of ``detect --json`` it must agree with.
_PREDICATE_FLAGS = {
    "is-osi": "is_osi_approved",
    "is-fsf": "is_fsf_libre",
    "is-spdx": "is_spdx",
}


def relational(rows: list[Result], cells: dict[str, Cell]) -> None:
    """Check the predicates against ``detect``, and annotate the rows.

    For one identifier, each predicate exits 0 exactly when the flag of
    ``detect --json``'s top result is true (README: ``is-osi`` reads
    ``is_osi_approved``). A single predicate can look perfectly well behaved
    while contradicting ``detect``.
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
        if len(found) < len(_PREDICATE_FLAGS) + 1:
            continue
        _apply_relational(ident, found)


def _apply_relational(ident: str, found: dict[str, Result]) -> None:
    """Record the cross-command answer, and flag any contradiction."""
    codes = {name: row["rc"] for name, row in found.items()}
    detected = _json_results(found["detect"]["out"]) or [{}]
    top = detected[0] if isinstance(detected[0], dict) else {}
    problems = [
        f"{name}={codes[name]} but detect {flag}={top.get(flag)}"
        for name, flag in _PREDICATE_FLAGS.items()
        if (codes[name] == 0) != (top.get(flag) is True)
    ]
    summary = f"answers for '{ident}': " + " ".join(
        f"{name}={code}" for name, code in sorted(codes.items())
    )
    for row in found.values():
        row["notes"] = row["notes"] + [f"relational: {p}" for p in problems] + [summary]
        if problems:
            row["verdict"] = FLAG

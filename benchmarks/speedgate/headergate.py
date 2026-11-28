# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The verdict of the headers set and its gate.

A header is judged at the answer bar (``moved.ANSWER_BAR``): *right* when the
top answer is the header's own licence or one of its class
(``headerclasses``), *wrong* for another licence, *none* below the bar. The
classes come from each side's own database and are stored in its result."""

from collections import Counter
from typing import Any, Final

from benchmarks.speedgate.gates import FAIL, NA, PASS, Gate, Sets
from benchmarks.speedgate.moved import ANSWER_BAR, top
from benchmarks.speedgate.results import cases_of
from benchmarks.speedgate.sets_headers import FORMS

NAME: Final = "Headers"
OUTCOMES: Final = ("right", "wrong", "none")
LABELS: Final = {"given": "as given", "cut": "cut"}


def verdict(key: str, case: dict[str, Any], classes: dict[str, str]) -> tuple[str, str]:
    """``(right | wrong | none, top answer)`` of the case ``hdr:<form>:<ID>``."""
    answer, _ = top(case, ANSWER_BAR)
    if answer is None:
        return "none", ""
    own = key.split(":")[2]
    same = classes.get(answer, answer) == classes.get(own, own)
    return ("right" if same else "wrong"), answer


def verdicts(result: dict[str, Any] | None) -> dict[str, tuple[str, str]]:
    """The verdict of every header case of a headers result, by key."""
    classes = (result or {}).get("classes") or {}
    return {k: verdict(k, c, classes) for k, c in cases_of(result).items()}


def counts(found: dict[str, tuple[str, str]]) -> dict[str, Counter[str]]:
    """Right, wrong and none of each form."""
    out = {form: Counter[str]() for form in FORMS}
    for key, (outcome, _) in found.items():
        out[key.split(":")[1]][outcome] += 1
    return out


def _triple(c: Counter[str]) -> str:
    return " / ".join(str(c[o]) for o in OUTCOMES)


def _worse(base: Counter[str], cand: Counter[str]) -> bool:
    return cand["right"] < base["right"] or cand["wrong"] > base["wrong"]


def gate(base: Sets, cand: Sets) -> Gate:
    """Headers: no fewer right and no more wrong than the base, in each form."""
    if not cases_of(cand.get("headers")):
        return Gate(NAME, NA, "no headers results")
    after = counts(verdicts(cand.get("headers")))
    if not cases_of(base.get("headers")):
        shown = ", ".join(f"{LABELS[f]} {_triple(after[f])}" for f in FORMS)
        return Gate(NAME, NA, f"base has no headers set; candidate {shown}")
    before = counts(verdicts(base.get("headers")))
    shown = ", ".join(
        f"{LABELS[f]} {_triple(before[f])} to {_triple(after[f])}" for f in FORMS
    )
    bad = [f for f in FORMS if _worse(before[f], after[f])]
    detail = f"right / wrong / none, base to candidate: {shown}"
    return Gate(NAME, FAIL if bad else PASS, detail)


def with_gate(gates: list[Gate], base: Sets, cand: Sets) -> list[Gate]:
    """*gates* with the headers gate before the first gate that is not
    measured here."""
    first = next((i for i, g in enumerate(gates) if g.status == NA), len(gates))
    return [*gates[:first], gate(base, cand), *gates[first:]]


def moved_lines(base: Sets, cand: Sets) -> list[str]:
    """Each header whose verdict moved, with its answer before and after."""
    a, b = verdicts(base.get("headers")), verdicts(cand.get("headers"))
    lines = []
    for key in sorted(a.keys() & b.keys()):
        if a[key][0] != b[key][0]:
            _, form, licence = key.split(":")
            lines.append(
                f"  {licence} ({LABELS[form]}): {a[key][0]} [{a[key][1] or '-'}] "
                f"-> {b[key][0]} [{b[key][1] or '-'}]"
            )
    return lines


def section(base: Sets, cand: Sets) -> list[str]:
    """The report lines of the headers whose verdict moved (none when a side
    lacks the set)."""
    if not (cases_of(base.get("headers")) and cases_of(cand.get("headers"))):
        return ["headers: not in both runs"]
    moved = moved_lines(base, cand)
    return [f"headers: {len(moved)} verdicts moved", *moved]

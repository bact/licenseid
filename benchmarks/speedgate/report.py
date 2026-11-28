# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The text of a comparison: answers that moved first, then times, labels,
gates."""

import json
from pathlib import Path
from typing import Any, Final

from benchmarks.speedgate import headergate
from benchmarks.speedgate.gates import FAIL, TIMED_SETS, Gate, Sets, evaluate, noise
from benchmarks.speedgate.moved import THRESHOLDS, label_counts, moved_answers
from benchmarks.speedgate.results import cases_of, kind_times, load_folder
from benchmarks.speedgate.storage import storage_alone

SHOW: Final = 12
CUT: Final = 70


def short(value: Any) -> str:
    """A value on one line, cut."""
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= CUT else text[: CUT - 3] + "..."


def identity_lines(label: str, sets: Sets) -> list[str]:
    """Which ``licenseid`` and Python each set of a side ran under, and the
    load: a wrong import or a busy machine shows here."""
    files = {r.get("licenseid_file") for r in sets.values() if r.get("licenseid_file")}
    pythons = {r.get("python") for r in sets.values() if r.get("python")}
    versions = {
        r.get("licenseid_version") for r in sets.values() if r.get("licenseid_version")
    }
    loaded = sorted(n for n, r in sets.items() if r.get("loaded"))
    head = f"{label}: licenseid {sorted(versions)} from {sorted(files)}; "
    lines = [head + f"Python {sorted(pythons)}"]
    foreign = sorted(n for n, r in sets.items() if r.get("from_side") is False)
    if foreign:
        lines.append(f"  WRONG IMPORT in {foreign}")
    if loaded:
        lines.append(
            f"  machine busy during {loaded}: read these as ratios only, or rerun alone"
        )
    return lines


def moved_lines(base: Sets, cand: Sets) -> list[str]:
    """Answers that differ, set by set; the first few listed with the key."""
    lines = []
    for name in TIMED_SETS:
        if not (base.get(name) and cand.get(name)):
            lines.append(f"{name}: not in both runs")
            continue
        pairs = moved_answers(name, cases_of(base.get(name)), cases_of(cand.get(name)))
        inputs = len({m.key for m in pairs})
        lines.append(f"{name}: {len(pairs)} fields differ in {inputs} inputs")
        lines.extend(
            f"  {m.key[:50]} [{m.field}] {short(m.base)} -> {short(m.cand)}"
            for m in pairs[:SHOW]
        )
    return lines


def time_lines(base: Sets, cand: Sets, twin: Sets | None) -> list[str]:
    """CPU seconds of each kind: base, candidate, base over candidate, the A/A
    ratio (base over its twin) beside it, and the medians."""
    head = f"{'kind':26s} {'n':>4s} {'base s':>8s} {'cand s':>8s} {'x':>6s} "
    lines = [head + f"{'A/A':>6s} {'med ms':>16s}"]
    for name in TIMED_SETS:
        b_times = kind_times(cases_of(cand.get(name)))
        t_times = kind_times(cases_of(twin.get(name))) if twin else {}
        for kind, a in kind_times(cases_of(base.get(name))).items():
            b = b_times.get(kind)
            if b is None:
                continue
            aa = (
                f"{a.seconds / t_times[kind].seconds:.2f}"
                if kind in t_times and t_times[kind].seconds
                else ""
            )
            ratio = f"{a.seconds / b.seconds:.1f}" if b.seconds else ""
            lines.append(
                f"{kind[:26]:26s} {a.count:4d} {a.seconds:8.2f} {b.seconds:8.2f} "
                f"{ratio:>6s} {aa:>6s} {a.median_ms:7.1f}{b.median_ms:9.1f}"
            )
    return lines


def label_lines(base: Sets, cand: Sets, labelled: dict[str, Any] | None) -> list[str]:
    """Agree, other and none against the weak labels at each bar."""
    if not labelled:
        return ["labels: pass --inputs to count them"]
    lines = []
    for cutoff in THRESHOLDS:
        a = label_counts(cases_of(base.get("core")), labelled, cutoff)
        b = label_counts(cases_of(cand.get("core")), labelled, cutoff)
        lines.append(
            f"labels at {cutoff}: agree {a['agree']} to {b['agree']}, "
            f"other {a['other']} to {b['other']}, none {a['none']} to {b['none']}"
        )
    return lines


def gate_lines(gates: list[Gate]) -> list[str]:
    """One line a gate."""
    return [f"{g.status.upper():12s} {g.name}: {g.detail}" for g in gates]


def noise_lines(base: Sets, twin: Sets | None) -> list[str]:
    """The A/A floor of the core set."""
    if not twin or not twin.get("core"):
        return ["A/A: no twin given (--twin)"]
    total, kinds = noise(base, twin)
    return [f"A/A core: twin took {total:.3f} of base; widest kind off by {kinds:.2f}x"]


def compare_folders(
    base_dir: Path,
    cand_dir: Path,
    twin_dir: Path | None,
    inputs: Path | None,
    storage: bool = False,
) -> tuple[str, bool]:
    """The report and whether a gate failed; with *storage*, the gate
    "Storage alone" judged (``storage.storage_alone``)."""
    base, cand = load_folder(base_dir), load_folder(cand_dir)
    twin = load_folder(twin_dir) if twin_dir else None
    labelled = json.loads(inputs.read_text("utf-8"))["labels"] if inputs else None
    gates = headergate.with_gate(evaluate(base, cand, labelled), base, cand)
    if storage:
        gates = [g for g in gates if g.name != "Storage alone"]
        gates.append(storage_alone(base, cand, twin))
    same = {
        r.get("inputs_digest")
        for r in (*base.values(), *cand.values())
        if r.get("inputs_digest")
    }
    lines = [
        "== Sides",
        *identity_lines("base", base),
        *identity_lines("candidate", cand),
    ]
    lines.append(
        "inputs: "
        + ("the same file" if len(same) == 1 else f"DIFFERENT ({len(same)} digests)")
    )
    lines += ["", "== Answers that moved (read first)", *moved_lines(base, cand)]
    lines += ["", "== Headers", *headergate.section(base, cand)]
    lines += [
        "",
        "== CPU seconds (x = base over candidate)",
        *time_lines(base, cand, twin),
        *noise_lines(base, twin),
    ]
    lines += ["", "== Labels and fixtures", *label_lines(base, cand, labelled)]
    lines += ["", "== Gates", *gate_lines(gates)]
    return "\n".join(lines), any(g.status == FAIL for g in gates)

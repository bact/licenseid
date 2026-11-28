# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The release gates of the 0.10.0 speed plan (section 6.2) that these sets
can answer, each as pass, fail or not measured, with its numbers."""

import statistics
from typing import Any, Final, NamedTuple

from benchmarks.speedgate.buildinputs import ONECALL_FILES
from benchmarks.speedgate.damage import NOT_READY, REFERENCE
from benchmarks.speedgate.moved import (
    ANSWER_BAR,
    THRESHOLDS,
    Moved,
    fixture_counts,
    label_counts,
    moved_answers,
    top,
)
from benchmarks.speedgate.results import (
    Cases,
    cases_of,
    kind_of,
    kind_times,
    total_seconds,
)

PASS: Final = "pass"
FAIL: Final = "fail"
NA: Final = "not measured"
CORE_FACTOR: Final = 12.0
CORE_TARGET: Final = 15.0
REAL_MEDIAN_MS: Final = 15.0
ONE_CALL_MS: Final = 300.0
ONE_CALL_FAST_MS: Final = 150.0
FAST_FILES: Final = ("real-MIT", "real-BSD-3-Clause")
CLASS_LIMIT: Final = 1.2
CLASS_FLOOR_S: Final = 0.05
ROADMAP_LIMIT_MS: Final = 200.0
LABEL_AGREE_MIN: Final = 190
LABEL_OTHER_MAX: Final = 16
DB_LIMIT_BYTES: Final = 20_000_000
MEMORY_SLACK_MB: Final = 1.0
TEXTS_CALL_SETS: Final = ("many", "cjk", "roadmap")
TIMED_SETS: Final = ("core", "prose", "many", "cjk", "options", "roadmap", "stress")
NOT_HERE: Final = (
    ("Values", "462 PyPI values: tools/pypi_licence_sample"),
    ("Accuracy test", "tests/test_accuracy.py"),
    ("Golden", "python -m tools.golden"),
    ("--diff", "read by hand"),
    ("Versions", "added by task T7"),
    ("Storage alone", "needs two runs of T6 and T7"),
    ("Platforms", "CI, tools.cli_matrix"),
)

Sets = dict[str, dict[str, Any]]


class Gate(NamedTuple):
    """One gate: its name, its status and the numbers behind it."""

    name: str
    status: str
    detail: str


def _gate(name: str, ok: bool, detail: str) -> Gate:
    return Gate(name, PASS if ok else FAIL, detail)


def core_cpu(base: Sets, cand: Sets) -> Gate:
    """Core set: CPU 12 times less or better."""
    a, b = (
        total_seconds(cases_of(base.get("core"))),
        total_seconds(cases_of(cand.get("core"))),
    )
    if not a or not b:
        return Gate("Core, CPU", NA, "core set missing")
    factor = round(a / b, 4)
    return _gate(
        "Core, CPU",
        factor >= CORE_FACTOR,
        f"{a:.1f} s to {b:.1f} s, {factor:.1f} times "
        f"(need {CORE_FACTOR:g}, target {CORE_TARGET:g})",
    )


def real_median(cand: Sets) -> Gate:
    """Median CPU of a real file, 15 ms or under."""
    times = kind_times(cases_of(cand.get("core"))).get("real")
    if times is None:
        return Gate("Real file, median", NA, "no real files")
    return _gate(
        "Real file, median",
        times.median_ms <= REAL_MEDIAN_MS,
        f"{times.median_ms:.1f} ms of {times.count} (limit {REAL_MEDIAN_MS:g})",
    )


def one_call(cand: Sets) -> Gate:
    """One call: each of 8 files 0.3 s or under; MIT and BSD-3-Clause 0.15 s."""
    cases = cases_of(cand.get("onecall"))
    files = {n[len("detect ") :]: cases[n] for n in cases if n[7:] in ONECALL_FILES}
    if not files:
        return Gate("One call", NA, "one-call set missing")
    slow = []
    for name, case in sorted(files.items()):
        limit = ONE_CALL_FAST_MS if name in FAST_FILES else ONE_CALL_MS
        if case["min_ms"] > limit:
            slow.append(f"{name} {case['min_ms']:.0f} ms over {limit:g}")
    worst = max(c["min_ms"] for c in files.values())
    return _gate(
        "One call",
        not slow,
        "; ".join(slow) or f"{len(files)} files, slowest {worst:.0f} ms",
    )


def _kind_ratio(a: float, b: float) -> float:
    return b / a if a else 0.0


def class_slowdowns(base: Sets, cand: Sets) -> list[tuple[str, float, float, float]]:
    """``(kind, base s, candidate s, ratio)`` of each kind (and stress input)
    whose base time is over the floor."""
    out = []
    for name in TIMED_SETS:
        a_times = kind_times(cases_of(base.get(name)))
        b_times = kind_times(cases_of(cand.get(name)))
        for kind, a in a_times.items():
            b = b_times.get(kind)
            if b is not None and a.seconds >= CLASS_FLOOR_S:
                out.append(
                    (kind, a.seconds, b.seconds, _kind_ratio(a.seconds, b.seconds))
                )
    return out


def no_class_slower(base: Sets, cand: Sets) -> Gate:
    """No input kind and no stress input over 1.2 times the last tag."""
    rows = class_slowdowns(base, cand)
    if not rows:
        return Gate("No class slower", NA, "no kinds to compare")
    slow = [f"{k} {r:.2f}x" for k, _, _, r in rows if r > CLASS_LIMIT]
    return _gate(
        "No class slower",
        not slow,
        "; ".join(slow)
        or f"{len(rows)} kinds, worst {max(r for *_, r in rows):.2f}x "
        f"(limit {CLASS_LIMIT})",
    )


def labels(cand: Sets, labelled: dict[str, Any] | None) -> Gate:
    """Weak labels at 0.85: agree not under 190, other not over 16."""
    if not labelled:
        return Gate("Labels", NA, "pass --inputs")
    counts = label_counts(cases_of(cand.get("core")), labelled, ANSWER_BAR)
    ok = counts["agree"] >= LABEL_AGREE_MIN and counts["other"] <= LABEL_OTHER_MAX
    return _gate(
        "Labels",
        ok,
        f"agree {counts['agree']} (min {LABEL_AGREE_MIN}), "
        f"other {counts['other']} (max {LABEL_OTHER_MAX}), none {counts['none']}",
    )


def fixtures(base: Sets, cand: Sets) -> Gate:
    """Fixtures: right not lower, wrong not higher, at 0.85, 0.7 and 0.5."""
    parts, ok = [], True
    for cutoff in THRESHOLDS:
        a = fixture_counts(cases_of(base.get("core")), cutoff)
        b = fixture_counts(cases_of(cand.get("core")), cutoff)
        ok = ok and b["right"] >= a["right"] and b["wrong"] <= a["wrong"]
        parts.append(
            f"{cutoff}: right {a['right']} to {b['right']}, "
            f"wrong {a['wrong']} to {b['wrong']}"
        )
    return _gate("Fixtures", ok, "; ".join(parts))


def prose(base: Sets, cand: Sets) -> Gate:
    """Prose: the answer (a top row at the answer cutoff) is the same on READMEs,
    notices and mixed inputs: it does not appear, disappear or change. How
    many top rows moved at lower cutoffs is information, not a failure."""
    a, b = cases_of(base.get("prose")), cases_of(cand.get("prose"))
    if not a or not b:
        return Gate("Prose", NA, "prose set missing")
    shared = sorted(a.keys() & b.keys())

    def moved_at(cut: float) -> list[str]:
        return [k for k in shared if top(a[k], cut)[0] != top(b[k], cut)[0]]

    moved = moved_at(ANSWER_BAR)
    info = ", ".join(
        f"{len(moved_at(cut))} at {cut:g} or more" for cut in THRESHOLDS[1:]
    )
    return _gate(
        "Prose",
        not moved,
        f"{len(moved)} of {len(a)} answers moved"
        + (": " + ", ".join(moved[:5]) if moved else "")
        + f" (top rows moved, not judged: {info}, {len(moved_at(0.0))} at any score)",
    )


def texts_moved(set_name: str, base: Cases, cand: Cases) -> list[Moved]:
    """The cases whose ``texts()`` differs, where both sides record it."""
    return [
        Moved(set_name, key, "texts", base[key]["texts"], cand[key]["texts"])
        for key in sorted(base.keys() & cand.keys())
        if "texts" in base[key]
        and "texts" in cand[key]
        and base[key]["texts"] != cand[key]["texts"]
    ]


def texts(base: Sets, cand: Sets) -> Gate:
    """``texts()`` equal wherever a set records it (many-text, CJK and roadmap
    inputs); the ``TEXTS`` of the top record equal under every option and on
    the core set where the top answer is the same."""
    if not cases_of(base.get("many")):
        return Gate("TEXTS", NA, "many set missing")
    bad: list[Moved] = []
    for name in TEXTS_CALL_SETS:
        bad.extend(
            texts_moved(name, cases_of(base.get(name)), cases_of(cand.get(name)))
        )
    for name in ("options", "core"):
        a, b = cases_of(base.get(name)), cases_of(cand.get(name))
        for key in sorted(a.keys() & b.keys()):
            same = top(a[key], 0.0)[0] == top(b[key], 0.0)[0]
            if same and a[key].get("texts_row") != b[key].get("texts_row"):
                bad.append(
                    Moved(
                        name, key, "texts_row", a[key]["texts_row"], b[key]["texts_row"]
                    )
                )
    return _gate(
        "TEXTS",
        not bad,
        f"{len(bad)} moved" + (": " + ", ".join(m.key for m in bad[:5]) if bad else ""),
    )


def roadmap_time(cand: Sets) -> Gate:
    """Inputs of items 11, 61 and 68 each under 0.2 s."""
    cases = cases_of(cand.get("roadmap"))
    slow = [
        f"{k[:40]} {c['cpu_ms']:.0f} ms"
        for k, c in cases.items()
        if kind_of(k) in ("roadmap:11", "roadmap:61", "roadmap:68")
        and (c.get("cpu_ms") or 0) > ROADMAP_LIMIT_MS
    ]
    if not cases:
        return Gate("Roadmap inputs", NA, "roadmap set missing")
    return _gate(
        "Roadmap inputs", not slow, "; ".join(slow) or "items 11, 61, 68 under 0.2 s"
    )


def item_68(base: Sets, cand: Sets) -> Gate:
    """No HPND-family fragment becomes an answer that is another licence."""
    a, b = cases_of(base.get("roadmap")), cases_of(cand.get("roadmap"))
    new = []
    for key, case in b.items():
        if not key.startswith("64 HPND:") or key not in a:
            continue
        answer, _ = top(case, ANSWER_BAR)
        own = key.split(":")[1].split()[0]
        if answer and answer != own and top(a[key], ANSWER_BAR)[0] is None:
            new.append(f"{key} -> {answer}")
    return _gate(
        "Item 68", not new, "; ".join(new) or "no new answer on the HPND family"
    )


def grams_differ(result: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Whether a damaged copy's gram tables are not the expected ones, its
    tables could not be read, or the file's bytes changed. A side without
    the tables has none of these fields: nothing differs."""
    if "grams_error" in result or result.get("bytes_same") is False:
        return True
    return "grams" in expected and result.get("grams") != expected["grams"]


def refused(result: dict[str, Any]) -> bool:
    """Whether a copy that is not of the side's build was refused as it must
    be: the lookups stopped with ``DatabaseNotReadyError`` and the file's
    bytes are the same."""
    return (
        "DatabaseNotReadyError" in str(result.get("error", ""))
        and "cases" not in result
        and result.get("bytes_same") is not False
    )


def _damage_differs(name: str, result: dict[str, Any], kinds: Sets) -> bool:
    """Whether the damaged copy *name* answers otherwise than its reference
    (the intact build, unless it has one of its own), or is not refused
    where it must be."""
    if name in NOT_READY:
        return not refused(result)
    reference = kinds.get(name + REFERENCE, kinds["none"])
    expected = kinds.get(name + REFERENCE, {"cases": cases_of(kinds["none"])})
    return bool(
        moved_answers(name, cases_of(expected), cases_of(result))
        or grams_differ(result, reference)
    )


def damage(cand: Sets) -> Gate:
    """Damage: every case equals the intact build of the same side, and a
    copy not of its build is refused."""
    kinds = (cand.get("damage") or {}).get("kinds")
    if not kinds or "none" not in kinds:
        return Gate("Damage", NA, "damage set missing")
    bad, skipped = [], []
    for name, result in kinds.items():
        if not result.get("applicable", True):
            skipped.append(name)
        elif not name.endswith(REFERENCE) and _damage_differs(name, result, kinds):
            bad.append(name)
    note = f"; {len(skipped)} not applicable ({', '.join(skipped)})" if skipped else ""
    return _gate(
        "Damage",
        not bad,
        (
            ", ".join(bad) + " differ"
            if bad
            else f"{len(kinds) - len(skipped)} kinds equal their reference"
        )
        + note,
    )


def threads(cand: Sets) -> Gate:
    """Threads: answers equal one thread, the first-call race agrees."""
    result = cand.get("threads")
    if not result or "differing" not in result:
        return Gate("Threads", NA, "threads set missing")
    ok = (
        result["differing"] == 0
        and result["first_call_race_same"]
        and not result["errors"]
    )
    return _gate(
        "Threads",
        ok,
        f"{result['threads']} threads, {result['items']} items: "
        f"differing {result['differing']}, "
        f"race same {result['first_call_race_same']}, "
        f"errors {len(result['errors'])}",
    )


def memory(base: Sets, cand: Sets, slack: float = MEMORY_SLACK_MB) -> Gate:
    """Memory: no peak over the last tag's (a slack for page rounding)."""
    a, b = (
        (base.get("memory") or {}).get("peak_mb"),
        (cand.get("memory") or {}).get("peak_mb"),
    )
    if not a or not b:
        return Gate("Memory", NA, "memory set missing")
    over = [
        f"{k} {b[k]:.0f} over {a[k]:.0f}" for k in a if k in b and b[k] > a[k] + slack
    ]
    last = list(b)[-1]
    return _gate(
        "Memory",
        not over,
        "; ".join(over) or f"peak {b[last]:.0f} MB, last tag {a.get(last, 0):.0f} MB",
    )


def db_size(cand: Sets) -> Gate:
    """The database file under 20 MB."""
    size = (cand.get("meta") or {}).get("db_bytes")
    if size is None:
        return Gate("Database size", NA, "no meta")
    return _gate(
        "Database size", size < DB_LIMIT_BYTES, f"{size / 1e6:.1f} MB (limit 20)"
    )


def evaluate(base: Sets, cand: Sets, labelled: dict[str, Any] | None) -> list[Gate]:
    """Every gate, in the order of the plan's table."""
    gates = [
        core_cpu(base, cand),
        real_median(cand),
        one_call(cand),
        no_class_slower(base, cand),
        labels(cand, labelled),
        fixtures(base, cand),
        prose(base, cand),
        texts(base, cand),
        roadmap_time(cand),
        item_68(base, cand),
        damage(cand),
        threads(cand),
        memory(base, cand),
        db_size(cand),
    ]
    gates.extend(Gate(name, NA, why) for name, why in NOT_HERE)
    return gates


def noise(base: Sets, twin: Sets, set_name: str = "core") -> tuple[float, float]:
    """The A/A floor of a set: total time ratio of the twin to the base, and
    the largest ratio over the kinds."""
    a, b = cases_of(base.get(set_name)), cases_of(twin.get(set_name))
    ratio = total_seconds(b) / total_seconds(a) if total_seconds(a) else 0.0
    kinds = [
        t.seconds / kind_times(a)[k].seconds
        for k, t in kind_times(b).items()
        if k in kind_times(a) and kind_times(a)[k].seconds > CLASS_FLOOR_S
    ]
    return ratio, max((max(r, 1 / r) for r in kinds if r), default=1.0)


def median_ratio(a: Cases, b: Cases) -> float:
    """Median over shared cases of the base to candidate CPU ratio."""
    ratios = [
        a[k]["cpu_ms"] / b[k]["cpu_ms"]
        for k in a.keys() & b.keys()
        if a[k].get("cpu_ms") and b[k].get("cpu_ms")
    ]
    return statistics.median(ratios) if ratios else 0.0

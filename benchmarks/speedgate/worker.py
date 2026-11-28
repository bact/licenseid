# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The child process of a run: one side's ``licenseid`` over one set.

It runs under the side's own Python path (``PYTHONPATH=<side>/src``) and
imports nothing of this repository: standard library and ``licenseid`` only.
Its first result field says which ``licenseid`` it imported, so a wrong import
shows in the result. Modes: ``detect`` (a set, or one case of it), ``memory``
and ``threads``.
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import threading
import time
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

WARM = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software"
)
TOP = 3


def identity(side: Path) -> dict[str, Any]:
    """Which ``licenseid`` this process imported, and which Python."""
    import licenseid

    imported = Path(licenseid.__file__ or "").resolve()
    return {
        "licenseid_file": str(imported),
        "licenseid_version": getattr(licenseid, "__version__", None),
        "python": platform.python_version(),
        "from_side": str(imported).startswith(str(side.resolve())),
    }


def rows_of(results: list[dict[str, Any]]) -> list[list[Any]]:
    """The top rows as ``[expression, score, method, exact]``."""
    return [
        [r["expression"], r.get("score"), r.get("method"), r.get("exact")]
        for r in results[:TOP]
    ]


def measure(det: Any, case: dict[str, Any]) -> dict[str, Any]:
    """One case: its rows, ``TEXTS`` and CPU milliseconds (warm)."""
    text = case["text"]
    out: dict[str, Any] = {"chars": len(text)}
    start = time.process_time()
    try:
        results = det.detect(text, **case.get("options", {}))
    except Exception as exc:  # recorded, never raised: one bad case is a result
        out.update(error=f"{type(exc).__name__}: {str(exc)[:120]}", rows=[])
        out["cpu_ms"] = 1e3 * (time.process_time() - start)
        return out
    out["cpu_ms"] = 1e3 * (time.process_time() - start)
    out["rows"] = rows_of(results)
    out["texts_row"] = [r.get("texts") for r in results[:1]]
    if case.get("texts_call"):
        start = time.process_time()
        try:
            out["texts"] = det.texts(text)
        except Exception as exc:
            out["texts"] = f"ERR {type(exc).__name__}"
        out["texts_ms"] = 1e3 * (time.process_time() - start)
    return out


def warm_up(det: Any, cases: list[dict[str, Any]]) -> None:
    """One untimed pass over the cases of a set: the same inputs and options
    as the timed pass, the results discarded. Whatever a side reads lazily on
    a first use (a stored text, a table) is read here, not in a timed case."""
    for case in cases:
        measure(det, case)


def run_detect(args: argparse.Namespace, inputs: dict[str, Any]) -> dict[str, Any]:
    """Every case of a set, after one untimed pass over the same cases. The
    one named by ``--only`` (the stress set: a process a case) gets one small
    call before it instead, as a pass would double a case of minutes."""
    from licenseid.detector import LicenseDetector

    det = LicenseDetector(args.db)
    cases = inputs["sets"][args.set]
    if args.only:
        cases = [c for c in cases if c["key"] == args.only]
        det.detect(WARM)
    else:
        warm_up(det, cases)
    done: dict[str, Any] = {}
    for number, case in enumerate(cases, 1):
        done[case["key"]] = measure(det, case)
        if number % 100 == 0:
            print(f"{args.set}: {number}/{len(cases)}", file=sys.stderr, flush=True)
    return {"cases": done}


#: Inputs of the gram tables besides the set's: kana text, and no List word.
GRAM_EXTRA = {
    "kana": "本ソフトウェアは無保証で提供されます。許諾書の条項に従う。" * 3,
    "no match": "zzqx vvkk wwpp qqjj xxyy kkzz ppvv jjqq yyxx zzkk",
}


def run_grams(args: argparse.Namespace, inputs: dict[str, Any]) -> dict[str, Any]:
    """``gram_scores`` of each input of the set and of ``GRAM_EXTRA``: a
    digest of each table (rows, grams, total) and its count of rows."""
    from licenseid.database import LicenseDatabase, gram_scores
    from licenseid.normalize import normalize_text

    db = LicenseDatabase(args.db, create=False)
    texts = {c["key"]: c["text"] for c in inputs["sets"][args.set]}
    tables: dict[str, Any] = {}
    for key, text in {**texts, **GRAM_EXTRA}.items():
        table = gram_scores(db, normalize_text(text))
        rows = [list(row) for row in table.rows]
        blob = json.dumps([rows, table.grams, table.total]).encode("utf-8")
        tables[key] = {
            "digest": hashlib.sha256(blob).hexdigest(),
            "rows": len(rows),
        }
    return {"tables": tables}


def peak_mb() -> float:
    """Peak resident set size of this process in MB."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1e6 if sys.platform == "darwin" else 1e3)


def run_memory(args: argparse.Namespace, inputs: dict[str, Any]) -> dict[str, Any]:
    """Peak RSS after the import, one file, the real files, every core input."""
    peaks = {"start": peak_mb()}
    from licenseid.detector import LicenseDetector

    peaks["import"] = peak_mb()
    cases = inputs["sets"]["core"]
    real = [c for c in cases if c["kind"] == "real"]
    det = LicenseDetector(args.db)
    peaks["detector"] = peak_mb()
    det.detect(real[0]["text"])
    peaks["1 input"] = peak_mb()
    for case in real:
        det.detect(case["text"])
    peaks[f"{len(real)} inputs"] = peak_mb()
    for case in cases:
        det.detect(case["text"])
    peaks[f"{len(cases)} inputs"] = peak_mb()
    return {"peak_mb": peaks}


def answers(det: Any, items: list[dict[str, Any]]) -> list[list[Any]]:
    """The top rows (expression, score) of each item."""
    return [
        [[r["expression"], r["score"]] for r in det.detect(c["text"])[:TOP]]
        for c in items
    ]


def run_pool(count: int, target: Callable[[int], None]) -> float:
    """Run *target* in *count* threads; the seconds they took together."""
    pool = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    start = time.perf_counter()
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    return time.perf_counter() - start


def rotated_pass(
    det: Any, items: list[dict[str, Any]], single: list[list[Any]], count: int
) -> dict[str, Any]:
    """Each thread over the items in its own rotation, so calls interleave:
    the seconds, the answers that differ from one thread, the errors."""
    got: list[list[list[Any]] | None] = [None] * count
    errors: list[str] = []

    def work(index: int) -> None:
        try:
            got[index] = answers(det, items[index:] + items[:index])
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {str(exc)[:100]}")

    seconds = run_pool(count, work)
    differing = 0
    for index, rows in enumerate(got):
        if rows is not None:
            back = rows[len(items) - index :] + rows[: len(items) - index]
            differing += sum(a != b for a, b in zip(single, back))
    return {"n_threads_s": seconds, "differing": differing, "errors": errors}


def first_call_race(
    args: argparse.Namespace, item: dict[str, Any], expected: list[Any]
) -> tuple[bool, list[str]]:
    """First calls of several threads on a fresh detector: the same answer
    from all, and the errors."""
    from licenseid.detector import LicenseDetector

    fresh = LicenseDetector(args.db)
    first: list[Any] = [None] * args.threads
    errors: list[str] = []

    def race(index: int) -> None:
        try:
            first[index] = answers(fresh, [item])
        except Exception as exc:
            errors.append(f"cold {type(exc).__name__}: {str(exc)[:100]}")

    run_pool(args.threads, race)
    return all(f == [expected] for f in first), errors


def run_threads(args: argparse.Namespace, inputs: dict[str, Any]) -> dict[str, Any]:
    """The same detector from several threads; answers against one thread,
    and a race of first calls."""
    from licenseid.detector import LicenseDetector

    cases = inputs["sets"]["core"]
    real = [c for c in cases if c["kind"] == "real"][: args.items]
    items = real + [c for c in cases if c["kind"] != "real"][: args.items // 2]
    det = LicenseDetector(args.db)
    start, cpu = time.perf_counter(), time.process_time()
    single = answers(det, items)
    result: dict[str, Any] = {
        "items": len(items),
        "threads": args.threads,
        "one_thread_s": time.perf_counter() - start,
        "one_thread_cpu_s": time.process_time() - cpu,
    }
    result.update(rotated_pass(det, items, single, args.threads))
    same, errors = first_call_race(args, items[0], single[0])
    result.update(first_call_race_same=same)
    result["errors"] = result["errors"] + errors
    return result


def main() -> int:
    """Run one mode and write its result as JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["detect", "memory", "threads", "grams"])
    parser.add_argument("--side", type=Path, required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--set", default="core")
    parser.add_argument("--only", default="")
    parser.add_argument("--items", type=int, default=100)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    warnings.simplefilter("ignore")
    inputs = json.loads(args.inputs.read_text("utf-8"))
    result = identity(args.side)
    if not result["from_side"]:
        print(f"wrong import: {result['licenseid_file']}", file=sys.stderr)
    modes = {
        "detect": run_detect,
        "grams": run_grams,
        "memory": run_memory,
        "threads": run_threads,
    }
    result.update(modes[args.mode](args, inputs))
    result["pid"] = os.getpid()
    args.out.write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["from_side"] else 3


if __name__ == "__main__":
    sys.exit(main())

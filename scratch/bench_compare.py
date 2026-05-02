#!/usr/bin/env python3
"""Compare two licenseid branches on recall, precision, speed, memory.

Runs bench_single.py twice via subprocess (complete process isolation).
Sequential — no parallel execution, no shared state.

Usage:
    python bench_compare.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).parent / "bench_single.py"
BRANCHES = [
    ("/tmp/licenseid-main/src/licenseid", "main"),
    ("/Users/art/projects/licenseid/src/licenseid", "license-marker"),
]
RATES = ["00", "02", "05"]


def run_branch(src_path: str, label: str) -> dict:
    print(f"\nRunning: {label} …", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), src_path, label],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        print(f"  ERROR (exit {proc.returncode}):", file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        sys.exit(1)
    # Progress lines go to stderr; JSON result is the last stdout line
    for line in proc.stderr.splitlines():
        print(f"  {line}", flush=True)
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    print(f"  subprocess wall time: {elapsed:.1f}s")
    return result


def fmt_pct(v: float) -> str:
    return f"{v:6.2f}%"


def print_report(r: dict) -> None:
    s = r["stats"]
    n = r["n_fixtures"]
    print(f"\n  Branch: {r['label']}  ({n} fixtures, {r['total_q']} queries)")
    print(
        f"  {'Rate':<12}  {'Recall@1':>9}  {'Recall@3':>9}  {'Recall@5':>9}  {'N':>5}"
    )
    print(f"  {'-' * 52}")
    for rate in RATES:
        if s[rate]["total"] == 0:
            continue
        t = s[rate]["total"]
        r1 = s[rate]["top1"] / t * 100
        r3 = s[rate]["top3"] / t * 100
        r5 = s[rate]["top5"] / t * 100
        lbl = "Verbatim" if rate == "00" else f"{rate}% noise"
        print(f"  {lbl:<12}  {fmt_pct(r1)}  {fmt_pct(r3)}  {fmt_pct(r5)}  {t:>5}")

    prec = (
        r["correct_returned"] / r["total_returned"] * 100 if r["total_returned"] else 0
    )
    avg_ret = r["total_returned"] / r["total_q"]
    print(f"\n  Precision (correct / all returned): {prec:.2f}%")
    print(f"  Avg results per query:              {avg_ret:.2f}")
    wt = r["wall_time"]
    print(
        f"\n  Wall time: {wt:.1f}s  ({r['total_q'] / wt:.1f} q/s, {wt / r['total_q'] * 1000:.1f} ms/q)"
    )
    print(f"  Peak memory: {r['peak_mem_mb']:.1f} MB")


def print_comparison(a: dict, b: dict) -> None:
    W = 34
    print(f"\n{'=' * 70}")
    print(f"  COMPARISON  {a['label']}  →  {b['label']}")
    print(f"{'=' * 70}")
    print(f"  {'Metric':<{W}}  {'main':>8}  {'lic-marker':>10}  {'Δ':>8}")
    print(f"  {'-' * 68}")
    for rate in RATES:
        lbl = "Verbatim" if rate == "00" else f"{rate}% noise"
        for k, col in [
            ("top1", "Recall@1"),
            ("top3", "Recall@3"),
            ("top5", "Recall@5"),
        ]:
            ta, tb = a["stats"][rate], b["stats"][rate]
            if ta["total"] == 0 or tb["total"] == 0:
                continue
            va = ta[k] / ta["total"] * 100
            vb = tb[k] / tb["total"] * 100
            mark = " ▲" if vb > va + 0.005 else (" ▼" if vb < va - 0.005 else "  ")
            name = f"{lbl} {col}"
            print(f"  {name:<{W}}  {va:>7.2f}%  {vb:>9.2f}%  {vb - va:>+7.2f}%{mark}")

    print(f"  {'-' * 68}")
    ap = a["correct_returned"] / a["total_returned"] * 100
    bp = b["correct_returned"] / b["total_returned"] * 100
    print(f"  {'Precision':<{W}}  {ap:>7.2f}%  {bp:>9.2f}%  {bp - ap:>+7.2f}%")
    at, bt = a["wall_time"], b["wall_time"]
    print(f"  {'Wall time (s)':<{W}}  {at:>8.1f}  {bt:>10.1f}  {bt - at:>+7.1f}s")
    aq = a["total_q"] / at
    bq = b["total_q"] / bt
    print(f"  {'Throughput (q/s)':<{W}}  {aq:>8.1f}  {bq:>10.1f}  {bq - aq:>+7.1f}")
    am, bm = a["peak_mem_mb"], b["peak_mem_mb"]
    print(f"  {'Peak memory (MB)':<{W}}  {am:>8.1f}  {bm:>10.1f}  {bm - am:>+7.1f}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    results = []
    for src, label in BRANCHES:
        results.append(run_branch(src, label))
        print_report(results[-1])

    if len(results) == 2:
        print_comparison(results[0], results[1])

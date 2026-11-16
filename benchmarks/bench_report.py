# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Render the Markdown comparison of two ``bench_single.py`` results."""

from typing import Any

_RECALL_COLUMNS: list[tuple[str, str]] = [
    ("top1", "Recall@1"),
    ("top3", "Recall@3"),
    ("top5", "Recall@5"),
    ("top10", "Recall@10"),
    ("top20", "Recall@20"),
    ("top30", "Recall@30"),
    ("top40", "Recall@40"),
    ("top50", "Recall@50"),
]

_EMPTY_STAT: dict[str, int] = {"total": 0, **{k: 0 for k, _ in _RECALL_COLUMNS}}

_TIER_KEYS: list[tuple[str, str]] = [
    ("tier0", "Tier 0 (short-text)"),
    ("tier05", "Tier 0.5 (marker)"),
    ("tier1", "Tier 1 (FTS5 pool)"),
    ("tier2", "Tier 2 (ranked)"),
    ("missed", "Missed"),
]

_TABLE_ALIGN = "| :--- | ---: | ---: | ---: |"


def _mark(before: float, after: float) -> str:
    """Return the change marker: green up, red down, a space when level."""
    if after > before + 0.005:
        return " 🟢"
    return " 🔴" if after < before - 0.005 else " "


def _metric_section(a: dict[str, Any], b: dict[str, Any], t_idx: int) -> list[str]:
    """Return the recall table of one input type."""
    la, lb = a["label"], b["label"]
    t_key = f"type_{t_idx}"
    lines = [
        f"### Input Type {t_idx}",
        f"| Category | {la} | {lb} | Δ |",
        _TABLE_ALIGN,
    ]
    stats_a = a["stats"].get(t_key, {})
    stats_b = b["stats"].get(t_key, {})
    for subcat in sorted(set(stats_a) | set(stats_b)):
        ta = stats_a.get(subcat, _EMPTY_STAT)
        tb = stats_b.get(subcat, _EMPTY_STAT)
        for k, col in _RECALL_COLUMNS:
            if ta["total"] == 0 or tb["total"] == 0:
                continue
            if k not in ta or k not in tb:
                continue
            va = ta[k] / ta["total"] * 100
            vb = tb[k] / tb["total"] * 100
            lines.append(
                f"| {subcat} {col} | {va:.2f}% | {vb:.2f}% |"
                f" {vb - va:+.2f}%{_mark(va, vb)} |"
            )
    lines.append("")
    return lines


def _sum_tier(data: dict[str, Any], tkey: str, field: str) -> int:
    """Sum one tier-stats field over all subcategories of an input type."""
    return sum(
        v.get(field, 0) for v in data.get("tier_stats", {}).get(tkey, {}).values()
    )


def _tier_section(a: dict[str, Any], b: dict[str, Any], t_idx: int) -> list[str]:
    """Return the tier-recall table of one input type, empty when no data."""
    t_key = f"type_{t_idx}"
    total_a = _sum_tier(a, t_key, "total")
    total_b = _sum_tier(b, t_key, "total")
    if total_a == 0 and total_b == 0:
        return []
    lines = [
        f"### Input Type {t_idx} tier recall",
        f"| Tier | main (n={total_a}) | license-marker (n={total_b}) | Δ |",
        _TABLE_ALIGN,
    ]
    for tier_key, tier_label in _TIER_KEYS:
        ca = _sum_tier(a, t_key, tier_key)
        cb = _sum_tier(b, t_key, tier_key)
        ra = ca / total_a * 100 if total_a else 0
        rb = cb / total_b * 100 if total_b else 0
        lines.append(
            f"| {tier_label} | {ra:.2f}% ({ca}) |"
            f" {rb:.2f}% ({cb}) | {rb - ra:+.2f}%{_mark(ra, rb)} |"
        )
    lines.append("")
    return lines


def _percent(count: int, total: int) -> float:
    """Return count as a percentage of total, 0 when total is 0."""
    return count / total * 100 if total else 0


def _global_summary(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Return the global summary table: recall, precision, time, memory."""
    ar = _percent(a["correct_returned"], a["total_q"])
    br = _percent(b["correct_returned"], b["total_q"])
    ap = _percent(a["correct_returned"], a["total_returned"])
    bp = _percent(b["correct_returned"], b["total_returned"])
    at, bt = a["wall_time"], b["wall_time"]
    aq = a["total_q"] / at if at > 0 else 0
    bq = b["total_q"] / bt if bt > 0 else 0
    am, bm = a["peak_mem_mb"], b["peak_mem_mb"]
    avg_a, avg_b = a.get("avg_mem_mb", 0), b.get("avg_mem_mb", 0)
    return [
        "### Global Summary",
        f"| Metric | {a['label']} | {b['label']} | Δ |",
        _TABLE_ALIGN,
        f"| Recall | {ar:.2f}% | {br:.2f}% | {br - ar:+.2f}% |",
        f"| Precision | {ap:.2f}% | {bp:.2f}% | {bp - ap:+.2f}% |",
        f"| Wall time (s) | {at:.1f} | {bt:.1f} | {bt - at:+.1f}s |",
        f"| Throughput (q/s) | {aq:.1f} | {bq:.1f} | {bq - aq:+.1f} |",
        f"| Peak memory (MB) | {am:.1f} | {bm:.1f} | {bm - am:+.1f} |",
        f"| End memory (MB) | {avg_a:.1f} | {avg_b:.1f} | {avg_b - avg_a:+.1f} |",
        "",
    ]


def generate_markdown_report(
    a: dict[str, Any], b: dict[str, Any], timestamp: str
) -> str:
    """Render the Markdown comparison of results ``a`` and ``b``."""
    lines = [
        f"# Benchmark Comparison: `{a['label']}` vs `{b['label']}`",
        f"**Date:** {timestamp}",
        "",
        "## Metrics",
        "",
    ]
    for t_idx in range(1, 6):
        lines.extend(_metric_section(a, b, t_idx))
    lines.extend(["## Tier Recall", ""])
    for t_idx in range(1, 6):
        lines.extend(_tier_section(a, b, t_idx))
    lines.extend(_global_summary(a, b))
    return "\n".join(lines)

# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Score keeping for ``bench_single.py``: recall counters per input type.

Import only after the source tree under test is on ``sys.path``.
"""

from typing import Any

from bench_single_matcher import InstrumentedMatcher, id_of

CATEGORIES: tuple[str, ...] = (
    "type_1",
    "type_2",
    "type_3",
    "type_4",
    "type_5",
    "type_51",
)
TOP_STEPS: tuple[int, ...] = (3, 5, 10, 20, 30, 40, 50)
TIER_NAMES: tuple[str, ...] = ("tier0", "tier05", "tier1", "tier2")


def init_stat() -> dict[str, int]:
    """Return zeroed recall counters for one subcategory."""
    stat = {"total": 0, "top1": 0}
    stat.update({f"top{n}": 0 for n in TOP_STEPS})
    return stat


def init_tier_stat() -> dict[str, int]:
    """Per-tier recall counters for a single subcat."""
    return {"total": 0, "tier0": 0, "tier05": 0, "tier1": 0, "tier2": 0, "missed": 0}


class Scoreboard:
    """Counters and failures of one run, by category and subcategory."""

    def __init__(self, matcher: InstrumentedMatcher) -> None:
        self.matcher = matcher
        self.stats: dict[str, dict[str, dict[str, int]]] = {c: {} for c in CATEGORIES}
        self.tier_stats: dict[str, dict[str, dict[str, int]]] = {
            c: {} for c in CATEGORIES
        }
        self.global_counts = {"total_returned": 0, "correct_returned": 0}
        self.failures: list[dict[str, Any]] = []

    def ensure(self, category: str, subcat: str) -> None:
        """Create the counters of *subcat* if it has none yet."""
        if subcat not in self.stats[category]:
            self.stats[category][subcat] = init_stat()
            self.tier_stats[category][subcat] = init_tier_stat()

    def category_total(self, category: str) -> int:
        """Return the number of queries run for *category*."""
        return sum(s["total"] for s in self.stats[category].values())

    def total_queries(self) -> int:
        """Return the number of queries run for all categories."""
        return sum(self.category_total(c) for c in self.stats)

    def check(self, true_id: str, text: str, category: str, subcat: str) -> None:
        """Match *text*, expected to be *true_id*, and count the outcome."""
        results, trace = self.matcher.match_traced(text, true_id)
        matched_ids = [id_of(r) for r in results]
        stat = self.stats[category][subcat]

        stat["total"] += 1
        self.global_counts["total_returned"] += len(matched_ids)
        self.global_counts["correct_returned"] += sum(
            1 for lid in matched_ids if lid == true_id
        )

        if matched_ids and matched_ids[0] == true_id:
            stat["top1"] += 1
        else:
            self.failures.append(
                {
                    "cat": category,
                    "subcat": subcat,
                    "true": true_id,
                    "got": matched_ids[0] if matched_ids else "NONE",
                }
            )
        for n in TOP_STEPS:
            if true_id in matched_ids[:n]:
                stat[f"top{n}"] += 1
        self._count_tier(self.tier_stats[category][subcat], trace.get("hit_tier"))

    @staticmethod
    def _count_tier(tier_stat: dict[str, int], tier_name: str | None) -> None:
        """Count the tier that first surfaced the correct answer."""
        tier_stat["total"] += 1
        if tier_name in TIER_NAMES:
            tier_stat[str(tier_name)] += 1
        else:
            tier_stat["missed"] += 1

# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Matcher for ``bench_single.py``: records the tier that found the answer.

Import only after the source tree under test is on ``sys.path``.
"""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast

from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.shorttext import match_name_tier

if TYPE_CHECKING:
    from licenseid.types import DetectOptions


def id_of(item: Mapping[str, Any]) -> Any:
    """Return the licence ID of a result or candidate.

    Older source trees give ``license_id``; the public result of newer
    ones gives ``expression``.
    """
    return item.get("license_id", item.get("expression"))


def _has_id(items: Iterable[Mapping[str, Any]], true_id: str) -> bool:
    """True if one of *items* names *true_id*."""
    return any(id_of(item) == true_id for item in items)


class InstrumentedMatcher(LicenseDetector):
    """Thin subclass used only by benchmarks to record per-tier recall.

    Production behaviour is unchanged. This class adds `match_traced`,
    which calls the same private methods as `detect` but records at which
    tier the correct candidate first appeared.
    """

    def match_traced(self, text: str, true_id: str) -> tuple[list[Any], dict[str, Any]]:
        """Run the full pipeline and return (results, trace).

        ``trace`` contains:
          ``hit_tier``: one of 'tier0', 'tier05', 'tier1', 'tier2', or None.
        """
        results = self.detect(text)
        trace: dict[str, Any] = {"hit_tier": None}
        if text:
            trace["hit_tier"] = self._hit_tier(text, true_id, results)
        return results, trace

    def _hit_tier(self, text: str, true_id: str, results: list[Any]) -> str | None:
        """Name the first tier that would have surfaced *true_id*.

        Reconstructs the tier decisions of detect() in read-only order.
        Guards use hasattr so this works on older source trees that lack
        certain attributes (e.g. ``markers``, which early releases lack).
        """
        norm_input = normalize_text(text)

        # Tier 0.5: marker detection
        marker_candidates: list[Any] = []
        if hasattr(self, "markers"):
            marker_candidates = self.markers.detect(text)
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            # An exact marker fired: the pipeline returned via the marker
            # path, so no further tier can be inspected.
            return "tier05" if _has_id(spdx_exact, true_id) else None

        # Tier 0: short-text shortcut
        short = self._short_text_hits(norm_input)
        if short is not None:
            return "tier0" if _has_id(short, true_id) else None

        # Tier 0.5 (non-exact markers only): is true_id in the marker pool?
        if _has_id(marker_candidates, true_id):
            return "tier05"

        # Tier 1: the text candidates, merged with the markers as in detect()
        if _has_id(self._tier1_pool(text, marker_candidates), true_id):
            return "tier1"

        # Tier 2: ranked output (final results from detect())
        return "tier2" if _has_id(results, true_id) else None

    def _short_text_hits(self, norm_input: str) -> list[Any] | None:
        """Tier 0 hits for a short input, or None when Tier 0 did not answer.
        A tree of 0.10.0 or later has no detector method for it."""
        if len(norm_input.split()) >= 20:
            return None
        if hasattr(self, "_match_short_text"):
            short = self._match_short_text(norm_input)
        else:
            short = match_name_tier(self.db, norm_input).found
        if short and short[0]["score"] > 1.0:
            return list(short)
        return None

    def _tier1_pool(self, text: str, marker_candidates: list[Any]) -> list[Any]:
        """Tier 1 candidates plus the marker candidates not among them."""
        request = cast("DetectOptions", {"text": text})
        pool: list[Any] = []
        if hasattr(self, "_get_candidates"):
            # A list, or since 0.10.0 the candidates with their bound.
            found = self._get_candidates(request, text)
            pool = list(getattr(found, "found", found))
        seen = {c["license_id"] for c in pool}
        for cand in marker_candidates:
            if cand["license_id"] not in seen:
                pool.append(cand)
                seen.add(cand["license_id"])
        return pool

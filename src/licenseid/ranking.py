# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Ordering of ranked candidates: the one sort key, and the -only / -or-later
tie-breaker that runs after ranking."""

from collections.abc import Callable

from licenseid.classify import has_or_later_language
from licenseid.types import InternalMatch

# Effective score penalty applied to deprecated licenses during ranking.
# Ensures that when a deprecated alias (e.g. GPL-2.0) and its canonical
# non-deprecated replacement (e.g. GPL-2.0-only) are both candidates with
# similar similarity scores, the canonical ID wins.  Calibrated at 0.03:
# large enough to overcome the typical 0.01–0.02 score gap caused by
# marker-confidence differences, small enough to avoid masking cases
# where the deprecated ID genuinely matches better (e.g. inputs that
# reference only "GPL-2.0" with no "only"/"or-later" qualifier).
DEP_PENALTY: float = 0.03

# -only / -or-later tie-breaker: two scores closer than TIE_WINDOW are a tie,
# and the granting language decides it by moving them TIE_NUDGE apart each
# way (together, the whole window). See apply_version_suffix_tiebreaker.
TIE_WINDOW: float = 0.01
TIE_NUDGE: float = 0.005


def ranking_key(
    enable_popularity: bool,
) -> Callable[[InternalMatch], tuple[float, bool, float, str]]:
    """The one ordering of ranked candidates, used wherever they are sorted.

    1. Highest score, with DEP_PENALTY taken off a deprecated ID so that it
       ranks below its canonical replacement when the scores are close.
    2. Non-deprecated before deprecated.
    3. Higher popularity, when enabled.
    4. License ID, so the order is the same whatever order they arrive in.
    """

    def key(match: InternalMatch) -> tuple[float, bool, float, str]:
        deprecated = match.get("is_deprecated", False)
        return (
            -(match["score"] - (DEP_PENALTY if deprecated else 0.0)),
            deprecated,
            -match.get("pop_score", 0) if enable_popularity else 0.0,
            match["license_id"],
        )

    return key


def apply_version_suffix_tiebreaker(
    ranked: list[InternalMatch],
    raw_text: str,
    is_pure: bool,
    enable_pop: bool = False,
) -> list[InternalMatch]:
    """Break -only / -or-later ties using granting language in the input.

    The two license bodies are identical, so their scores tie and only
    the alphabetical ID tie-break (-only first) would separate them. When
    two candidates share the same base ID (e.g. GPL-2.0-only and
    GPL-2.0-or-later) and their scores differ by less than TIE_WINDOW,
    the preferred one gains TIE_NUDGE and the other loses it. Results
    stay sorted by score, so the choice has to be a score; the price is
    that the reported scores move by up to TIE_NUDGE and a pair member
    can pass an unrelated license scoring within that of it.

    - Pure license text: the body is identical for both; the GPL appendix
      also contains the 'or later' template, making regexes unreliable.
      Default to -only (conservative: grant exactly this version).
    - Mixed / source-file text: check for explicit granting language.
      Granting language present → prefer -or-later.
      No granting language      → prefer -only.
    """
    if is_pure:
        or_later_signal = False  # body text indistinguishable; default -only
    else:
        or_later_signal = has_or_later_language(raw_text)

    id_to_score = {r["license_id"]: r["score"] for r in ranked}
    adjustments: dict[str, float] = {}

    for match in ranked:
        lid = match["license_id"]
        if not lid.endswith("-only"):
            continue
        base = lid[: -len("-only")]
        peer = base + "-or-later"
        if peer not in id_to_score:
            continue

        # Rounded so a gap of exactly TIE_WINDOW is not decided by the
        # last bit of a float (0.91 - 0.90 is not 0.01; 0.35 - 0.34 is).
        if round(abs(match["score"] - id_to_score[peer]), 9) >= TIE_WINDOW:
            continue  # not a genuine tie — trust the similarity score

        delta = TIE_NUDGE
        if or_later_signal:
            adjustments[base + "-or-later"] = delta
            adjustments[base + "-only"] = -delta
        else:
            adjustments[base + "-only"] = delta
            adjustments[base + "-or-later"] = -delta

    if adjustments:
        for match in ranked:
            adj = adjustments.get(match["license_id"], 0.0)
            if adj:
                match["score"] += adj

        ranked.sort(key=ranking_key(enable_pop))

    return ranked

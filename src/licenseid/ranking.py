# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Ordering of ranked candidates: the one sort key, and the -only / -or-later
tie-breaker that runs after ranking."""

import functools
from collections.abc import Callable, Collection, Iterable

from licenseid.grantsubject import (
    NO_GRANT,
    Grant,
    GrantSignal,
    grants,
    has_unowned_phrase,
    lazy_signal,
    onlys,
)
from licenseid.listlookup import fold_case
from licenseid.plusoperator import grant_stem
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


@functools.lru_cache(maxsize=2)
def _grants_of(text: str) -> tuple[Grant, ...]:
    """:func:`licenseid.grantsubject.grants` of *text*, kept for the second
    reader of the same input (the tie-breaker, then the variant settling)."""
    return tuple(grants(text))


@functools.lru_cache(maxsize=2)
def _unowned_in(text: str) -> bool:
    return has_unowned_phrase(text)


@functools.lru_cache(maxsize=2)
def _onlys_of(text: str) -> tuple[Grant, ...]:
    return tuple(onlys(text))


def or_later_signal(raw_text: str, is_pure: bool) -> GrantSignal:
    """Whether the input grants the later versions of a licence: the one signal
    that chooses ``-or-later`` over ``-only``, for a tie
    (:func:`apply_version_suffix_tiebreaker`) and for ``variant_stated``
    (licenseid.variants). Asked per licence ID, as a grant is the licence's
    it names (:mod:`licenseid.grantsubject`: ``Python 3.8 or later`` grants
    none), and read at the first question. A pure licence text has none (its
    body is identical for both, and the GPL's "How to Apply" appendix holds
    the phrase), so it is never read for one."""
    if is_pure:
        return NO_GRANT
    return lazy_signal(lambda: _grants_of(raw_text))


def leave_signal(raw_text: str, is_pure: bool) -> Callable[[], bool]:
    """Whether ``licenseid.variants`` leaves an ``-or-later`` answer alone: the
    input holds a later-version phrase no subject owns
    (:func:`licenseid.grantsubject.has_unowned_phrase`), so the licence's own
    grant may be one the subject rule cannot read, read at the first question;
    or it is a pure licence text, never read for a grant."""
    if is_pure:
        return lambda: True
    return lambda: _unowned_in(raw_text)


def only_signal(raw_text: str, is_pure: bool) -> GrantSignal:
    """Whether the input states "only" after a version number of a licence
    (``licenseid.variants``: that states ``-only``, no guess), asked per
    licence ID like :func:`or_later_signal`. A pure licence text is never read
    for one."""
    if is_pure:
        return NO_GRANT
    return lazy_signal(lambda: _onlys_of(raw_text))


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
      A later-version phrase no subject owns (a cut text, ``or any version
      later``) counts as granting language, as it always did.
    """
    signal = or_later_signal(raw_text, is_pure)  # asked per pair, read once

    id_to_score = {r["license_id"]: r["score"] for r in ranked}
    adjustments: dict[str, float] = {}

    for match in ranked:
        lid = match["license_id"]
        if not lid.endswith("-only"):
            continue
        base = grant_stem(lid)
        peer = base + "-or-later"
        if peer not in id_to_score:
            continue

        # Rounded so a gap of exactly TIE_WINDOW is not decided by the
        # last bit of a float (0.91 - 0.90 is not 0.01; 0.35 - 0.34 is).
        if round(abs(match["score"] - id_to_score[peer]), 9) >= TIE_WINDOW:
            continue  # not a genuine tie — trust the similarity score

        delta = TIE_NUDGE
        if signal(peer) or (not is_pure and _unowned_in(raw_text)):
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


def under_found(
    ranked: list[InternalMatch],
    group: Collection[str],
    runner_ups: Collection[str],
    named: Iterable[str] = (),
) -> list[InternalMatch]:
    """*ranked* without the runner-ups (*runner_ups*, the IDs Tier 2 scored
    beside a text found whole) that nothing names: the input holds the text
    of the same-text group *group* whole, so a look-alike of it is no second
    answer (roadmap items 13 and 68: ``Pixar`` at 0.99 under a verbatim
    Apache-2.0 file).

    A runner-up that the input or the caller names (*named*: the IDs of the
    markers and of ``hint``, either twin of one and both of a bare deprecated
    ID, by :func:`licenseid.plusoperator.grant_stem`) is a candidate in its
    own right: it stays where it scores under the best of *group*, as every
    runner-up did in 0.10.0, so the later steps read the rows they read then
    (the tie-breaker, the twins ``licenseid.variants`` fills a bare ID from).
    A candidate that is no runner-up stays. Unchanged when no member of
    *group* is ranked."""
    best = max((m["score"] for m in ranked if m["license_id"] in group), default=None)
    if best is None:
        return ranked
    stems = {fold_case(grant_stem(license_id)) for license_id in named}

    def stays(match: InternalMatch) -> bool:
        license_id = match["license_id"]
        if license_id not in runner_ups:
            return True
        return fold_case(grant_stem(license_id)) in stems and match["score"] < best

    return [match for match in ranked if stays(match)]

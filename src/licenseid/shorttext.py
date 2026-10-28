# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 0 for inputs of a few words: exact and fuzzy matching of a bare
license ID or name."""

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.looseid import loose_id, narrowed, resolved_id, warn_narrowed
from licenseid.plusoperator import strip_plus_operator
from licenseid.ranking import DEP_PENALTY
from licenseid.types import LicenseNameId, RawMatch
from licenseid.versionkey import version_key

# The score of an exact ID or name match; a fuzzy one scores less.
EXACT_MATCH_SCORE = 1.02


def exact_id_match(license_id: str) -> RawMatch:
    """A result found by its ID: certain, with nothing measured. The caller
    adds the flags."""
    return RawMatch(
        license_id=license_id,
        method="id",
        exact=True,
        score=EXACT_MATCH_SCORE,
        similarity=None,
        coverage=None,
    )


def match_version_key(db: LicenseDatabase, text: str) -> list[RawMatch]:
    """The license *text* names loosely (see licenseid.looseid), as an ID
    match: "Apache2" is Apache-2.0."""
    found = loose_id(db, text)
    if found is None:
        return []
    # loose_id reads the narrow row of ListLookup; the flags are in the full one.
    row = _full_row(db, found[0]["license_id"])
    return [] if row is None else [_id_hit(row, found[1], text)]


def _full_row(db: LicenseDatabase, license_id: str) -> LicenseNameId | None:
    """The row of *license_id* from the cached rows by version key."""
    rows = db.get_names_by_key(version_key).get(version_key(license_id), [])
    return next((row for row in rows if row["license_id"] == license_id), None)


def match_short_text(
    db: LicenseDatabase, norm_input: str, text: str | None = None
) -> list[RawMatch]:
    """Tier 0 for very short inputs: the ID of the version key of *text* (the
    raw input; *norm_input* when not given, which has lost its full stops),
    else an exact or fuzzy ID or name match on *norm_input*."""
    raw = norm_input if text is None else text
    loose = match_version_key(db, raw)
    if loose:
        return loose
    all_metadata = db.get_all_names_and_ids()
    # Case-fold exact ID match: a score > 1.0, so the Tier 0 caller
    # recognises it as a definitive hit.
    exact = _exact_id_row(all_metadata, norm_input, raw)
    if exact is not None:
        return [_id_hit(exact, resolved_id(db, exact), raw)]
    ranked: list[RawMatch] = []
    words = norm_input.split()
    threshold = 90.0 if len(words) <= 2 else 85.0
    # The names of rows in use: a deprecated row that shares one is not the
    # exact answer, the row that replaced it is.
    live_names = {m["norm_name"] for m in all_metadata if not m["is_deprecated"]}

    for meta in all_metadata:
        lid = meta["license_id"]
        id_norm = meta["norm_license_id"]
        name_norm = meta["norm_name"]

        if norm_input == name_norm:
            # Exact name match: id_norm was already ruled out above, so
            # the RapidFuzz scores are known without computing them.
            score_id = 0.0
            score_id_partial = 0.0
            score_name_exact = 100.0
            score_name_flex = 100.0
        else:
            # A score under the threshold is dropped below, so the cutoff
            # changes no result; it lets RapidFuzz stop early, where a long
            # word against every row cost seconds (roadmap item 27).
            score_id = fuzz.ratio(norm_input, id_norm, score_cutoff=threshold)
            score_id_partial = (
                fuzz.partial_ratio(norm_input, id_norm, score_cutoff=threshold)
                if len(words) == 1
                else 0
            )
            score_name_exact = fuzz.ratio(norm_input, name_norm, score_cutoff=threshold)
            score_name_flex = fuzz.token_set_ratio(
                norm_input, name_norm, score_cutoff=threshold
            )

        best_raw = max(score_id, score_name_exact, score_name_flex, score_id_partial)
        if best_raw >= threshold:
            score = best_raw / 100.0
            # Boost exact name matches more than flex matches. (An exact ID
            # returned above: fuzz.ratio is 100 only for equal strings.)
            if score_name_exact == 100:
                score += 0.02
            elif score_name_flex == 100:
                score += 0.01
            # Penalise deprecated aliases so the canonical replacement wins
            # when scores are otherwise tied or close.
            if meta["is_deprecated"]:
                score -= DEP_PENALTY

            # A name match measures how alike the names are, not how much of
            # a license text the input covers.
            match = RawMatch(
                license_id=lid,
                method="name",
                exact=score_name_exact == 100
                and not (meta["is_deprecated"] and name_norm in live_names),
                score=score,
                similarity=best_raw / 100.0,
                coverage=None,
            )
            _copy_flags(meta, match)
            ranked.append(match)

    # The deprecated penalty is already in each score, and these results
    # carry no is_deprecated or pop_score.
    ranked.sort(key=lambda x: (-x["score"], x["license_id"]))
    return ranked


def _exact_id_row(
    rows: list[LicenseNameId], norm_input: str, text: str
) -> LicenseNameId | None:
    """The row whose normalised ID is *norm_input*, ASCII case folded.
    normalize_text() drops a "+", so GPL-2.0 and GPL-2.0+ share one: a row
    with a "+" answers a *text* with the "+" operator (as identifiers reads
    it: "GPL 2 0 +" has none), and only such a row does, or the "+" would be
    dropped in silence ("GPL-2.0-only+" is no GPL-2.0-only). (The version
    key, asked first, already chose between a row in use and a deprecated
    one.)"""
    norm_upper = norm_input.upper()
    plus = strip_plus_operator(text) != text
    found = [
        row
        for row in rows
        if row["norm_license_id"].upper() == norm_upper
        and row["license_id"].endswith("+") == plus
    ]
    return found[0] if found else None


def _id_hit(row: LicenseNameId, resolved: str, text: str) -> RawMatch:
    """An ID match on *row*, answering *resolved*. A deprecated ID narrowed
    to -only that *text* did not state ("GPL3", "GPL 2 0") is a guess: the
    narrower grant is the safer one, and a guess is not exact, nor silent."""
    match = exact_id_match(resolved)
    if resolved == row["license_id"]:
        _copy_flags(row, match)
    # A deprecated ID can resolve to an expression, whose flags are not this
    # row's: the caller works them out.
    if narrowed(row["license_id"], resolved, text):
        match["exact"] = False
        warn_narrowed(text, resolved)
    return match


def _copy_flags(meta: LicenseNameId, match: RawMatch) -> None:
    """Give *match* the SPDX, OSI and FSF flags of its license row."""
    match["is_spdx"] = meta["is_spdx"]
    match["is_osi_approved"] = meta["is_osi_approved"]
    match["is_fsf_libre"] = meta["is_fsf_libre"]

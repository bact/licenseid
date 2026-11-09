# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 0 for inputs of a few words: exact and fuzzy matching of a bare
license ID or name."""

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.looseid import loose_id, narrowed, resolved_id, warn_narrowed
from licenseid.plusoperator import grant_stem, strip_plus_operator
from licenseid.ranking import DEP_PENALTY
from licenseid.types import LicenseNameId, RawMatch
from licenseid.versionkey import version_key

# The score of an exact ID or name match; a fuzzy one scores less.
EXACT_MATCH_SCORE = 1.02

# The words that end a List name with its grant, normalised.
_GRANT_WORDS = (" only", " or later")


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
    """The row of *license_id* from the cached rows by version key. The
    ``None`` fallback can only fire when the table cache is rebuilt between
    the two reads (another process's ``update``)."""
    rows = db.get_names_by_key(version_key).get(version_key(license_id), [])
    return next((row for row in rows if row["license_id"] == license_id), None)


def match_short_text(
    db: LicenseDatabase,
    norm_input: str,
    text: str | None = None,
    *,
    ids: bool = True,
) -> list[RawMatch]:
    """Tier 0 for very short inputs: the ID of the version key of *text* (the
    raw input; *norm_input* when not given, which has lost its full stops),
    else an exact or fuzzy ID or name match on *norm_input*. Not the IDs if
    not *ids*: a value ``resolve()`` refused is no ID, and the normalised
    text has lost the marks it refused it for."""
    raw = norm_input if text is None else text
    if ids:
        loose = match_version_key(db, raw)
        if loose:
            return loose
    all_metadata = db.get_all_names_and_ids()
    # Case-fold exact ID match: a score > 1.0, so the Tier 0 caller
    # recognises it as a definitive hit.
    exact = _exact_id_row(all_metadata, norm_input, raw) if ids else None
    if exact is not None:
        return [_id_hit(exact, resolved_id(db, exact), raw)]
    ranked: list[RawMatch] = []
    words = norm_input.split()
    threshold = 90.0 if len(words) <= 2 else 85.0
    # The names of rows in use: a deprecated row that shares one is not the
    # exact answer, the row that replaced it is.
    live_names = {m["norm_name"] for m in all_metadata if not m["is_deprecated"]}
    stems = _grant_left_out(all_metadata, set(words))
    partial = _partial_names(all_metadata, words, stems)

    for meta in all_metadata:
        name_norm = meta["norm_name"]
        score_id, score_id_partial, score_name_exact, score_name_flex = _name_scores(
            norm_input, meta, threshold, len(words) == 1, partial
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
                license_id=meta["license_id"],
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
    if narrowed_name(ranked) is not None and not _grant_left_out_alone(
        ranked, stems, raw
    ):
        return []  # both grants tie, and the input is no name without its grant
    return ranked


def _name_scores(
    norm_input: str,
    meta: LicenseNameId,
    threshold: float,
    one_word: bool,
    partial: set[str],
) -> tuple[float, float, float, float]:
    """The ID, partial ID (*one_word* only), exact name and flex name scores
    of *norm_input* against *meta*, 0 to 100; 0 below *threshold*."""
    name_norm = meta["norm_name"]
    if norm_input == name_norm:
        # Exact name match: an exact ID was already ruled out, so the
        # RapidFuzz scores are known without computing them.
        return 0.0, 0.0, 100.0, 100.0
    # A score under the threshold is dropped by the caller, so the cutoff
    # changes no result; it lets RapidFuzz stop early, where a long word
    # against every row cost seconds (roadmap item 27).
    id_norm = meta["norm_license_id"]
    score_id_partial = (
        fuzz.partial_ratio(norm_input, id_norm, score_cutoff=threshold)
        if one_word
        else 0.0
    )
    # Token set: the same words in any order, or a name with words left
    # out. A name that only holds the input's words is not the input's name
    # (_partial_names): the plain ratio judges it.
    score_name_flex = (
        0.0
        if name_norm in partial
        else fuzz.token_set_ratio(norm_input, name_norm, score_cutoff=threshold)
    )
    return (
        fuzz.ratio(norm_input, id_norm, score_cutoff=threshold),
        score_id_partial,
        fuzz.ratio(norm_input, name_norm, score_cutoff=threshold),
        score_name_flex,
    )


def _partial_names(
    rows: list[LicenseNameId], words: list[str], stems: set[str]
) -> set[str]:
    """The names that hold every one of *words* and more, unless they name
    one licence: the words are no name in use, only one name holds them,
    and they are at least half its words ("GNU Public License v2.0 only").
    Token set scores such a name 100, as if it were the input: "the" is in
    six names, "license" in most, "GNU General Public License" in every
    GPL (22 names), and "MIT License" in six besides MIT's own. The
    words of a deprecated name of its own ("GNU Affero General Public
    License v3.0") are held by the names that replaced it (its -only and
    -or-later): those are kept, as before. So are the names of the
    licences of *stems* (_grant_left_out), whose name the words are without
    its grant, and only those: GPL-2.0-with-GCC-exception also holds "GNU
    General Public License v2.0", and the GFDL-1.3 names with invariants
    hold "GNU Free Documentation License v1.3", the name of the deprecated
    GFDL-1.3."""
    query = set(words)
    pairs = [(row, set(row["norm_name"].split())) for row in rows]
    named = {bool(row["is_deprecated"]) for row, name in pairs if name == query}
    held = [row for row, name in pairs if query < name]
    # More than one licence of *stems* gets no answer (_grant_left_out_alone).
    if False not in named and stems:
        return {
            row["norm_name"]
            for row in held
            if grant_stem(row["license_id"]) not in stems
        }
    if named == {True}:
        return set()  # a deprecated name, and no name in use
    holders = {row["norm_name"] for row in held}
    if (
        len(holders) == 1
        and not named
        and 2 * len(query) >= len(set(next(iter(holders)).split()))
    ):
        return set()
    return holders


def _grant_left_out(rows: list[LicenseNameId], query: set[str]) -> set[str]:
    """The licences (plusoperator.grant_stem) that have both an -only and an
    -or-later row in use whose name is the words of *query* and its grant:
    "GNU General Public License v2.0" is GPL-2.0-only's name without
    "only", and GPL-2.0-or-later's without "or later". Every other word
    must be there ("GNU Affero General Public License" states no version),
    and both grants, or the guess could not be the narrower."""
    grants: dict[str, set[str]] = {}
    for row in rows:
        name = row["norm_name"]
        stem = grant_stem(row["license_id"])
        if row["is_deprecated"] or stem == row["license_id"]:
            continue
        for grant in _GRANT_WORDS:
            if name.endswith(grant) and set(name[: -len(grant)].split()) == query:
                grants.setdefault(stem, set()).add(grant)
    return {stem for stem, found in grants.items() if len(found) == len(_GRANT_WORDS)}


def _grant_left_out_alone(ranked: list[RawMatch], stems: set[str], text: str) -> bool:
    """Whether *ranked*, whose first two results are one licence's -only and
    -or-later tied, may stand: *text* is the name of the one licence of
    *stems* without its grant, it has no "+" (normalize_text dropped it,
    and "v2.0+" states the wider grant), and no third result ties. An
    input that holds both names ("v2.0 or later only") is none."""
    first, third = ranked[0], ranked[2] if len(ranked) > 2 else None
    alone = third is None or third["score"] < first["score"]
    return len(stems) == 1 and "+" not in text and alone


def narrowed_name(found: list[RawMatch]) -> str | None:
    """The -only ID *found* answers for a name that states no grant: its
    first two results tie, found by name and neither exact, and are one
    licence's -only and -or-later ("GNU General Public License v2.0").
    Sorted by ID, the narrower comes first. None for any other *found*."""
    if len(found) < 2:
        return None
    first, second = found[0], found[1]
    license_id = first["license_id"]
    paired = second["license_id"] == f"{grant_stem(license_id)}-or-later"
    if not (license_id.endswith("-only") and paired):
        return None
    tied = first["score"] == second["score"]
    by_name = {first["method"], second["method"]} == {"name"}
    guessed = not (first["exact"] or second["exact"])
    return license_id if tied and by_name and guessed else None


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
    to -only ("GPL3", "GPL 2 0", "GPL-2.0" itself) is a guess: the narrower
    grant is the safer one, and a guess is not exact, nor silent."""
    match = exact_id_match(resolved)
    if resolved == row["license_id"]:
        _copy_flags(row, match)
    # A deprecated ID can resolve to an expression, whose flags are not this
    # row's: the caller works them out.
    if narrowed(row["license_id"], resolved):
        match["exact"] = False
        warn_narrowed(text, resolved)
    return match


def _copy_flags(meta: LicenseNameId, match: RawMatch) -> None:
    """Give *match* the SPDX, OSI and FSF flags of its license row."""
    match["is_spdx"] = meta["is_spdx"]
    match["is_osi_approved"] = meta["is_osi_approved"]
    match["is_fsf_libre"] = meta["is_fsf_libre"]

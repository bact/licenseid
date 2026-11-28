# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 0 for inputs of a few words: exact and fuzzy matching of a bare
license ID or name."""

from rapidfuzz import fuzz, process

from licenseid.database import LicenseDatabase, exception_words
from licenseid.exprflags import judged_id
from licenseid.looseid import loose_id, mark_guessed, resolved_id
from licenseid.namehits import NameHits, settle
from licenseid.plusoperator import grant_stem, strip_plus_operator
from licenseid.ranking import DEP_PENALTY
from licenseid.resolvereason import ends_a_word_with_plus
from licenseid.types import LicenseNameId, RawMatch
from licenseid.variants import decided, read_from
from licenseid.versionkey import version_key

# The score of an exact ID or name match; a fuzzy one scores less.
EXACT_MATCH_SCORE = 1.02

# The native scorers of :func:`_rows_at_threshold`, kept as they are:
# ``process.extract`` runs only a RapidFuzz scorer in C.
_RATIO, _PARTIAL, _TOKEN_SET = fuzz.ratio, fuzz.partial_ratio, fuzz.token_set_ratio

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
    return [] if row is None else [_id_hit(db, row, found[1], text)]


def _full_row(db: LicenseDatabase, license_id: str) -> LicenseNameId | None:
    """The row of *license_id* from the cached rows by version key. The
    ``None`` fallback can only fire when the table cache is rebuilt between
    the two reads (another process's ``update``)."""
    rows = db.get_names_by_key(version_key).get(version_key(license_id), [])
    return next((row for row in rows if row["license_id"] == license_id), None)


def match_short_text(
    db: LicenseDatabase, norm_input: str, text: str | None = None
) -> list[RawMatch]:
    """The hits of :func:`match_name_tier`: for a caller that has no use for
    its refusal (the sections of a mixed text, which Tier 1 reads next)."""
    return match_name_tier(db, norm_input, text).found


def match_name_tier(
    db: LicenseDatabase, norm_input: str, text: str | None = None
) -> NameHits:
    """Tier 0 for very short inputs: the ID of the version key of *text* (the
    raw input; *norm_input* when not given, which has lost its full stops),
    else an exact or fuzzy ID or name match on *norm_input*. A name hit that
    a rule of :mod:`licenseid.namehits` doubts is dropped; ``refused`` says
    that the hit would have answered."""
    raw = norm_input if text is None else text
    loose = match_version_key(db, raw)
    if loose:
        return NameHits(loose, False)
    all_metadata = db.get_all_names_and_ids()
    # Case-fold exact ID match: a score > 1.0, so the Tier 0 caller
    # recognises it as a definitive hit.
    exact = _exact_id_row(all_metadata, norm_input, raw)
    if exact is not None:
        return NameHits([_id_hit(db, exact, resolved_id(db, exact), raw)], False)
    words = norm_input.split()
    ranked, stems = _ranked_names(db, all_metadata, norm_input, words)
    if decided_name(ranked) is not None and not _grant_left_out_alone(
        ranked, stems, raw
    ):
        return NameHits([], False)  # both grants tie, the input has no grant
    return settle(ranked, all_metadata, words, raw, lambda: exception_words(db))


def _ranked_names(
    db: LicenseDatabase,
    all_metadata: list[LicenseNameId],
    norm_input: str,
    words: list[str],
) -> tuple[list[RawMatch], set[str]]:
    """The name and ID hits of *norm_input* (its *words*) at or above the
    threshold, best first, and the licences whose name it is without their
    grant (:func:`_grant_left_out`)."""
    ranked: list[RawMatch] = []
    threshold = 90.0 if len(words) <= 2 else 85.0
    # The names of rows in use: a deprecated row that shares one is not the
    # exact answer, the row that replaced it is.
    live_names = {m["norm_name"] for m in all_metadata if not m["is_deprecated"]}
    stems = _grant_left_out(all_metadata, set(words))
    partial = _partial_names(all_metadata, words, stems)

    for index in _rows_at_threshold(all_metadata, norm_input, threshold, len(words)):
        meta = all_metadata[index]
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
            _copy_flags(db, meta, match)
            ranked.append(match)

    # The deprecated penalty is already in each score, and these results
    # carry no is_deprecated or pop_score.
    ranked.sort(key=lambda x: (-x["score"], x["license_id"]))
    return ranked, stems


def _rows_at_threshold(
    rows: list[LicenseNameId], norm_input: str, threshold: float, word_count: int
) -> list[int]:
    """The positions in *rows*, in order, of every row that any score of
    :func:`_name_scores` can lift to *threshold* or more: ID, name and token
    set against the name, and for one word the partial ID. RapidFuzz drops
    the rest in one native pass, so the Python loop of :func:`_ranked_names`
    scores a handful of rows, not the List. Cut at the *threshold* itself, as
    the loop is: a bonus is added only to a score at or above it, so a row
    under it is never kept by one. A superset of the rows the loop keeps (the
    token set of a name that :func:`_partial_names` set aside is 0 there)."""
    ids = [row["norm_license_id"] for row in rows]
    names = [row["norm_name"] for row in rows]
    scored = [(_RATIO, ids), (_RATIO, names), (_TOKEN_SET, names)]
    if word_count == 1:
        scored.append((_PARTIAL, ids))
    found: set[int] = set()
    for scorer, choices in scored:
        found.update(
            index
            for _, _, index in process.extract(
                norm_input,
                choices,
                scorer=scorer,
                processor=None,
                score_cutoff=threshold,
                limit=None,
            )
        )
    return sorted(found)


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
    -or-later): those are kept. So are the names of the
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
    and both grants, or the guess could not be the one decided."""
    grants: dict[str, set[str]] = {}
    for row in rows:
        name = row["norm_name"]
        stem = grant_stem(row["license_id"])
        if row["is_deprecated"] or stem == row["license_id"]:
            continue
        for grant in _GRANT_WORDS:
            if name.endswith(grant) and query in _spellings(name[: -len(grant)]):
                grants.setdefault(stem, set()).add(grant)
    return {stem for stem, found in grants.items() if len(found) == len(_GRANT_WORDS)}


def _spellings(name: str) -> list[set[str]]:
    """The word sets that state *name* (a List name without its grant): its
    words, and without a last "0" after "vN", where "GNU General Public
    License v3" is "v3.0" (the rule PR #168 set for "v2.0")."""
    words = name.split()
    spelled = [set(words)]
    if len(words) > 1 and words[-1] == "0" and _is_v_number(words[-2]):
        spelled.append(set(words[:-1]))
    return spelled


def _is_v_number(word: str) -> bool:
    """Whether *word* is "v" and digits (``v3``)."""
    return word.startswith("v") and word[1:].isdigit()


def _grant_left_out_alone(ranked: list[RawMatch], stems: set[str], text: str) -> bool:
    """Whether *ranked*, whose first two results are one licence's -only and
    -or-later tied, may stand: *text* is the name of the one licence of
    *stems* without its grant, it has no "+" (normalize_text dropped it,
    and "v2.0+" states the wider grant) nor a stray one ("v2.0 ＋",
    ``resolvereason.ends_a_word_with_plus``: the sections of a mixed text
    reach here without ``refuses_text_match``), and no third result ties. An
    input that holds both names ("v2.0 or later only") is none."""
    first, third = ranked[0], ranked[2] if len(ranked) > 2 else None
    alone = third is None or third["score"] < first["score"]
    plus = "+" in text or ends_a_word_with_plus(text)
    return len(stems) == 1 and not plus and alone


def decided_name(found: list[RawMatch]) -> str | None:
    """The -only ID *found* answers for a name that states no grant: its
    first two results tie, found by name and neither exact, and are one
    licence's -only and -or-later ("GNU General Public License v2.0").
    Sorted by ID, the -only one comes first. None for any other *found*."""
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


def _id_hit(
    db: LicenseDatabase, row: LicenseNameId, resolved: str, text: str
) -> RawMatch:
    """An ID match on *row*, answering *resolved*. A deprecated ID whose
    variant the option decided ("GPL3", "GPL 2 0", "GPL-2.0" itself read
    ``-only`` or ``-or-later``) is a guess: not exact, nor silent."""
    match = read_from([exact_id_match(resolved)], text)[0]
    if resolved == row["license_id"]:
        _copy_flags(db, row, match)
    # A deprecated ID can resolve to an expression, whose flags are not this
    # row's: the caller works them out.
    if decided(row["license_id"], resolved):
        match["exact"] = False
        mark_guessed(match, text)
    return match


def _copy_flags(db: LicenseDatabase, meta: LicenseNameId, match: RawMatch) -> None:
    """Give *match* the SPDX flag of its license row, and the OSI and FSF
    flags of its judged row: a kept deprecated ID is judged by its ``-only``
    twin, as in every other channel (:func:`licenseid.exprflags.judged_id`;
    ``AGPL-1.0`` is FSF-libre, its twins are not)."""
    twin = judged_id(meta["license_id"])
    judged = _full_row(db, twin) if twin != meta["license_id"] else None
    flags = judged or meta
    match["is_spdx"] = meta["is_spdx"]
    match["is_osi_approved"] = flags["is_osi_approved"]
    match["is_fsf_libre"] = flags["is_fsf_libre"]

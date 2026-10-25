# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 0 for inputs of a few words: exact and fuzzy matching of a bare
license ID or name."""

import functools
import re

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier
from licenseid.normalize import normalize_text
from licenseid.ranking import DEP_PENALTY
from licenseid.types import LicenseNameId, RawMatch

# The score of an exact ID or name match; a fuzzy one scores less.
EXACT_MATCH_SCORE = 1.02

# "v" directly before a digit is a version prefix: "GPLv3", "v2.0".
_RE_VERSION_PREFIX = re.compile(r"v(?=\d)", re.IGNORECASE)
# A boundary between a letter and a digit: "Apache2", "0BSD".
_RE_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
# A whole version number whose every part after the major is 0: "2.0" and
# "2.0.0", not "1.2.0", "2.0.1" or "2.00". The lookarounds keep it to the
# whole number; a full stop after it ends a sentence.
_RE_ZERO_VERSION = re.compile(r"(?<![\d.])(\d+)(?:\.0){1,2}(?!\.?\d)")


def version_key(text: str) -> str:
    """*text* as a version-tolerant ID: "Apache2", "apache 2" and
    "Apache-2.0" all give "apache 2", and "CC by 3 nl" gives the key of
    CC-BY-3.0-NL.

    Order matters: the prefix goes before the split, or "GPLv3" would become
    "gplv 3"; the split goes before the fold, or "Apache2.0" would keep its
    ".0"; the fold reads the full stops normalize_text() drops ("2.0" and
    "2 0" differ); a "+" becomes the "or later" it means before
    normalize_text() drops it, or GPL-2.0+ and GPL-2.0 would share a key.
    normalize_text() then folds case, dashes and punctuation as for an ID.
    """
    text = _RE_VERSION_PREFIX.sub(" ", text)
    text = _RE_LETTER_DIGIT.sub(" ", text)
    text = _RE_ZERO_VERSION.sub(r"\1", text)
    return normalize_text(text.replace("+", " or later "))


# The keys of the License List's IDs, which change only with a release.
_id_version_key = functools.lru_cache(maxsize=4096)(version_key)


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
    """The one license whose ID has the version key of *text* (see
    version_key), as an exact ID match: "Apache2" is Apache-2.0.

    A row in use wins over a deprecated one of the same key ("GPL2+" is
    GPL-2.0-or-later, not GPL-2.0+); two rows in use are no answer.
    """
    key = version_key(text)
    rows = [
        meta
        for meta in db.get_all_names_and_ids()
        if _id_version_key(meta["license_id"]) == key
    ]
    rows = [meta for meta in rows if not meta["is_deprecated"]] or rows
    if len(rows) != 1:
        return []
    return [_id_hit(db, rows[0])]


def match_short_text(db: LicenseDatabase, norm_input: str) -> list[RawMatch]:
    """Fallback logic for very short inputs."""
    all_metadata = db.get_all_names_and_ids()
    ranked: list[RawMatch] = []
    words = norm_input.split()
    threshold = 90.0 if len(words) <= 2 else 85.0
    norm_upper = norm_input.upper()
    # The names of rows in use: a deprecated row that shares one is not the
    # exact answer, the row that replaced it is.
    live_names = {m["norm_name"] for m in all_metadata if not m["is_deprecated"]}

    for meta in all_metadata:
        lid = meta["license_id"]
        id_norm = meta["norm_license_id"]
        name_norm = meta["norm_name"]

        # Case-fold exact ID match: return immediately with a score > 1.0
        # so the Tier 0 caller recognises it as a definitive hit.
        if id_norm.upper() == norm_upper:
            return [_id_hit(db, meta)]

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


def _id_hit(db: LicenseDatabase, meta: LicenseNameId) -> RawMatch:
    """An exact ID match on the row *meta*. A deprecated ID goes through
    normalize_identifier() for the same canonical-successor redirect the
    license_id= path already gets."""
    lid = meta["license_id"]
    resolved_id = normalize_identifier(lid, db) if meta["is_deprecated"] else lid
    match = exact_id_match(resolved_id)
    if resolved_id == lid:
        _copy_flags(meta, match)
    # A deprecated ID can resolve to an expression, whose flags are not this
    # row's: the caller works them out.
    return match


def _copy_flags(meta: LicenseNameId, match: RawMatch) -> None:
    """Give *match* the SPDX, OSI and FSF flags of its license row."""
    match["is_spdx"] = meta["is_spdx"]
    match["is_osi_approved"] = meta["is_osi_approved"]
    match["is_fsf_libre"] = meta["is_fsf_libre"]

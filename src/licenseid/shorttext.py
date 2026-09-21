# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 0 for inputs of a few words: exact and fuzzy matching of a bare
license ID or name."""

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier
from licenseid.ranking import DEP_PENALTY
from licenseid.types import LicenseMatch


def match_short_text(db: LicenseDatabase, norm_input: str) -> list[LicenseMatch]:
    """Fallback logic for very short inputs."""
    all_metadata = db.get_all_names_and_ids()
    ranked: list[LicenseMatch] = []
    words = norm_input.split()
    threshold = 90.0 if len(words) <= 2 else 85.0
    norm_upper = norm_input.upper()

    for meta in all_metadata:
        lid = meta["license_id"]
        id_norm = meta["norm_license_id"]
        name_norm = meta["norm_name"]

        # Case-fold exact ID match: return immediately with a score > 1.0
        # so the Tier 0 caller recognises it as a definitive hit.
        # Deprecated IDs go through normalize_identifier() for the same
        # canonical-successor redirect the license_id= path already gets.
        if id_norm.upper() == norm_upper:
            resolved_id = (
                normalize_identifier(lid, db) if meta["is_deprecated"] else lid
            )
            return [
                LicenseMatch(
                    license_id=resolved_id,
                    score=1.02,
                    similarity=1.0,
                    coverage=1.0,
                )
            ]

        if norm_input == name_norm:
            # Exact name match: id_norm was already ruled out above, so
            # the RapidFuzz scores are known without computing them.
            score_id = 0.0
            score_id_partial = 0.0
            score_name_exact = 100.0
            score_name_flex = 100.0
        else:
            score_id = fuzz.ratio(norm_input, id_norm)
            score_id_partial = (
                fuzz.partial_ratio(norm_input, id_norm) if len(words) == 1 else 0
            )
            score_name_exact = fuzz.ratio(norm_input, name_norm)
            score_name_flex = fuzz.token_set_ratio(norm_input, name_norm)

        best_raw = max(score_id, score_name_exact, score_name_flex, score_id_partial)
        if best_raw >= threshold:
            score = best_raw / 100.0
            # Boost exact matches for names and IDs more than flex matches
            if score_name_exact == 100 or score_id == 100:
                score += 0.02
            elif score_name_flex == 100:
                score += 0.01
            # Penalise deprecated aliases so the canonical replacement wins
            # when scores are otherwise tied or close.
            if meta["is_deprecated"]:
                score -= DEP_PENALTY

            ranked.append(
                LicenseMatch(
                    license_id=lid,
                    score=score,
                    similarity=best_raw / 100.0,
                    coverage=0.0,
                )
            )

    # The deprecated penalty is already in each score, and these results
    # carry no is_deprecated or pop_score.
    ranked.sort(key=lambda x: (-x["score"], x["license_id"]))
    return ranked

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

import math
import os
import shutil
from typing import Any, Optional, cast

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text
from licenseid.types import (
    CandidateMatch,
    InternalMatch,
    LicenseDetails,
    LicenseMatch,
    MatchRequest,
)


class AggregatedLicenseMatcher:
    """
    Main matcher class that implements Tier 1 (FTS5), Tier 2 (RapidFuzz),
    and Tier 3 (Java) matching.
    """

    def __init__(
        self, db_path: str, enable_java: bool = False, enable_popularity: bool = False
    ):
        self.db = LicenseDatabase(db_path)
        self.enable_java = enable_java
        self.enable_popularity = enable_popularity
        self.jar_path = os.getenv("SPDX_TOOLS_JAR")
        self.has_java = shutil.which("java") is not None

    def match(
        self,
        text: Optional[str] = None,
        *,
        license_id: Optional[str] = None,
        file_path: Optional[str] = None,
        **options: Any,
    ) -> list[LicenseMatch]:
        """
        Identify license text and return ranked matches.
        Must provide exactly one of text, license_id, or file_path.
        """
        # 1. Explicit ID Lookup
        if license_id:
            details = self.db.get_license_details(license_id)
            if details:
                return [
                    LicenseMatch(
                        license_id=details["license_id"],
                        score=1.0,
                        similarity=1.0,
                        coverage=1.0,
                        is_spdx=details["is_spdx"],
                        is_osi_approved=details["is_osi_approved"],
                        is_fsf_libre=details["is_fsf_libre"],
                    )
                ]
            return []

        # 2. File Path
        target_text = ""
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                target_text = f.read()
        else:
            target_text = text or ""

        if not target_text:
            return []

        request = cast(MatchRequest, options)
        request["text"] = target_text

        norm_input = normalize_text(target_text)
        words = norm_input.split()

        # Tier 0: Short-Text Shortcut (Names/IDs)
        if len(words) < 20:
            short_matches = self._match_short_text(norm_input)
            if short_matches and short_matches[0]["score"] > 1.0:
                return short_matches

        # Tier 1: Broad Recall
        candidates = self._get_candidates(request, target_text)

        # Tier 2: Precision Ranking
        ranked = self._rank_candidates(candidates, norm_input, request)

        # Tier 3: Optional Java Consultant
        enable_java = request.get("enable_java", self.enable_java)
        if (
            enable_java
            and self.has_java
            and self.jar_path
            and os.path.exists(self.jar_path)
            and ranked
        ):
            return cast(list[LicenseMatch], self._consult_java(target_text, ranked))

        return cast(list[LicenseMatch], ranked)

    def _resolve_to_record(
        self,
        text: Optional[str] = None,
        *,
        license_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Optional[LicenseDetails]:
        """Internal helper to resolve explicit inputs to a database record."""
        results = self.match(text, license_id=license_id, file_path=file_path)
        if results and results[0]["score"] >= 0.85:
            return self.db.get_license_details(results[0]["license_id"])
        return None

    def is_spdx(self, text: Optional[str] = None, **kwargs: Any) -> bool:
        """True if the license is in the SPDX License List."""
        record = self._resolve_to_record(text, **kwargs)
        return record is not None and record.get("is_spdx", False)

    def is_osi(self, text: Optional[str] = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved."""
        record = self._resolve_to_record(text, **kwargs)
        return record is not None and record.get("is_osi_approved", False)

    def is_fsf(self, text: Optional[str] = None, **kwargs: Any) -> bool:
        """True if the license is FSF-libre."""
        record = self._resolve_to_record(text, **kwargs)
        return record is not None and record.get("is_fsf_libre", False)

    def is_open(self, text: Optional[str] = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved OR FSF-libre."""
        record = self._resolve_to_record(text, **kwargs)
        if not record:
            return False
        return bool(
            record.get("is_osi_approved", False) or record.get("is_fsf_libre", False)
        )

    def _get_candidates(self, data: MatchRequest, text: str) -> list[CandidateMatch]:
        """Fetch and filter candidates from the database."""
        only_spdx = data.get("only_spdx", True)
        only_common = data.get("only_common", False)
        exclude_list: list[str] = data.get("exclude", [])
        hint_list: list[str] = data.get("hint", [])

        # Tier 1: Retrieval
        # Truncate very long queries for FTS5 to avoid performance/limit issues
        # 100 words is more than enough for trigram retrieval.
        words = text.split()
        search_query = text
        if len(words) > 100:
            search_query = " ".join(words[:100])

        # Fetch Top 50 for better recall
        candidates = self.db.search_candidates(search_query, limit=50)
        filtered: list[CandidateMatch] = []
        for cand in candidates:
            license_id = cand["license_id"]
            if license_id in exclude_list:
                continue

            # Filtering logic using pre-fetched metadata
            if only_spdx and not cand["is_spdx"]:
                continue
            if only_common and not cand["is_high_usage"]:
                if not (cand["is_osi_approved"] or cand["is_fsf_libre"]):
                    continue

            filtered.append(cand)

        # Force-include hints
        candidate_ids = {c["license_id"] for c in filtered}
        for h_id in hint_list:
            if h_id not in candidate_ids:
                details = self.db.get_license_details(h_id)
                if details:
                    filtered.append(
                        CandidateMatch(
                            license_id=details["license_id"],
                            search_text="",
                            word_count=details["word_count"],
                            is_spdx=details["is_spdx"],
                            is_high_usage=details["is_high_usage"],
                            is_osi_approved=details["is_osi_approved"],
                            is_fsf_libre=details["is_fsf_libre"],
                            popularity_score=details["popularity_score"],
                        )
                    )
        return filtered

    # pylint: disable=too-many-branches
    def _rank_candidates(
        self, candidates: list[CandidateMatch], norm_input: str, data: MatchRequest
    ) -> list[InternalMatch]:
        """Rank candidates using dynamic sliding window and popularity boost."""
        enable_popularity = data.get("enable_popularity", self.enable_popularity)
        query_words = norm_input.split()
        q_len = len(query_words)
        ranked: list[InternalMatch] = []

        for cand in candidates:
            license_id = cand["license_id"]
            search_text = cand["search_text"] or ""
            c_len = cand["word_count"] or 0
            if c_len == 0:
                c_len = len(search_text.split())

            similarity = 0.0
            best_window = search_text

            if norm_input == search_text:
                similarity = 1.0
            elif q_len >= c_len * 0.8:
                # Rule 1: Full Text Comparison
                similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0
            else:
                # Rule 2: Surgical Window Alignment (for snippets)
                if q_len < 500:
                    fast_score = fuzz.partial_ratio(norm_input, search_text) / 100.0
                    if fast_score >= 0.6:
                        alignment = fuzz.partial_ratio_alignment(
                            norm_input, search_text
                        )
                        if alignment:
                            best_window = search_text[
                                alignment.dest_start : alignment.dest_end
                            ]
                            similarity = (
                                fuzz.token_sort_ratio(norm_input, best_window) / 100.0
                            )
                        else:
                            similarity = fast_score
                    else:
                        similarity = fast_score
                else:
                    # Large-to-large comparison fallback
                    similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0

            coverage = (q_len / c_len) if c_len > 0 else 0.0

            # Step C: Semantic Safeguards
            critical_tokens = {"not", "except", "unless", "irrevocable"}
            if 0.90 < similarity < 1.0:
                q_tokens = set(query_words)
                c_tokens = set(search_text.split())
                for token in critical_tokens:
                    if (token in q_tokens) != (token in c_tokens):
                        similarity *= 0.95

            ranked.append(
                InternalMatch(
                    license_id=license_id,
                    base_score=similarity,
                    similarity=similarity,
                    coverage=coverage,
                    pop_score=cand["popularity_score"],
                    best_window=best_window,
                    score=0.0,
                )
            )

        if ranked:
            # Composite scoring: Similarity is primary.
            # Coverage is a strong tie-breaker for similar texts.
            for r in ranked:
                similarity = r["base_score"]
                # Penalty for poor coverage: a license that is much larger than
                # the input is less likely to be the "exact" match than one of
                # similar size. However, we only apply this if similarity is
                # high (likely a match).
                coverage_penalty = 0.0
                if r["coverage"] < 0.8:
                    # Penalize based on how much of the candidate is "missing"
                    coverage_penalty = (1.0 - r["coverage"]) * 0.02

                # Bonus for near-perfect coverage
                coverage_bonus = 0.005 if 0.95 <= r["coverage"] <= 1.05 else 0.0

                score = similarity - coverage_penalty + coverage_bonus

                if enable_popularity:
                    score += math.log10(max(1, r["pop_score"])) * 0.0001

                r["score"] = score

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    def _ensure_jvm(self) -> None:
        """Ensure the JVM is started with the tools-java JAR."""
        try:
            import jpype  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError(
                "JPype1 is required for Java validation. "
                "Install it with 'pip install licenseid[java]'"
            ) from exc

        if not jpype.isJVMStarted():
            jpype.startJVM(classpath=[self.jar_path], convertStrings=False)
            model_factory = jpype.JClass("org.spdx.library.SpdxModelFactory")
            model_factory.init()

    def _consult_java(
        self, text: str, ranked: list[InternalMatch]
    ) -> list[InternalMatch]:
        """Consult the tools-java MatchingStandardLicenses logic via JPype."""
        try:
            import jpype  # pylint: disable=import-outside-toplevel
        except ImportError:
            return ranked

        print("  DEBUG: Consulting Java...")
        self._ensure_jvm()
        j_thread = jpype.JClass("java.lang.Thread")
        j_thread.attachAsDaemon()
        try:
            compare_helper = jpype.JClass(
                "org.spdx.utility.compare.LicenseCompareHelper"
            )
            java_matches_list = compare_helper.matchingStandardLicenseIdsWithinText(
                text
            )
            java_matches = {str(m) for m in java_matches_list}

            for r in ranked:
                if r["license_id"] in java_matches:
                    r["score"] = 1.0
                    r["java_verified"] = True
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        finally:
            j_thread.detach()

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    def _match_short_text(self, norm_input: str) -> list[LicenseMatch]:
        """Fallback logic for very short inputs."""
        all_metadata = self.db.get_all_names_and_ids()
        ranked: list[LicenseMatch] = []
        words = norm_input.split()
        threshold = 90.0 if len(words) <= 2 else 85.0

        for meta in all_metadata:
            lid = meta["license_id"]
            name = meta["name"]

            id_norm = normalize_text(lid)
            score_id = fuzz.ratio(norm_input, id_norm)
            score_id_partial = (
                fuzz.partial_ratio(norm_input, id_norm) if len(words) == 1 else 0
            )

            name_norm = normalize_text(name)
            score_name_exact = fuzz.ratio(norm_input, name_norm)
            score_name_flex = fuzz.token_set_ratio(norm_input, name_norm)

            best_raw = max(
                score_id, score_name_exact, score_name_flex, score_id_partial
            )
            if best_raw >= threshold:
                score = best_raw / 100.0
                # Boost exact matches for names and IDs more than flex matches
                if score_name_exact == 100 or score_id == 100:
                    score += 0.02
                elif score_name_flex == 100:
                    score += 0.01

                ranked.append(
                    LicenseMatch(
                        license_id=lid,
                        score=score,
                        similarity=best_raw / 100.0,
                        coverage=0.0,
                    )
                )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

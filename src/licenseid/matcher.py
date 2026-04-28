# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

import math
import os
import shutil
from typing import Any, Dict, List, Union

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text


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

    def match(self, data: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify license text and return ranked matches.
        """
        if isinstance(data, str):
            data = {"text": data, "only_spdx": True, "only_common": False}

        text = data.get("text", "")
        norm_input = normalize_text(text)
        words = norm_input.split()

        # Tier 0: Short-Text Fallback
        if len(words) < 12:
            return self._match_short_text(norm_input)

        # Tier 1: Broad Recall
        candidates = self._get_candidates(data, text)

        # Tier 2: Precision Ranking
        ranked = self._rank_candidates(candidates, norm_input, data)

        # Tier 3: Optional Java Consultant
        enable_java = data.get("enable_java", self.enable_java)
        if (
            enable_java
            and self.has_java
            and self.jar_path
            and os.path.exists(self.jar_path)
            and ranked
        ):
            return self._consult_java(text, ranked)

        return ranked

    def _get_candidates(self, data: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
        """Fetch and filter candidates from the database."""
        only_spdx = data.get("only_spdx", True)
        only_common = data.get("only_common", False)
        exclude_list = data.get("exclude", [])
        hint_list = data.get("hint", [])

        # Tier 1: Retrieval
        # Truncate very long queries for FTS5 to avoid performance/limit issues
        # 100 words is more than enough for trigram retrieval.
        words = text.split()
        search_query = text
        if len(words) > 100:
            search_query = " ".join(words[:100])

        # Fetch Top 50 for better recall
        candidates = self.db.search_candidates(search_query, limit=50)
        filtered = []
        for cand in candidates:
            license_id = cand["license_id"]
            if license_id in exclude_list:
                continue

            # Filtering logic using pre-fetched metadata
            if only_spdx and not cand.get("is_spdx"):
                continue
            if only_common and not cand.get("is_high_usage"):
                if not (cand.get("is_osi_approved") or cand.get("is_fsf_libre")):
                    continue

            filtered.append(cand)

        # Force-include hints
        candidate_ids = {c["license_id"] for c in filtered}
        for h_id in hint_list:
            if h_id not in candidate_ids:
                details = self.db.get_license_details(h_id)
                if details:
                    filtered.append(details)
        return filtered

    def _rank_candidates(
        self, candidates: List[Dict[str, Any]], norm_input: str, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank candidates using dynamic sliding window and popularity boost."""
        enable_popularity = data.get("enable_popularity", self.enable_popularity)
        query_words = norm_input.split()
        q_len = len(query_words)
        ranked: List[Dict[str, Any]] = []

        for cand in candidates:
            license_id = cand["license_id"]
            search_text = cand.get("search_text") or ""
            c_len = cand.get("word_count") or 0
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
                {
                    "license_id": license_id,
                    "base_score": similarity,
                    "similarity": similarity,
                    "coverage": coverage,
                    "pop_score": cand.get("popularity_score", 1),
                    "best_window": best_window,
                }
            )

        if ranked:
            # Composite scoring: Similarity is primary.
            # Coverage is a strong tie-breaker for similar texts.
            for r in ranked:
                similarity = r["base_score"]
                # Penalty for poor coverage: a license that is much larger than the input
                # is less likely to be the "exact" match than one of similar size.
                # However, we only apply this if similarity is high (likely a match).
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

        ranked.sort(key=lambda x: float(x["score"]), reverse=True)
        return ranked

    def _ensure_jvm(self) -> None:
        """Ensure the JVM is started with the tools-java JAR."""
        try:
            import jpype  # type: ignore[import-untyped] # pylint: disable=import-outside-toplevel
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
        self, text: str, ranked: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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

        ranked.sort(key=lambda x: float(x["score"]), reverse=True)
        return ranked

    def _match_short_text(self, norm_input: str) -> List[Dict[str, Any]]:
        """Fallback logic for very short inputs."""
        all_metadata = self.db.get_all_names_and_ids()
        ranked: List[Dict[str, Any]] = []
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
            score_name = fuzz.token_set_ratio(norm_input, name_norm)

            best_score = max(score_id, score_name, score_id_partial)
            if best_score >= threshold:
                ranked.append({"license_id": lid, "score": best_score / 100.0})

        ranked.sort(key=lambda x: float(x["score"]), reverse=True)
        return ranked

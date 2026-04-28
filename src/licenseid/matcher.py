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

        candidates = self.db.search_candidates(text, limit=30)
        filtered = []
        for cand in candidates:
            license_id = cand["license_id"]
            if license_id in exclude_list:
                continue

            details = self.db.get_license_details(license_id)
            if not details:
                continue

            if only_spdx and not details.get("is_spdx"):
                continue
            if only_common and not details.get("is_high_usage"):
                if not (details.get("is_osi_approved") or details.get("is_fsf_libre")):
                    continue

            cand["popularity_score"] = details.get("popularity_score", 1)
            filtered.append(cand)

        # Force-include hints
        candidate_ids = {c["license_id"] for c in filtered}
        for h_id in hint_list:
            if h_id not in candidate_ids:
                details = self.db.get_license_details(h_id)
                if details:
                    filtered.append(
                        {
                            "license_id": h_id,
                            "search_text": "",
                            "popularity_score": details.get("popularity_score", 1),
                        }
                    )
        return filtered

    def _rank_candidates(
        self, candidates: List[Dict[str, Any]], norm_input: str, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank candidates using fuzzy matching and popularity boost."""
        enable_popularity = data.get("enable_popularity", self.enable_popularity)
        ranked: List[Dict[str, Any]] = []
        for cand in candidates:
            search_text = cand.get("search_text") or ""
            base_score = fuzz.token_set_ratio(norm_input, search_text) / 100.0
            ranked.append(
                {
                    "license_id": cand["license_id"],
                    "base_score": base_score,
                    "pop_score": cand.get("popularity_score", 1),
                }
            )

        if ranked:
            top_base = max(r["base_score"] for r in ranked)
            tie_threshold = 0.002
            for r in ranked:
                if enable_popularity and (top_base - r["base_score"]) <= tie_threshold:
                    boost = math.log10(max(1, r["pop_score"])) * 0.005
                    r["score"] = r["base_score"] + boost
                else:
                    r["score"] = r["base_score"]

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

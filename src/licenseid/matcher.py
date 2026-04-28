# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import math
import os
import shutil
from typing import Any, Dict, List, Union

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text


class AggregatedLicenseMatcher:
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
        only_spdx = data.get("only_spdx", True)
        only_common = data.get("only_common", False)
        exclude_list = data.get("exclude", [])
        hint_list = data.get("hint", [])
        enable_java = data.get("enable_java", self.enable_java)
        enable_popularity = data.get("enable_popularity", self.enable_popularity)

        # Tier 0: Minimum Threshold Check & Short-Text Fallback
        norm_input = normalize_text(text)
        words = norm_input.split()

        # Evidence-based threshold: The shortest full license (any-OSI) is 12 words.
        # Anything shorter is treated as a title, snippet, or ID and uses the fallback logic.
        if len(words) < 12:
            return self._match_short_text(norm_input)

        # Tier 1: Broad Recall (SQLite Trigram)
        candidates = self.db.search_candidates(text)

        # Filter candidates based on metadata
        filtered_candidates = []
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
                # Fallback to OSI/FSF approval status if high_usage flag is missing
                if not (details.get("is_osi_approved") or details.get("is_fsf_libre")):
                    continue

            cand["popularity_score"] = details.get("popularity_score", 1)
            filtered_candidates.append(cand)

        # Force-include hints
        candidate_ids = {c["license_id"] for c in filtered_candidates}
        for h_id in hint_list:
            if h_id not in candidate_ids:
                details = self.db.get_license_details(h_id)
                if details:
                    # Append hinted license for precision ranking
                    filtered_candidates.append(
                        {
                            "license_id": h_id,
                            "search_text": "",
                            "popularity_score": details.get("popularity_score", 1),
                        }
                    )

        # Tier 2: Precision Ranking (RapidFuzz Token Set Ratio)
        # We compare the input text with the search_text (normalized fingerprint)
        ranked = []
        for cand in filtered_candidates:
            # If search_text is empty (e.g. from hint), try to fetch it
            search_text = cand.get("search_text") or ""

            # Token Set Ratio is good for reordered paragraphs and minor noise
            base_score = fuzz.token_set_ratio(norm_input, search_text) / 100.0
            ranked.append(
                {
                    "license_id": cand["license_id"],
                    "base_score": base_score,
                    "pop_score": cand.get("popularity_score", 1),
                }
            )

        # Popularity tie-breaker: only applies within a narrow band (0.2%) of the
        # top textual score so that large textual gaps are never overridden.
        # Candidates outside this band keep their base score unchanged.
        if ranked:
            top_base = max(r["base_score"] for r in ranked)
            tie_threshold = 0.002  # Diff between Apache-2.0 and Pixar is 0.0018
            for r in ranked:
                if enable_popularity and (top_base - r["base_score"]) <= tie_threshold:
                    boost = math.log10(max(1, r["pop_score"])) * 0.005
                    r["score"] = r["base_score"] + boost
                else:
                    r["score"] = r["base_score"]

        ranked.sort(key=lambda x: x["score"], reverse=True)

        # Tier 3: Optional Java Consultant
        if (
            enable_java
            and self.has_java
            and self.jar_path
            and os.path.exists(self.jar_path)
            and ranked
        ):
            return self._consult_java(text, ranked)

        return ranked

    def _ensure_jvm(self) -> None:
        """Ensure the JVM is started with the tools-java JAR."""
        try:
            import jpype
        except ImportError:
            raise ImportError(
                "JPype1 is required for Java validation. "
                "Install it with 'pip install licenseid[java]'"
            )

        if not jpype.isJVMStarted():
            # Start JVM with daemon thread support and string conversion disabled
            jpype.startJVM(classpath=[self.jar_path], convertStrings=False)
            # Initialize SPDX Model Factory once
            SpdxModelFactory = jpype.JClass("org.spdx.library.SpdxModelFactory")
            SpdxModelFactory.init()

    def _consult_java(
        self, text: str, ranked: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Consult the tools-java MatchingStandardLicenses logic via JPype.
        """
        try:
            import jpype
        except ImportError:
            # If enable_java was True but JPype is missing, we already checked in match()
            # but being safe here too.
            return ranked

        self._ensure_jvm()

        # Reliable thread attach/detach pattern
        JThread = jpype.JClass("java.lang.Thread")
        JThread.attachAsDaemon()
        try:
            LicenseCompareHelper = jpype.JClass(
                "org.spdx.utility.compare.LicenseCompareHelper"
            )

            # matchingStandardLicenseIdsWithinText returns a java.util.List<String>
            java_matches_list = (
                LicenseCompareHelper.matchingStandardLicenseIdsWithinText(text)
            )
            # convertStrings=False requires manual conversion
            java_matches = {str(m) for m in java_matches_list}

            # Boost scores for Java-verified matches
            for r in ranked:
                if r["license_id"] in java_matches:
                    r["score"] = 1.0  # Perfect match if Java verifies
                    r["java_verified"] = True
        except Exception:
            # Handle or log exception
            pass
        finally:
            JThread.detach()

        # Re-sort matches by boosted score
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    def _match_short_text(self, norm_input: str) -> List[Dict[str, Any]]:
        """
        Fallback logic for very short inputs (< 12 words) that are likely names, titles, or IDs.
        Matches against the license ID and official name rather than the full text to avoid false positives.
        """
        # Very short inputs (e.g. < 5 chars and 1 word) should be exact/prefix match, or just rejected
        # if they are generic like "this". But fuzzy match takes care of that if threshold is high.

        all_metadata = self.db.get_all_names_and_ids()
        ranked = []

        # Determine strictness threshold:
        # If the input is extremely short (1 word), require a very high similarity.
        # Otherwise, 85% similarity is a reasonable baseline for names.
        words = norm_input.split()
        threshold = 90.0 if len(words) <= 2 else 85.0

        for meta in all_metadata:
            lid = meta["license_id"]
            name = meta["name"]

            # Compare against ID
            id_norm = normalize_text(lid)
            score_id = fuzz.ratio(norm_input, id_norm)
            score_id_partial = (
                fuzz.partial_ratio(norm_input, id_norm) if len(words) == 1 else 0
            )

            # Compare against Name
            name_norm = normalize_text(name)
            # Use Token Set Ratio for names because titles might be permuted e.g. "GNU AFFERO" vs "GNU Affero General Public License"
            score_name = fuzz.token_set_ratio(norm_input, name_norm)

            best_score = max(score_id, score_name, score_id_partial)

            if best_score >= threshold:
                ranked.append({"license_id": lid, "score": best_score / 100.0})

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

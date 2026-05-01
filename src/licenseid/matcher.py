# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

import math
import os
import re
import shutil
from typing import Any, Optional, cast

from rapidfuzz import fuzz

from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier
from licenseid.markers import MarkerDetector
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
        self.detector = MarkerDetector(self.db)
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
        # pylint: disable=too-many-return-statements
        """
        Identify license text and return ranked matches.
        Must provide exactly one of text, license_id, or file_path.
        """
        # 1. Explicit ID Lookup
        if license_id:
            license_id = normalize_identifier(license_id, self.db)
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

        # Content Classification
        is_pure = self._is_pure_license_text(file_path, target_text)

        # Tier 0.5: Marker Detection
        # Detects explicit license identifiers and context clues in the text.
        # SPDX-License-Identifier is an unambiguous machine tag → early return.
        # All other markers (name fields, headings, first-line) go into the
        # candidate pool and influence ranking via a confidence bonus.
        marker_candidates = self.detector.detect(target_text)
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            return self._finalize_exact_markers(spdx_exact)

        # Build a marker-boost map: license_id → marker confidence score.
        # Used later in ranking to signal which candidates are marker-confirmed.
        marker_boosts: dict[str, float] = {
            c["license_id"]: c.get("score", 0.0) for c in marker_candidates
        }

        norm_input = normalize_text(target_text)
        words = norm_input.split()

        # Tier 0: Short-Text Shortcut (Names/IDs)
        if len(words) < 20:
            short_matches = self._match_short_text(norm_input)
            if short_matches and short_matches[0]["score"] > 1.0:
                return short_matches

        # Tier 1: Broad Recall
        candidates = self._get_candidates(request, target_text)

        # For mixed content or thin FTS5 results, augment via windowed search.
        if not candidates or (not is_pure and len(candidates) < 5):
            mixed_candidates = self._match_mixed_content(request, target_text)
            seen_ids = {c["license_id"] for c in candidates}
            for mc in mixed_candidates:
                if mc["license_id"] not in seen_ids:
                    candidates.append(mc)
                    seen_ids.add(mc["license_id"])

        # Merge marker candidates not already surfaced by FTS5.
        # Markers now carry real search_text so they rank on true similarity.
        seen_ids = {cand["license_id"] for cand in candidates}
        for c in marker_candidates:
            if c["license_id"] not in seen_ids:
                candidates.append(c)
                seen_ids.add(c["license_id"])

        # Tier 2: Precision Ranking
        # Pass marker boosts and purity context so ranking can weight signals
        # appropriately: small additive bonus for pure text (similarity leads),
        # confidence floor for mixed content (marker is primary signal).
        ranked = self._rank_candidates(
            candidates,
            norm_input,
            request,
            marker_boosts=marker_boosts,
            is_pure=is_pure,
        )

        # Tiebreaker: -only vs -or-later when scores are identical
        ranked = self._apply_version_suffix_tiebreaker(ranked, target_text, is_pure)

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

    def _rank_candidates(
        self,
        candidates: list[CandidateMatch],
        norm_input: str,
        data: MatchRequest,
        marker_boosts: Optional[dict[str, float]] = None,
        is_pure: bool = True,
    ) -> list[InternalMatch]:
        """Rank candidates using dynamic sliding window and marker-boosted scoring."""
        enable_popularity = data.get("enable_popularity", self.enable_popularity)
        query_words = norm_input.split()
        q_len = len(query_words)
        q_tokens = set(query_words)
        boosts = marker_boosts or {}
        ranked: list[InternalMatch] = []

        for cand in candidates:
            similarity, coverage, best_window = self._calculate_base_similarity(
                norm_input, q_len, q_tokens, cand
            )
            ranked.append(
                InternalMatch(
                    license_id=cand["license_id"],
                    base_score=similarity,
                    similarity=similarity,
                    coverage=coverage,
                    pop_score=cand.get("popularity_score", 0),
                    best_window=best_window,
                    score=0.0,
                )
            )

        for r in ranked:
            r["score"] = self._calculate_final_score(
                r, boosts, is_pure, enable_popularity
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    def _calculate_base_similarity(
        self, norm_input: str, q_len: int, q_tokens: set[str], cand: CandidateMatch
    ) -> tuple[float, float, str]:
        """Calculate base similarity and coverage for a candidate."""
        search_text = cand["search_text"] or ""
        c_len = cand["word_count"] or 0
        if c_len == 0:
            c_len = len(search_text.split())

        similarity = 0.0
        best_window = search_text

        if norm_input == search_text:
            similarity = 1.0
        elif q_len >= c_len * 0.8:
            similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0
        else:
            if q_len < 500:
                fast_score = fuzz.partial_ratio(norm_input, search_text) / 100.0
                if fast_score >= 0.6:
                    alignment = fuzz.partial_ratio_alignment(norm_input, search_text)
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
                similarity = fuzz.token_sort_ratio(norm_input, search_text) / 100.0

        # Semantic Safeguards
        if 0.90 < similarity < 1.0:
            critical_tokens = {"not", "except", "unless", "irrevocable"}
            c_tokens = set(search_text.split())
            for token in critical_tokens:
                if (token in q_tokens) != (token in c_tokens):
                    similarity *= 0.95

        coverage = (q_len / c_len) if c_len > 0 else 0.0
        return similarity, coverage, best_window

    def _calculate_final_score(
        self,
        match: InternalMatch,
        boosts: dict[str, float],
        is_pure: bool,
        enable_popularity: bool,
    ) -> float:
        """Calculate the final adjusted score for a match."""
        similarity = match["base_score"]
        coverage = match["coverage"]

        coverage_penalty = (1.0 - coverage) * 0.02 if coverage < 0.8 else 0.0
        coverage_bonus = 0.005 if 0.95 <= coverage <= 1.05 else 0.0

        score = similarity - coverage_penalty + coverage_bonus

        if enable_popularity:
            score += math.log10(max(1, match["pop_score"])) * 0.0001

        marker_conf = boosts.get(match["license_id"], 0.0)
        if marker_conf > 0:
            if is_pure:
                score += marker_conf * 0.03
            else:
                score = max(score, marker_conf * 0.95)

        return score

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

    # Detects -or-later granting language in mixed/source-file contexts.
    # Allows for comment characters (// # * ;) between "or" and "(at your option)".
    # Also catches shorthand notations like GPLv2+ and "version 2 or later".
    _RE_OR_LATER = re.compile(
        r"or[\s/*#;-]*\(?at\s+your\s+option\)?\s*[\s/*#;-]*any\s+later\s+version"
        r"|(?:version\s+)?v?\d+(?:\.\d+)?[\s,]+or\s+later\b"
        r"|(?:lgpl|gpl|agpl)[-v]?\d+(?:\.\d+)?\+",
        re.IGNORECASE | re.MULTILINE,
    )

    def _has_or_later_language(self, text: str) -> bool:
        """Return True if text contains -or-later granting language.

        Only meaningful for non-pure input (source files, READMEs).  The GPL
        license body itself contains the same phrase in its 'How to Apply'
        appendix, so this must NOT be called on pure license text.
        """
        return bool(self._RE_OR_LATER.search(text))

    def _apply_version_suffix_tiebreaker(
        self, ranked: list[InternalMatch], raw_text: str, is_pure: bool
    ) -> list[InternalMatch]:
        """Break -only / -or-later ties using granting language in the input.

        When two candidates share the same base ID (e.g. GPL-2.0-only and
        GPL-2.0-or-later) and their scores are within 0.01 of each other,
        apply a small score nudge:

        - Pure license text: the body is identical for both; the GPL appendix
          also contains the 'or later' template, making regexes unreliable.
          Default to -only (conservative: grant exactly this version).
        - Mixed / source-file text: check for explicit granting language.
          Granting language present → prefer -or-later.
          No granting language      → prefer -only.
        """
        if is_pure:
            or_later_signal = False  # body text indistinguishable; default -only
        else:
            or_later_signal = self._has_or_later_language(raw_text)

        id_to_score = {r["license_id"]: r["score"] for r in ranked}
        # Track which base IDs we've already processed to avoid double-counting.
        processed: set[str] = set()
        adjustments: dict[str, float] = {}

        for match in ranked:
            lid = match["license_id"]
            if lid.endswith("-only"):
                base, peer = lid[:-5], lid[:-5] + "-or-later"
            elif lid.endswith("-or-later"):
                base, peer = lid[:-9], lid[:-9] + "-only"
            else:
                continue

            if base in processed or peer not in id_to_score:
                continue

            if abs(match["score"] - id_to_score[peer]) > 0.01:
                continue  # not a genuine tie — trust the similarity score

            processed.add(base)
            delta = 0.005
            if or_later_signal:
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
            ranked.sort(key=lambda x: x["score"], reverse=True)

        return ranked

    def _finalize_exact_markers(
        self, exact: list[CandidateMatch]
    ) -> list[LicenseMatch]:
        """Convert SPDX-exact marker candidates to LicenseMatch results."""
        seen: set[str] = set()
        results: list[LicenseMatch] = []
        for c in exact:
            lid = c["license_id"]
            if lid in seen:
                continue
            seen.add(lid)
            results.append(
                LicenseMatch(
                    license_id=lid,
                    score=1.0,
                    similarity=1.0,
                    coverage=1.0,
                    is_spdx=c.get("is_spdx", False),
                    is_osi_approved=c.get("is_osi_approved", False),
                    is_fsf_libre=c.get("is_fsf_libre", False),
                )
            )
        return results

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

    # Compiled once at class level for efficiency
    _RE_NON_LICENSE_SECTION = re.compile(
        r"^#{1,6}\s*"
        r"(installation|usage|getting\s+started|contributing|"
        r"prerequisites|requirements|setup|build|deploy|example|"
        r"quick\s+start|table\s+of\s+contents|overview|features|"
        r"changelog|roadmap|faq|support|credits|acknowledgements?)",
        re.IGNORECASE,
    )
    _RE_LICENSE_OPENER = re.compile(
        r"(permission is hereby granted|permission to use, copy|"
        r"gnu general public license|apache license|"
        r"mozilla public license|common development and distribution|"
        r"creative commons|redistribution and use in source|"
        r"everyone is permitted to copy)",
        re.IGNORECASE,
    )
    _RE_NUMBERED_SECTION = re.compile(r"^\s*\d+\.\s+\w", re.MULTILINE)

    def _is_pure_license_text(self, file_path: Optional[str], text: str) -> bool:
        """Return True if the content appears to be a standalone license document.

        Uses filename as a strong positive signal, then falls back to
        content heuristics so plain-text license input (no file_path) is
        also classified correctly.
        """
        if file_path:
            basename = os.path.basename(file_path).upper()
            if basename in ("LICENSE", "COPYING", "UNLICENSE", "LICENCE") or any(
                basename.startswith(p) for p in ("LICENSE.", "COPYING.", "LICENCE.")
            ):
                return True

        if len(text.split()) < 30 or "```" in text or "~~~" in text:
            return False

        md_headers = [
            line for line in text.splitlines() if re.match(r"^#{1,6}\s+\S", line)
        ]
        if len(md_headers) > 3 or any(
            self._RE_NON_LICENSE_SECTION.match(h) for h in md_headers
        ):
            return False

        # Positive indicators: numbered sections or known preamble
        return len(self._RE_NUMBERED_SECTION.findall(text)) >= 3 or bool(
            self._RE_LICENSE_OPENER.search(text[:1000])
        )

    def _match_mixed_content(
        self, request: MatchRequest, target_text: str
    ) -> list[CandidateMatch]:
        """Extract sections from mixed content and search them for licenses."""
        sections = self.detector.get_sections(target_text)
        candidates: list[CandidateMatch] = []
        seen_ids = set()

        for section in sections:
            # 1. Try Tier 0 (Short Text) on the windowed section
            norm_section = normalize_text(section)
            short_matches = self._match_short_text(norm_section)
            for m in short_matches:
                if m["license_id"] not in seen_ids:
                    details = self.db.get_license_details(m["license_id"])
                    if details:
                        candidates.append(
                            self.detector.to_candidate(details, m["score"])
                        )
                        seen_ids.add(m["license_id"])

            # 2. Try Tier 1 (Recall) on a targeted window starting at the keyword
            # We find the keyword in the section and start there for FTS5
            words = section.split()
            for i, word in enumerate(words):
                if "licens" in word.lower():
                    # FTS5 works best if the first few words are relevant
                    fts_query_text = " ".join(words[i : i + 50])
                    for c in self._get_candidates(request, fts_query_text):
                        if c["license_id"] not in seen_ids:
                            candidates.append(c)
                            seen_ids.add(c["license_id"])

        # Fallback: if no sections found or no candidates from sections,
        # try the whole text (it might be a pure license without keyword)
        if not candidates:
            candidates = self._get_candidates(request, target_text)
        return candidates

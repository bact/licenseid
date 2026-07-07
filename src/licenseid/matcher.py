# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

import os
import shutil
from typing import Any, Optional, cast

from rapidfuzz import fuzz

from licenseid.classify import has_or_later_language, is_pure_license_text
from licenseid.database import LicenseDatabase, get_default_db_path
from licenseid.identifiers import (
    disambiguate_deprecated_id,
    normalize_identifier,
)
from licenseid.markers import MarkerDetector
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.similarity import (
    build_probe,
    calculate_base_similarity,
    calculate_final_score,
)
from licenseid.types import (
    CandidateMatch,
    InternalMatch,
    LicenseDetails,
    LicenseMatch,
    MatchRequest,
)

# Maximum additive boost applied to a candidate whose highest-IDF fingerprint
# n-gram has idf_norm == 1.0 (unique to that single license in the corpus).
# Calibrated to be in the same range as the marker boost (~0.05) so that
# fingerprint matches can break ties between near-equal similarity scores
# without overriding genuine similarity differences.
_FP_BOOST: float = 0.05

# Effective score penalty applied to deprecated licenses during ranking.
# Ensures that when a deprecated alias (e.g. GPL-2.0) and its canonical
# non-deprecated replacement (e.g. GPL-2.0-only) are both candidates with
# similar similarity scores, the canonical ID wins.  Calibrated at 0.03:
# large enough to overcome the typical 0.01–0.02 score gap caused by
# marker-confidence differences, small enough to avoid masking cases
# where the deprecated ID genuinely matches better (e.g. inputs that
# reference only "GPL-2.0" with no "only"/"or-later" qualifier).
_DEP_PENALTY: float = 0.03


class AggregatedLicenseMatcher:
    """
    Main matcher class that implements Tier 1 (FTS5), Tier 2 (RapidFuzz),
    and Tier 3 (Java) matching.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        enable_java: bool = False,
        enable_popularity: bool = False,
    ):
        if not db_path:
            db_path = get_default_db_path()
        self.db = LicenseDatabase(db_path)
        self.detector = MarkerDetector(self.db)
        self.enable_java = enable_java
        self.enable_popularity = enable_popularity
        self.jar_path = os.getenv("SPDX_TOOLS_JAR")
        self.has_java = shutil.which("java") is not None

    # pylint: disable=too-many-locals
    def match(
        self,
        text: Optional[str] = None,
        *,
        license_id: Optional[str] = None,
        file_path: Optional[str] = None,
        **options: Any,
    ) -> list[LicenseMatch]:
        # pylint: disable=too-many-return-statements
        # pylint: disable=too-many-branches
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
        is_pure = is_pure_license_text(file_path, target_text)

        norm_input = normalize_text(target_text)
        words = norm_input.split()

        # Tier 0.5: Marker Detection
        # Detects explicit license identifiers and context clues in the text.
        # SPDX-License-Identifier is an unambiguous machine tag → early return.
        # All other markers (name fields, headings, first-line) go into the
        # candidate pool and influence ranking via a confidence bonus.
        # Skip for very short inputs (< 30 words): marker scanning adds
        # overhead without benefit — these inputs are handled by Tier 0.
        marker_candidates: list[CandidateMatch] = []
        if len(words) >= 30:
            marker_candidates = self.detector.detect(
                target_text,
                file_path=file_path,
            )
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            return self._finalize_exact_markers(spdx_exact)

        # Build a marker-boost map: license_id -> marker confidence score.
        # Used later in ranking to signal which candidates are
        # marker-confirmed.
        marker_boosts: dict[str, float] = {
            c["license_id"]: c.get("score", 0.0) for c in marker_candidates
        }

        # Tier 0: Short-Text Shortcut (Names/IDs)
        # Threshold: inputs under 30 words (~200 chars) are likely bare IDs
        # or short names and can be resolved via exact/fuzzy name matching
        # without entering the FTS5 pipeline.  Keeping this threshold low
        # avoids routing ~50-word licence preambles (head_300 inputs) through
        # the name matcher, which degrades recall for variant licences
        # (e.g. MIT-STK, MIT-enna) where it returns the generic parent.
        if len(words) < 30:
            # Fast path: bare deprecated ID + prose disambiguation context in
            # the raw (un-normalised) text, e.g. "GPL-2.0 or later version".
            # Must use target_text, not norm_input, because normalize_text()
            # strips punctuation/case that the regex patterns rely on.
            disambiguated = disambiguate_deprecated_id(target_text)
            if disambiguated:
                details = self.db.get_license_details(disambiguated)
                return [
                    LicenseMatch(
                        license_id=disambiguated,
                        score=1.02,
                        similarity=1.0,
                        coverage=1.0,
                        is_spdx=details["is_spdx"] if details else True,
                        is_osi_approved=(
                            details["is_osi_approved"] if details else False
                        ),
                        is_fsf_libre=details["is_fsf_libre"] if details else False,
                    )
                ]

            short_matches = self._match_short_text(norm_input)
            if short_matches and short_matches[0]["score"] > 1.0:
                # Apply marker boosts to break ties among equal-scored
                # candidates
                if marker_boosts:
                    for sm in short_matches:
                        marker_conf = marker_boosts.get(sm["license_id"], 0.0)
                        sm["score"] += marker_conf * 0.01
                    short_matches.sort(key=lambda x: (-x["score"], x["license_id"]))
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
        ranked = self._apply_version_suffix_tiebreaker(
            ranked,
            target_text,
            is_pure,
            enable_pop=request.get(
                "enable_popularity",
                self.enable_popularity,
            ),
        )

        # Tier 3: Optional Java Consultant
        enable_java = request.get("enable_java", self.enable_java)
        if (
            enable_java
            and self.has_java
            and self.jar_path
            and os.path.exists(self.jar_path)
            and ranked
        ):
            return cast(
                list[LicenseMatch],
                self._consult_java(target_text, ranked),
            )

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

    def _get_candidates(
        self,
        data: MatchRequest,
        text: str,
    ) -> list[CandidateMatch]:
        """Fetch and filter candidates from the database."""
        only_spdx = data.get("only_spdx", True)
        only_common = data.get("only_common", False)
        exclude_list: list[str] = data.get("exclude", [])
        hint_list: list[str] = data.get("hint", [])

        # Strip comment prefixes before FTS5: improves recall for Type 5
        # inputs where license text is wrapped in // / # / * comment markers.
        text = strip_comment_prefixes(text)

        # Normalize the full text once, up front, before any word-count
        # slicing.  normalize_text() applies several line-anchored rules
        # (copyright-notice removal, bullets, comment prefixes, separator
        # runs) that only fire correctly with real line breaks intact.
        # Slicing raw words first and rejoining them with spaces (the
        # previous approach) destroyed that line structure before
        # normalization ever ran, so the query-side text silently skipped
        # rules that index-side normalization (run on the untouched
        # original text in database.py) had already applied — producing
        # FTS5 OR-terms for words that no longer exist in the indexed
        # document.  Normalizing here keeps query-side and index-side
        # normalization consistent.
        norm_text = normalize_text(text)

        # Tier 1: Retrieval
        # search_candidates builds an OR query from the first 20 words of
        # whatever it receives (see database.py).  The caps below control
        # which normalised words those are:
        #
        #   Head query: pass norm_words[:100] so search_candidates uses
        #     words 0–19 (the preamble/title, which is highly distinctive).
        #     The 100-word buffer leaves room if the OR-term limit is raised
        #     again later.
        #
        #   Tail query: pass norm_words[-20:] — exactly the last 20 words —
        #     so search_candidates uses words -20 to -1 (the true end of the
        #     document: warranty disclaimer, governing-law clause, etc.).
        #     Benchmarks showed that passing words[-120:] was wrong: FTS5 only
        #     saw words -120 to -101, which are mid-text and less distinctive
        #     than the actual tail.  Aligning the slice with the OR-term limit
        #     (20 words) recovers those end-specific signals.
        #     Threshold >200 words ensures head (0–99) and tail (last 20) are
        #     non-overlapping for inputs up to any realistic length.
        #
        # Both queries use limit=50 so BM25 ranking is computed over 50
        # results before any cap.  Tail-only additions (candidates in the
        # tail set but not the head set) are capped at 25, bounding the
        # union at 75 candidates and Tier 2 (RapidFuzz) work at 75 passes.
        #
        # Benchmark on 469 licences with >200 normalised words showed that
        # uncapped tail adds a mean of 33 candidates (median 38, max 50),
        # pushing the union to a mean of 83 (max 100).  Because tail
        # candidates are in BM25 order the cap retains the 25 most
        # distinctive tail-only candidates and discards the rest, which are
        # largely generic vocabulary shared across many licences.
        # The cap does not affect the head set (always up to 50).
        #
        # These thresholds (100/200/50/25/20) were originally tuned against
        # raw word counts; they now slice normalised word counts instead,
        # which are usually somewhat shorter (copyright/comment/bullet noise
        # removed) — re-validate via bench_compare after this change.
        _TAIL_ONLY_CAP = 25
        norm_words = norm_text.split()
        raw_candidates: list[CandidateMatch] = []
        if len(norm_words) > 100:
            head_query = " ".join(norm_words[:100])
            raw_candidates = list(
                self.db.search_candidates(
                    head_query, limit=50, already_normalized=True
                )
            )
            if len(norm_words) > 200:
                tail_query = " ".join(norm_words[-20:])
                seen_ids = {
                    c["license_id"] for c in raw_candidates if c.get("license_id")
                }
                tail_only_added = 0
                for c in self.db.search_candidates(
                    tail_query, limit=50, already_normalized=True
                ):
                    if tail_only_added >= _TAIL_ONLY_CAP:
                        break
                    if c.get("license_id") not in seen_ids:
                        raw_candidates.append(c)
                        seen_ids.add(c["license_id"])
                        tail_only_added += 1
        else:
            raw_candidates = list(
                self.db.search_candidates(norm_text, limit=50, already_normalized=True)
            )

        filtered: list[CandidateMatch] = []
        for cand in raw_candidates:
            license_id = cand.get("license_id")
            if not license_id or license_id in exclude_list:
                continue

            # Filtering logic using pre-fetched metadata
            if only_spdx and not cand.get("is_spdx", False):
                continue
            if only_common and not cand.get("is_high_usage", False):
                if not (
                    cand.get("is_osi_approved", False)
                    or cand.get("is_fsf_libre", False)
                ):
                    continue

            filtered.append(cand)

        candidate_ids = {c.get("license_id") for c in filtered if c.get("license_id")}
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
                            pop_score=details.get("pop_score", 0),
                            is_deprecated=details.get("is_deprecated", False),
                            superseded_by=details.get("superseded_by", ""),
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
        """Rank candidates using dynamic sliding window and
        marker-boosted scoring."""
        enable_popularity = data.get(
            "enable_popularity",
            self.enable_popularity,
        )
        query_words = norm_input.split()
        q_len = len(query_words)
        q_tokens = set(query_words)
        boosts = marker_boosts or {}
        ranked: list[InternalMatch] = []

        # Precompute the probe sample once per query (see similarity.PROBE_WORDS).
        probe = build_probe(query_words)

        for cand in candidates:
            sim, coverage, best_window = calculate_base_similarity(
                norm_input, q_len, q_tokens, cand, probe
            )
            ranked.append(
                InternalMatch(
                    license_id=cand["license_id"],
                    base_score=sim,
                    similarity=sim,
                    coverage=coverage,
                    pop_score=cand.get("pop_score", 0),
                    is_deprecated=cand.get("is_deprecated", False),
                    superseded_by=cand.get("superseded_by", ""),
                    best_window=best_window,
                    score=0.0,
                )
            )

        for r in ranked:
            r["score"] = calculate_final_score(
                r, boosts, is_pure, enable_popularity, q_len
            )

        # Fingerprint boost: add a small bonus to candidates that share at
        # least one discriminative n-gram with the query.  The bonus is
        # proportional to idf_norm (the uniqueness of the matching n-gram
        # within the corpus), capped at _FP_BOOST.  This breaks ties between
        # high-similarity variants (e.g. MIT vs MIT-0, GPL-2.0 vs GPL-3.0)
        # without distorting the overall similarity ranking.
        fp_hits = self.db.find_fingerprint_hits(norm_input)
        if fp_hits:
            for r in ranked:
                idf_norm = fp_hits.get(r["license_id"], 0.0)
                if idf_norm > 0.0:
                    r["score"] += _FP_BOOST * idf_norm

        # Ranking criteria:
        # 1. Final score (similarity + boosts), with deprecated penalty applied
        #    as an adjustment so deprecated aliases rank below their canonical
        #    non-deprecated replacements when scores are close.
        # 2. Prefer non-deprecated
        # 3. Prefer higher popularity (if enabled)
        # 4. Alphabetical tie-break
        def sort_key(x: InternalMatch) -> tuple[float, bool, float, str]:
            dep_adj = _DEP_PENALTY if x.get("is_deprecated", False) else 0.0
            return (
                -(x["score"] - dep_adj),
                x.get("is_deprecated", False),
                -x.get("pop_score", 0) if enable_popularity else 0.0,
                x["license_id"],
            )

        ranked.sort(key=sort_key)
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
            classpath = [self.jar_path] if self.jar_path is not None else None
            jpype.startJVM(classpath=classpath, convertStrings=False)
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

        def sort_key(x: InternalMatch) -> tuple[float, bool, float, str]:
            return (
                -x["score"],
                x.get("is_deprecated", False),
                -x.get("pop_score", 0) if self.enable_popularity else 0.0,
                x["license_id"],
            )

        ranked.sort(key=sort_key)
        return ranked


    def _apply_version_suffix_tiebreaker(
        self,
        ranked: list[InternalMatch],
        raw_text: str,
        is_pure: bool,
        enable_pop: bool = False,
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
            or_later_signal = has_or_later_language(raw_text)

        id_to_score = {r["license_id"]: r["score"] for r in ranked}
        # Track which base IDs we've already processed to avoid
        # double-counting.
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

            def sort_key(x: InternalMatch) -> tuple[float, bool, float, str]:
                return (
                    -x["score"],
                    x.get("is_deprecated", False),
                    -x.get("pop_score", 0) if enable_pop else 0.0,
                    x["license_id"],
                )

            ranked.sort(key=sort_key)

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
        norm_upper = norm_input.upper()

        for meta in all_metadata:
            lid = meta["license_id"]
            id_norm = meta["norm_license_id"]
            name_norm = meta["norm_name"]

            # Case-fold exact ID match: return immediately with a score > 1.0
            # so the Tier 0 caller recognises it as a definitive hit.
            if id_norm.upper() == norm_upper:
                return [
                    LicenseMatch(
                        license_id=lid,
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
                # Penalise deprecated aliases so the canonical replacement wins
                # when scores are otherwise tied or close.
                if meta["is_deprecated"]:
                    score -= _DEP_PENALTY

                ranked.append(
                    LicenseMatch(
                        license_id=lid,
                        score=score,
                        similarity=best_raw / 100.0,
                        coverage=0.0,
                    )
                )

        ranked.sort(
            key=lambda x: (
                -x["score"],
                x.get("is_deprecated", False),
                -cast(int, x.get("pop_score", 0)),
                x["license_id"],
            )
        )
        return ranked

    def _match_mixed_content(
        self, request: MatchRequest, target_text: str
    ) -> list[CandidateMatch]:
        """Extract sections from mixed content and search them for licenses."""
        sections = self.detector.get_sections(target_text)
        candidates: list[CandidateMatch] = []
        seen_ids = set()

        for section in sections:
            # Strip comment prefixes before both short-text and FTS5 matching
            # so that comment-wrapped license text (Type 5) is handled cleanly.
            section = strip_comment_prefixes(section)
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

            # 2. Try Tier 1 (Recall) on a targeted window starting at the
            # keyword
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

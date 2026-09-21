# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

from dataclasses import dataclass
from typing import Any, cast

from licenseid.classify import is_pure_license_text
from licenseid.database import LicenseDatabase, get_default_db_path
from licenseid.dbcheck import check_database_ready
from licenseid.errors import InvalidInputError
from licenseid.identifiers import (
    disambiguate_deprecated_id,
    normalize_identifier,
    parse_expression,
    strip_plus_operator,
    with_expression_details,
)
from licenseid.markers import MarkerDetector
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.ranking import apply_version_suffix_tiebreaker, ranking_key
from licenseid.retrieval import get_candidates
from licenseid.shorttext import match_short_text
from licenseid.similarity import (
    build_probe,
    calculate_base_similarity,
    calculate_final_score,
)
from licenseid.textinput import read_text_file
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


# The keyword options match() accepts; `text`, `license_id` and `file_path`
# are its named parameters, so a request can carry no other key.
_MATCH_OPTIONS: frozenset[str] = frozenset(MatchRequest.__annotations__) - {
    "text",
    "license_id",
    "file_path",
}


def _reject_unknown_options(options: dict[str, Any]) -> None:
    """Raise InvalidInputError for an option match() does not know, so a typo
    or a removed option (`enable_java`) cannot pass with no effect."""
    unknown = sorted(options.keys() - _MATCH_OPTIONS)
    if unknown:
        raise InvalidInputError(
            f"option: invalid: {', '.join(map(repr, unknown))}"
            f"; use one of {', '.join(sorted(_MATCH_OPTIONS))}"
        )


@dataclass(frozen=True)
class _MatchContext:
    """Immutable per-call state threaded through match()'s tiers. Built
    once after file/text resolution; read-only afterward. Not part of
    the public API. marker_candidates/marker_boosts live outside this
    context as explicit parameters instead, since they're a tier's
    *output* (Tier 0.5's) rather than a fixed, request-scoped input."""

    target_text: str
    file_path: str | None
    request: MatchRequest
    is_pure: bool
    norm_input: str
    word_count: int


class AggregatedLicenseMatcher:
    """
    Main matcher class that implements Tier 1 (FTS5) and Tier 2 (RapidFuzz)
    matching.
    """

    def __init__(
        self,
        db_path: str | None = None,
        *,
        enable_popularity: bool = False,
    ):
        if not db_path:
            db_path = get_default_db_path()
        # Before LicenseDatabase, which creates its tables on open.
        check_database_ready(db_path)
        self.db = LicenseDatabase(db_path)
        self.detector = MarkerDetector(self.db)
        self.enable_popularity = enable_popularity

    def _try_explicit_id_match(self, license_id: str) -> list[LicenseMatch]:
        """Phase 1: resolve an explicit license_id argument to a match."""
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
        with_match = self._match_with_expression(license_id)
        if with_match:
            return [with_match]
        return []

    def _resolve_target_text(self, text: str | None, file_path: str | None) -> str:
        """Phase 2: read file_path as the CLI reads a file, or use the text."""
        if file_path:
            return read_text_file(file_path)
        return text or ""

    def _build_match_context(
        self, target_text: str, file_path: str | None, options: MatchRequest
    ) -> _MatchContext:
        """Phase 2 (cont.): classify content and build the immutable
        per-call state shared by the remaining tiers."""
        request = options
        request["text"] = target_text
        norm_input = normalize_text(target_text)
        return _MatchContext(
            target_text=target_text,
            file_path=file_path,
            request=request,
            is_pure=is_pure_license_text(file_path, target_text),
            norm_input=norm_input,
            word_count=len(norm_input.split()),
        )

    def _try_tier0_5_markers(
        self, ctx: _MatchContext
    ) -> tuple[list[CandidateMatch], dict[str, float], list[LicenseMatch] | None]:
        """Tier 0.5: Marker Detection.

        Detects explicit license identifiers and context clues in the
        text. SPDX-License-Identifier is an unambiguous machine tag, so
        it's returned as a final answer (the third tuple element). All
        other markers (name fields, headings, first-line) go into the
        candidate pool and influence ranking via a confidence bonus.
        Skip for very short inputs (< 30 words): marker scanning adds
        overhead without benefit — these inputs are handled by Tier 0.
        """
        marker_candidates: list[CandidateMatch] = []
        if ctx.word_count >= 30:
            marker_candidates = self.detector.detect(
                ctx.target_text,
                file_path=ctx.file_path,
            )
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            return marker_candidates, {}, self._finalize_exact_markers(spdx_exact)

        # Build a marker-boost map: license_id -> marker confidence score.
        # Used later in ranking to signal which candidates are
        # marker-confirmed.
        marker_boosts = {
            c["license_id"]: c.get("score", 0.0) for c in marker_candidates
        }
        return marker_candidates, marker_boosts, None

    def _try_tier0_short_text(self, ctx: _MatchContext) -> list[LicenseMatch] | None:
        """Tier 0: Short-Text Shortcut (Names/IDs).

        Threshold: inputs under 30 words (~200 chars) are likely bare IDs
        or short names and can be resolved via exact/fuzzy name matching
        without entering the FTS5 pipeline. Keeping this threshold low
        avoids routing ~50-word licence preambles (head_300 inputs)
        through the name matcher, which degrades recall for variant
        licences (e.g. MIT-STK, MIT-enna) where it returns the generic
        parent. Returns None (fall through to Tier 1) for inputs at or
        above the threshold, or below it with no confident match.
        """
        if ctx.word_count >= 30:
            return None

        # Fast path: bare deprecated ID + prose disambiguation context in
        # the raw (un-normalised) text, e.g. "GPL-2.0 or later version".
        # Must use target_text, not norm_input, because normalize_text()
        # strips punctuation/case that the regex patterns rely on.
        disambiguated = disambiguate_deprecated_id(ctx.target_text)
        if disambiguated:
            details = self.db.get_license_details(disambiguated)
            return [
                LicenseMatch(
                    license_id=disambiguated,
                    score=1.02,
                    similarity=1.0,
                    coverage=1.0,
                    is_spdx=details["is_spdx"] if details else True,
                    is_osi_approved=(details["is_osi_approved"] if details else False),
                    is_fsf_libre=details["is_fsf_libre"] if details else False,
                )
            ]

        short_matches = self._match_short_text(ctx.norm_input)
        if short_matches and short_matches[0]["score"] > 1.0:
            return short_matches

        return None

    def _run_tier1_and_tier2(
        self,
        ctx: _MatchContext,
        marker_candidates: list[CandidateMatch],
        marker_boosts: dict[str, float],
    ) -> list[InternalMatch]:
        """Tier 1 (Broad Recall) retrieval + augmentation, then Tier 2
        (Precision Ranking). Never short-circuits match()."""
        candidates = self._get_candidates(ctx.request, ctx.target_text)

        # For mixed content or thin FTS5 results, augment via windowed search.
        if not candidates or (not ctx.is_pure and len(candidates) < 5):
            mixed_candidates = self._match_mixed_content(ctx.request, ctx.target_text)
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

        # Pass marker boosts and purity context so ranking can weight signals
        # appropriately: small additive bonus for pure text (similarity leads),
        # confidence floor for mixed content (marker is primary signal).
        return self._rank_candidates(
            candidates,
            ctx.norm_input,
            ctx.request,
            marker_boosts=marker_boosts,
            is_pure=ctx.is_pure,
        )

    def match(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: str | None = None,
        **options: Any,
    ) -> list[LicenseMatch]:
        """
        Identify license text and return ranked matches.
        Must provide exactly one of text, license_id, or file_path.
        Raises licenseid.errors.InvalidInputError: unknown option, binary file.
        """
        _reject_unknown_options(options)
        if license_id:
            return self._try_explicit_id_match(license_id)

        target_text = self._resolve_target_text(text, file_path)
        if not target_text:
            return []

        ctx = self._build_match_context(
            target_text, file_path, cast(MatchRequest, options)
        )

        # Tier 0.5: Marker Detection — SPDX-License-Identifier is
        # unambiguous and short-circuits; other markers feed the
        # candidate pool and ranking boost.
        marker_candidates, marker_boosts, spdx_exact = self._try_tier0_5_markers(ctx)
        if spdx_exact is not None:
            return spdx_exact

        # Tier 0: Short-Text Shortcut — bare IDs/names below the word
        # threshold are resolved without entering the FTS5 pipeline.
        short_text_result = self._try_tier0_short_text(ctx)
        if short_text_result is not None:
            return short_text_result

        # Tier 1: Broad Recall, then Tier 2: Precision Ranking.
        ranked = self._run_tier1_and_tier2(ctx, marker_candidates, marker_boosts)

        # Tiebreaker: -only vs -or-later when scores are identical
        ranked = apply_version_suffix_tiebreaker(
            ranked,
            ctx.target_text,
            ctx.is_pure,
            enable_pop=ctx.request.get(
                "enable_popularity",
                self.enable_popularity,
            ),
        )

        return cast(list[LicenseMatch], ranked)

    def _match_with_expression(self, license_id: str) -> LicenseMatch | None:
        """Resolve a bare ``<license> WITH <exception>`` expression.

        The ``licenses`` table only has rows for plain license IDs (plus a
        handful of legacy hardcoded compound IDs), so a well-formed but
        otherwise unseen expression like ``MIT WITH Font-exception-2.0``
        would not be found by a direct ``get_license_details`` lookup even
        though it is perfectly valid. Parse it structurally, then validate
        each half against this project's own (live-downloaded) license and
        exception tables.

        A ``+`` after the license is kept (``Apache-2.0+ WITH X``). An input
        that does not parse (see identifiers.parse_expression) is not a WITH
        match.
        """
        without_plus = strip_plus_operator(license_id)
        details = with_expression_details(parse_expression(without_plus), self.db)
        if not details:
            return None
        lic_details, exc_details = details

        plus = "+" if without_plus != license_id else ""
        combined_id = (
            f"{lic_details['license_id']}{plus} WITH {exc_details['exception_id']}"
        )
        return LicenseMatch(
            license_id=combined_id,
            score=1.0,
            similarity=1.0,
            coverage=1.0,
            is_spdx=lic_details["is_spdx"],
            is_osi_approved=lic_details["is_osi_approved"],
            is_fsf_libre=lic_details["is_fsf_libre"],
        )

    def resolve_record(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: str | None = None,
    ) -> LicenseDetails | None:
        """Resolve the input to the record of its top match (score 0.85 or
        more), or None. The is_*() predicates and the CLI's is-* commands both
        answer from this, so they cannot disagree with match()."""
        results = self.match(text, license_id=license_id, file_path=file_path)
        if not results or results[0]["score"] < 0.85:
            return None

        top = results[0]
        record = self.db.get_license_details(top["license_id"])
        if record:
            return record

        # Composite "license WITH exception" matches aren't a single DB
        # row (see _match_with_expression) — fall back to the flags match()
        # already computed rather than reporting "unknown".
        return cast(
            LicenseDetails,
            {
                "license_id": top["license_id"],
                "name": top["license_id"],
                "is_spdx": top.get("is_spdx", False),
                "is_osi_approved": top.get("is_osi_approved", False),
                "is_fsf_libre": top.get("is_fsf_libre", False),
                "is_high_usage": False,
                "pop_score": 0,
                "word_count": 0,
            },
        )

    def is_spdx(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is in the SPDX License List."""
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_spdx", False)

    def is_osi(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved."""
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_osi_approved", False)

    def is_fsf(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is FSF-libre."""
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_fsf_libre", False)

    def is_open(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved OR FSF-libre."""
        record = self.resolve_record(text, **kwargs)
        if not record:
            return False
        return bool(
            record.get("is_osi_approved", False) or record.get("is_fsf_libre", False)
        )

    def _get_candidates(self, data: MatchRequest, text: str) -> list[CandidateMatch]:
        """Tier 1 retrieval for *text* (see licenseid.retrieval)."""
        return get_candidates(self.db, data, text)

    def _match_short_text(self, norm_input: str) -> list[LicenseMatch]:
        """Tier 0 ID and name matching for a short input (see
        licenseid.shorttext)."""
        return match_short_text(self.db, norm_input)

    def _rank_candidates(
        self,
        candidates: list[CandidateMatch],
        norm_input: str,
        data: MatchRequest,
        marker_boosts: dict[str, float] | None = None,
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

        ranked.sort(key=ranking_key(enable_popularity))
        return ranked

    def _finalize_exact_markers(
        self, exact: list[CandidateMatch]
    ) -> list[LicenseMatch]:
        """Convert SPDX-exact marker candidates to LicenseMatch results."""
        # MarkerDetector.detect() already returns one candidate per license_id.
        return [
            LicenseMatch(
                license_id=c["license_id"],
                score=1.0,
                similarity=1.0,
                coverage=1.0,
                is_spdx=c.get("is_spdx", False),
                is_osi_approved=c.get("is_osi_approved", False),
                is_fsf_libre=c.get("is_fsf_libre", False),
            )
            for c in exact
        ]

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

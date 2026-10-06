# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

import contextlib
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from licenseid.classify import is_pure_license_text
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import check_database_ready, lookup_error
from licenseid.errors import InvalidInputError, invalid_id_error
from licenseid.identifiers import disambiguate_deprecated_id, is_simple_expression
from licenseid.manifest import extension, license_value_groups
from licenseid.markers import MarkerDetector
from licenseid.normalize import normalize_text, strip_comment_prefixes
from licenseid.ranking import apply_version_suffix_tiebreaker, ranking_key
from licenseid.result import public_result
from licenseid.retrieval import get_candidates
from licenseid.shorttext import EXACT_MATCH_SCORE, exact_id_match, match_short_text
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
    Method,
    RawMatch,
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
    manifest: list[list[str]]  # license_value_groups(): parsed once per call


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

    @contextlib.contextmanager
    def _database_errors(self) -> Iterator[None]:
        """Word a SQLite failure of a lookup as ``DatabaseNotReadyError``, so
        a caller tells a bad database from bad input (``InvalidInputError``)
        without catching ``sqlite3.Error``."""
        try:
            yield
        except sqlite3.Error as exc:
            raise lookup_error(str(self.db.db_path), exc) from exc

    def _try_explicit_id_match(self, license_id: str) -> list[RawMatch]:
        """Phase 1: resolve an explicit license_id argument to a match.

        A declaration names one license, so a compound expression, a license
        name and an SPDX URL are all a mistake to declare, not a value to
        resolve; a file's tag may still hold any of them. What is left goes
        through the resolver every other source of a license value uses, so
        an ID, a tag and a JSON field cannot answer differently.
        """
        if not license_id.strip():
            return []  # as for an empty license_id: nothing is declared
        if not is_simple_expression(license_id):
            raise invalid_id_error("license_id", license_id)
        return self._resolve_declared(license_id)

    def _resolve_declared(self, value: str) -> list[RawMatch]:
        """The answer to a declared license value: certain, or none."""
        return self._finalize_exact_markers(
            self.detector.resolve_license_value(value, 1.0), method="id"
        )

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
            manifest=license_value_groups(target_text, extension(file_path)),
        )

    def _try_tier0_5_markers(
        self, ctx: _MatchContext
    ) -> tuple[list[CandidateMatch], dict[str, float], list[RawMatch] | None]:
        """Tier 0.5: Marker Detection.

        Detects explicit license identifiers and context clues in the
        text. SPDX-License-Identifier is an unambiguous machine tag, so
        it's returned as a final answer (the third tuple element). All
        other markers (name fields, headings, first-line) go into the
        candidate pool and influence ranking via a confidence bonus.
        A very short input (< 30 words) is read only for what it declares, a
        manifest's license field or an SPDX-License-Identifier tag, which is
        certain: the other markers add overhead without benefit there, and
        Tier 0 handles the rest. A small package.json or a header line would
        otherwise be matched by name, and wrongly.
        """
        if ctx.word_count >= 30:
            marker_candidates = self.detector.detect(
                ctx.target_text, file_path=ctx.file_path, manifest=ctx.manifest
            )
        else:
            marker_candidates = self.detector.detect_declared(
                ctx.target_text, ctx.manifest
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

    def _try_tier0_short_text(self, ctx: _MatchContext) -> list[RawMatch] | None:
        """Tier 0: Short-Text Shortcut (Names/IDs).

        Threshold: inputs under 30 words (~200 chars) are likely bare IDs
        or short names and can be resolved via exact/fuzzy name matching
        without entering the FTS5 pipeline. Keeping this threshold low
        avoids routing ~50-word licence preambles (head_300 inputs)
        through the name matcher, which degrades recall for variant
        licences (e.g. MIT-STK, MIT-enna) where it returns the generic
        parent. A lone SPDX expression answers as license_id would.
        Returns None (fall through to Tier 1) for inputs at or above the
        threshold, or below it with no confident match.
        """
        if ctx.word_count >= 30:
            return None

        # A lone expression ("GPL-2.0+") is read as license_id reads it, so
        # text and ID answer alike: the normalised text has lost the "+",
        # and GPL-2.0 alone is GPL-2.0-only. A value that names no license
        # goes on to the name match.
        if is_simple_expression(ctx.target_text):
            declared = self._resolve_declared(ctx.target_text)
            if declared:
                return declared

        # Fast path: bare deprecated ID + prose disambiguation context in
        # the raw (un-normalised) text, e.g. "GPL-2.0 or later version".
        # Must use target_text, not norm_input, because normalize_text()
        # strips punctuation/case that the regex patterns rely on.
        disambiguated = disambiguate_deprecated_id(ctx.target_text)
        if disambiguated:
            details = self.db.get_license_details(disambiguated)
            match = exact_id_match(disambiguated)
            match["is_spdx"] = details["is_spdx"] if details else True
            match["is_osi_approved"] = details["is_osi_approved"] if details else False
            match["is_fsf_libre"] = details["is_fsf_libre"] if details else False
            return [match]

        short_matches = self._match_short_text(ctx.norm_input)
        if short_matches and short_matches[0]["score"] > 1.0:
            for m in short_matches:
                if "is_spdx" not in m:  # an expression (see shorttext)
                    flags = self.detector.license_flags(m["license_id"])
                    m["is_spdx"] = flags["is_spdx"]
                    m["is_osi_approved"] = flags["is_osi_approved"]
                    m["is_fsf_libre"] = flags["is_fsf_libre"]
            return short_matches

        return None

    def _without_tags(self, ctx: _MatchContext) -> _MatchContext:
        """A short *ctx* without its SPDX-License-Identifier tags. Tier 0.5
        read them, so one left named no license, and is neither a name nor
        text to match: "SPDX-License-Identifier: LicenseRef-MIT+" is not MIT.
        A long input keeps them: its tags are a small part of its text."""
        if ctx.word_count >= 30:
            return ctx
        text = self.detector.without_spdx_tags(ctx.target_text)
        if text == ctx.target_text:
            return ctx
        norm_input = normalize_text(text)
        return replace(
            ctx,
            target_text=text,
            norm_input=norm_input,
            word_count=len(norm_input.split()),
        )

    def _try_manifest_value(self, ctx: _MatchContext) -> list[RawMatch] | None:
        """Tier 0 on a manifest's license value that did not resolve as an ID,
        name or expression (Tier 0.5): "Apache 2.0" names Apache-2.0.

        A small manifest is not license text, so it is never matched by name
        as a whole (that answered Apache-1.0 for "Apache 2.0"): if it has no
        value, or its value names no license, there is no answer. A larger
        one goes on to Tiers 1 and 2 as before.
        """
        if not ctx.manifest:
            return None  # no manifest
        for value in (value for group in ctx.manifest for value in group):
            norm_value = normalize_text(value)
            result = self._try_tier0_short_text(
                replace(
                    ctx,
                    target_text=value,
                    norm_input=norm_value,
                    word_count=len(norm_value.split()),
                )
            )
            # Only an exact ID or name: "BSD" is a fuzzy match for 0BSD.
            if result and result[0]["score"] >= EXACT_MATCH_SCORE:
                # The field declares the exact hit, so nothing is measured
                # (as for a field Tier 0.5 resolved); a look-alike name after
                # it was only found by name.
                for match in result:
                    if match["exact"]:
                        match["method"] = "field"
                        match["similarity"] = None
                return result
        return [] if ctx.word_count < 30 else None

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
        Identify license text and return ranked matches, each with the same
        keys (see licenseid.types.LicenseMatch).
        Must provide exactly one of text, license_id, or file_path.
        Raises licenseid.errors.InvalidInputError: unknown option, binary file,
        or a license_id that names no single license (an AND/OR expression, a
        license name, an SPDX URL, prose).
        """
        # The one exit: every tier ranks on its raw score, and only here does
        # a result take its public form. One connection serves the call's
        # lookups, about five for each tag value, and the database is checked
        # once for a rebuild.
        with self._database_errors(), self.db.reading():
            raw = self._match_raw(
                text, license_id=license_id, file_path=file_path, **options
            )
        return [public_result(r) for r in raw]

    def _match_raw(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: str | None = None,
        **options: Any,
    ) -> Sequence[RawMatch | InternalMatch]:
        """match() before the public form: each tier's own records."""
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

        # A manifest field that names its license loosely ("Apache 2.0").
        field_result = self._try_manifest_value(ctx)
        if field_result is not None:
            return field_result

        # Tier 0: Short-Text Shortcut — bare IDs/names below the word
        # threshold are resolved without entering the FTS5 pipeline.
        # A short input is matched without its tags, read above: one left
        # named no license, and is no text to match.
        ctx = self._without_tags(ctx)
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

        return ranked

    def resolve_record(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: str | None = None,
    ) -> LicenseDetails | None:
        """Resolve the input to the record of its top match (score 0.85 or
        more), or None. The is_*() predicates and the CLI's is-* commands both
        answer from this, so they cannot disagree with match(), and raise
        what it raises. The bar reads the public score, as --threshold does:
        rounded to 4 places, so a raw 0.84995 passes."""
        with self._database_errors(), self.db.reading():
            results = self.match(text, license_id=license_id, file_path=file_path)
            if not results or results[0]["score"] < 0.85:
                return None
            top = results[0]
            record = self.db.get_license_details(top["license_id"])
        if record:
            return record

        # An expression (a WITH, an OR, a LicenseRef) is not a single DB row:
        # fall back to the flags match() already computed, not "unknown".
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

    def diff_pair(self, text: str, license_id: str) -> tuple[str, str]:
        """The two sides of a word diff of *text* against *license_id*: the
        normalised input Tier 2 read (a short one without its tags) and the
        part of the license's normalised text it aligned with. ("", "") if
        the license has no text. The alignment Tier 2 makes, made again for
        one license."""
        with self._database_errors(), self.db.reading():
            # A "WITH Font-exception-2.0" the License List has no row for is
            # ranked on its license's text (markers, the font-exception rule).
            details = self.db.get_license_details(
                license_id
            ) or self.db.get_license_details(license_id.split(" WITH ")[0])
            if not details:
                return "", ""
            ctx = self._build_match_context(text, None, cast(MatchRequest, {}))
            candidate = self.detector.to_candidate(details, 0.0)
        norm_input = self._without_tags(ctx).norm_input
        words = norm_input.split()
        _, _, window = calculate_base_similarity(
            norm_input, len(words), set(words), candidate, build_probe(words)
        )
        return norm_input, window

    def is_spdx(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is in the SPDX License List.

        Raises what match() raises.
        """
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_spdx", False)

    def is_osi(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved. Raises what match() raises."""
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_osi_approved", False)

    def is_fsf(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is FSF-libre. Raises what match() raises."""
        record = self.resolve_record(text, **kwargs)
        return record is not None and record.get("is_fsf_libre", False)

    def is_open(self, text: str | None = None, **kwargs: Any) -> bool:
        """True if the license is OSI-approved OR FSF-libre.

        Raises what match() raises.
        """
        record = self.resolve_record(text, **kwargs)
        if not record:
            return False
        return bool(
            record.get("is_osi_approved", False) or record.get("is_fsf_libre", False)
        )

    def _get_candidates(self, data: MatchRequest, text: str) -> list[CandidateMatch]:
        """Tier 1 retrieval for *text* (see licenseid.retrieval)."""
        return get_candidates(self.db, data, text)

    def _match_short_text(self, norm_input: str) -> list[RawMatch]:
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
                    method="text",
                    # The whole input is the License List's text, both
                    # normalised. Stricter than SPDX matching, which lets a
                    # copyright line differ (roadmap item 31). An input that
                    # normalises to nothing equals no text: a hinted
                    # candidate has none.
                    exact=bool(norm_input) and norm_input == cand.get("search_text"),
                    base_score=sim,
                    similarity=sim,
                    coverage=coverage,
                    pop_score=cand.get("pop_score", 0),
                    is_deprecated=cand.get("is_deprecated", False),
                    superseded_by=cand.get("superseded_by", ""),
                    best_window=best_window,
                    score=0.0,
                    is_spdx=bool(cand.get("is_spdx", False)),
                    is_osi_approved=bool(cand.get("is_osi_approved", False)),
                    is_fsf_libre=bool(cand.get("is_fsf_libre", False)),
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
        self, exact: list[CandidateMatch], method: Method | None = None
    ) -> list[RawMatch]:
        """Convert certain candidates to results: each found by its own
        method (a tag or a field), or by *method*. Nothing is measured."""
        # The detector keeps one candidate per license_id (_first_per_license).
        return [
            RawMatch(
                license_id=c["license_id"],
                method=method or c["method"],
                exact=True,
                score=1.0,
                similarity=None,
                coverage=None,
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

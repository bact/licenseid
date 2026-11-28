# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Aggregated license matching logic using hybrid search.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from typing_extensions import Unpack

from licenseid.candidates import as_matches
from licenseid.classify import is_pure_license_text
from licenseid.database import LicenseDatabase, snapshot, text_parts, text_source
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import check_database_ready, reject_blank_path, require_path
from licenseid.detectrequest import PathInput, check_request, target_text_of
from licenseid.errors import invalid_id_error
from licenseid.firsttext import settle_texts
from licenseid.identifiers import (
    is_qualified_plus,
    is_simple_expression,
)
from licenseid.idoptions import excluded_ids, free_text_hits, upgraded_options
from licenseid.looseid import (
    decide_ids,
    disambiguate_whole,
    loose_with,
    mark_guessed,
)
from licenseid.manifest import extension, license_value_groups
from licenseid.markerfloor import doubt_floors
from licenseid.markers import MarkerDetector
from licenseid.namehits import refusal_answer
from licenseid.normalize import normalize_text
from licenseid.ranking import apply_version_suffix_tiebreaker, ranking_key, under_found
from licenseid.resolvefirst import as_resolved, match_of, too_short, unread_url
from licenseid.resolver import resolve_with
from licenseid.resolvereason import is_plus_refusal, no_text_answer, refuses_text_match
from licenseid.resolverinfo import list_info
from licenseid.resolvertypes import Resolution
from licenseid.resolveurl import urls_as_ids
from licenseid.result import public_result
from licenseid.retrieval import (
    Candidates,
    add_free_text,
    get_candidates,
    text_candidates,
)
from licenseid.shorttext import (
    EXACT_MATCH_SCORE,
    exact_id_match,
    match_name_tier,
    match_version_key,
)
from licenseid.similarity import (
    boost_by_fingerprint,
    calculate_base_similarity,
    query_of,
    score_candidates,
    with_core,
)
from licenseid.textcandidates import TextCandidates
from licenseid.textnames import held_texts, input_texts, skipped
from licenseid.types import (
    CandidateMatch,
    Detection,
    DetectOptions,
    InternalMatch,
    LicenseFlags,
    RawMatch,
    Variant,
)
from licenseid.variants import DEFAULT, read_as, read_from, settle_free_text
from licenseid.wholetexts import Found
from licenseid.wordregion import WordRegions


@dataclass(frozen=True)
class _MatchContext:
    """Immutable per-call state threaded through detect()'s tiers. Built
    once after file/text resolution; read-only afterward. Not part of
    the public API. marker_candidates/marker_boosts live outside this
    context as explicit parameters instead, since they're a tier's
    *output* (Tier 0.5's) rather than a fixed, request-scoped input."""

    target_text: str
    file_path: str | None
    request: DetectOptions
    is_pure: bool
    norm_input: str
    word_count: int
    manifest: list[list[str]]  # license_value_groups(): parsed once per call


def _set_flags(match: RawMatch, flags: LicenseFlags) -> None:
    """Give *match* the SPDX, OSI and FSF *flags*."""
    match["is_spdx"] = flags["is_spdx"]
    match["is_osi_approved"] = flags["is_osi_approved"]
    match["is_fsf_libre"] = flags["is_fsf_libre"]


class LicenseDetector:
    """The detection pipeline: the whole input through ``resolve()``, then
    markers (Tier 0.5), IDs and names (Tier 0), word-gram recall (Tier 1) and
    RapidFuzz ranking (Tier 2)."""

    def __init__(
        self,
        db_path: PathInput | None = None,
        *,
        enable_popularity: bool = False,
    ):
        if db_path is not None:
            require_path(db_path, "db_path")
        else:
            db_path = get_default_db_path()
        reject_blank_path(db_path, "db_path")
        # Before LicenseDatabase, which opens the file (create=False below: it
        # must be there, and a lookup never makes one).
        check_database_ready(db_path)
        self.db = LicenseDatabase(db_path, create=False)
        self.markers = MarkerDetector(self.db)
        self.enable_popularity = enable_popularity

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
        # `--id` answers as the same argument does: an ID written loosely
        # ("GPL2"), then what only resolve() reads (the title ``CC0``).
        declared = (
            self._resolve_declared(license_id)
            or self._resolve_loose_with(license_id)
            or self._as_resolve_reads(license_id)
        )
        return declared or self._with_flags(match_version_key(self.db, license_id))

    def _with_flags(self, matches: list[RawMatch]) -> list[RawMatch]:
        """*matches*, each given the flags of its expression if it has none
        (an ID hit that answers another ID, see shorttext)."""
        for match in matches:
            if "is_spdx" not in match:
                _set_flags(match, self.markers.license_flags(match["license_id"]))
        return matches

    def _resolve_declared(self, val: str, *, resolved: bool = False) -> list[RawMatch]:
        """The answer to a declared license value: certain, or none."""
        found = self.markers.resolve_license_value(val, 1.0, resolved=resolved)
        return as_matches(found, method="id")

    def _resolve_loose_with(self, text: str) -> list[RawMatch]:
        """*text*, a license written loosely WITH an exception, answered as
        the expression of its ID (see looseid.loose_with); a decided variant
        is not exact, and is said once the expression resolves."""
        found = loose_with(self.db, text)
        if found is None:
            return []
        expression, loose = found
        declared = read_from(self._resolve_declared(expression), text)
        if declared and loose is not None:
            for match in declared:
                match["exact"] = False
                mark_guessed(match, text)
        return declared

    def _build_match_context(
        self, target_text: str, file_path: str | None, options: DetectOptions
    ) -> _MatchContext:
        """Phase 2 (cont.): classify content and build the immutable
        per-call state shared by the remaining tiers."""
        norm_input = normalize_text(target_text)
        return _MatchContext(
            target_text=target_text,
            file_path=file_path,
            request=options,
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
            marker_candidates = self.markers.detect(
                ctx.target_text, file_path=ctx.file_path, manifest=ctx.manifest
            )
        else:
            marker_candidates = self.markers.detect_declared(
                ctx.target_text, ctx.manifest
            )
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            return marker_candidates, {}, as_matches(spdx_exact)

        # Build a marker-boost map: license_id -> marker confidence score.
        # Used later in ranking to signal which candidates are
        # marker-confirmed.
        marker_boosts = {
            c["license_id"]: c.get("score", 0.0) for c in marker_candidates
        }
        return marker_candidates, marker_boosts, None

    def _try_tier0_short_text(
        self, ctx: _MatchContext, read: Resolution | None = None
    ) -> list[RawMatch] | None:
        """Tier 0: Short-Text Shortcut (Names/IDs).

        Inputs under 30 words (~200 chars) are likely bare IDs or short names:
        exact/fuzzy name matching answers them without Tiers 1 and 2. A
        low threshold keeps ~50-word licence preambles (head_300 inputs)
        away from the name matcher, which returns the generic parent of
        variant licences (MIT-STK, MIT-enna). A lone SPDX expression
        answers as license_id would. None (fall through to Tier 1) for
        inputs at or above the threshold, or below it with no confident match.
        *read* is what resolve() made of ``ctx.target_text`` in this call, if
        the caller has it: the value is not resolved a second time.
        """
        if ctx.word_count >= 30:  # a long text is matched whatever its "+" (C++)
            return None
        # What resolve() reads is the answer, whatever wraps it ("GPL-2.0+,",
        # a quoted field, a license written loosely WITH an exception).
        resolution = resolve_with(self.db, ctx.target_text) if read is None else read
        if resolution["expression"] is not None:
            return self._answer_of(resolution)
        return self._short_text_refused(ctx, resolution["reason"])

    def _short_text_refused(
        self, ctx: _MatchContext, reason: str | None
    ) -> list[RawMatch] | None:
        """Tier 0 for a short value resolve() refused, for *reason*. A "+"
        that is no operator gets no text match: normalize_text() drops it,
        so one would answer the licence round it, exact (item 44; from 10
        words on, Tier 1 matches the rest). A bare deprecated ID and its
        prose ("GPL-2.0 or later version") is read in the raw text, whose
        marks the readers judge. The rest is matched as ID or name unless
        normalize_text() would drop what it was refused for: a mark, an
        unpaired bracket, or a "+" ending a word (item 48), or a name hit
        that :mod:`licenseid.namehits` doubts (item 47)."""
        if is_plus_refusal(reason):
            return None
        disambiguated = disambiguate_whole(ctx.target_text, self.db)
        if disambiguated == "":
            return []  # resolve() refuses it ("GPL-2.0; or later"): no reading
        if disambiguated:
            match = read_from([exact_id_match(disambiguated)], ctx.target_text)[0]
            _set_flags(match, self.markers.license_flags(disambiguated))
            return [match]
        if refuses_text_match(reason, ctx.target_text):
            return no_text_answer(self.db, ctx.target_text, ctx.word_count)
        found, refused = match_name_tier(self.db, ctx.norm_input, ctx.target_text)
        if refused:  # a rule doubted a name hit that would have answered
            return refusal_answer(ctx.word_count)
        # A confident ID or name hit scores above 1; an expression has no flags.
        return self._with_flags(found) if found and found[0]["score"] > 1.0 else None

    def _without_tags(self, ctx: _MatchContext) -> _MatchContext:
        """A short *ctx* without its SPDX-License-Identifier tags. Tier 0.5
        read them, so one left named no license, and is neither a name nor
        text to match: "SPDX-License-Identifier: LicenseRef-MIT+" is not MIT.
        A long input keeps them: its tags are a small part of its text."""
        if ctx.word_count >= 30:
            return ctx
        text = self.markers.without_spdx_tags(ctx.target_text)
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
        one goes on to Tiers 1 and 2.
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
            # Only an exact ID or name, or a declared reading ("GPL-2.0+,",
            # a name resolve() reads): "BSD" is a fuzzy match for 0BSD.
            if result and (
                result[0]["score"] >= EXACT_MATCH_SCORE
                or result[0]["method"] == "id"
                or result[0]["similarity"] is None  # resolve() read it
            ):
                # The field declares the exact hit, or the ID it names
                # loosely, so nothing is measured (as for a field Tier 0.5
                # resolved); a look-alike name after it was only found by
                # name.
                for match in result:
                    # (a reading by a rule is no exact one, but is the field's)
                    if (
                        match["exact"]
                        or match["method"] == "id"
                        or match["similarity"] is None
                    ):
                        match.update({"method": "field", "similarity": None})
                        read_from([match], value)  # a declared value
                return result
        return [] if ctx.word_count < 30 else None

    def _run_tier1_and_tier2(
        self,
        ctx: _MatchContext,
        marker_candidates: list[CandidateMatch],
        marker_boosts: dict[str, float],
    ) -> tuple[list[InternalMatch], TextCandidates]:
        """Tier 1 (Broad Recall) retrieval + augmentation, then Tier 2
        (Precision Ranking), and the whole-text search of the input, which
        every reader of ``TEXTS`` shares. Never short-circuits detect()."""
        # The postings, the ids and the coded texts in one transaction.
        with snapshot(self.db):
            texts = text_candidates(self.db, ctx.target_text, ctx.norm_input)
            found = get_candidates(self.db, ctx.request, ctx.target_text, texts)
            candidates = found.found

            # Merge the marker candidates, then the hinted ones, not already
            # among the gram candidates, also when there are none. A prose
            # marker is free text: exclude drops it as it drops a Tier 1
            # candidate (a declaration never gets here).
            add_free_text(self.db, ctx.request, candidates, marker_candidates)
            if candidates:  # no candidate, no result to search the texts for
                texts.prepare([c["license_id"] for c in candidates])

        # Pass marker boosts and purity context so ranking can weight signals
        # appropriately: small additive bonus for pure text (similarity leads),
        # confidence floor for mixed content (marker is primary signal).
        ranked = self._rank_candidates(
            candidates,
            texts,
            ctx.request,
            marker_boosts=marker_boosts,
            is_pure=ctx.is_pure,
        )
        if found.narrowed is not None:  # its runner-ups rank under the text
            ranked = under_found(
                ranked, found.narrowed.group, found.narrowed.runner_ups
            )
        return ranked, texts

    def detect(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
        **options: Unpack[DetectOptions],
    ) -> list[Detection]:
        """
        Identify license text and return ranked matches, each with the same
        keys (see licenseid.types.Detection).

        Give exactly one of text, license_id or file_path. The *options*
        (licenseid.types.DetectOptions) are checked for every input but act
        only where licence text is matched, so an input answered whole
        ignores them (except ``variant``, which reads every input):
        exclude, hint, only_spdx and only_common on the candidates of
        Tier 1, and on the hinted ones (exclude alone also on markers and a
        short text's name hit),
        enable_popularity on the Tier 2 ranking and its tie-breaker. Raises
        :class:`TypeError` for a text or license_id that is no str, a
        file_path that is neither a str nor an os.PathLike of one, or an
        option of the wrong type (a flag that is no bool, an exclude or hint
        that is no list of str);
        licenseid.errors.InvalidInputError for none or two of the three, an
        unknown option, a text with a lone surrogate, a license_id that names
        no single license (an AND/OR expression, a license name, an SPDX URL,
        prose), or a file_path that is binary, missing or no readable file.
        An overlong licence ID, as license_id or in a text, is no match, not
        DatabaseNotReadyError, which means only that the database itself
        cannot be read.
        """
        # The one exit: every tier ranks on its raw score, and only here does
        # a result take its public form. One connection serves the call's
        # lookups, about five for each tag value, and the database is checked
        # once for a rebuild.
        with self.db.reading():
            raw = self._match_raw(
                text, license_id=license_id, file_path=file_path, **options
            )
            lists = [list_info(self.db, "database")]  # resolve()'s builder
            twins = {i: p.same_text for i, p in text_parts(self.db).items()}
        return [public_result(r, lists, twins) for r in raw]

    def _match_raw(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
        **options: Unpack[DetectOptions],
    ) -> Sequence[RawMatch | InternalMatch]:
        """detect() before the public form: each tier's own records."""
        file_path = check_request(text, license_id, file_path, options)
        return read_as(
            options.get("variant", DEFAULT),
            lambda: self._match_by(text, license_id, file_path, options),
        )

    def _match_by(
        self,
        text: str | None,
        license_id: str | None,
        file_path: str | None,
        options: DetectOptions,
    ) -> Sequence[RawMatch | InternalMatch]:
        """:meth:`_match_raw` of an input already checked, read as the
        variant in force says."""
        if license_id is not None:
            return self._try_explicit_id_match(license_id)

        target_text = target_text_of(text, file_path)
        if not target_text:
            return []
        # The whole input as one declared value first, so detect() and
        # resolve() answer it alike (resolvefirst).
        whole = resolve_with(self.db, target_text)
        if whole["expression"] is not None:
            return self._answer_of(whole)
        if unread_url(whole, target_text):  # a page is no text to match
            return []
        return self._match_text(
            self._build_match_context(target_text, file_path, options), whole
        )

    def _as_resolve_reads(self, value: str) -> list[RawMatch]:
        """*value* as resolve() reads it, or nothing if it refuses it."""
        resolution = resolve_with(self.db, value)
        if resolution["expression"] is None:
            return []
        return self._answer_of(resolution)

    def _answer_of(self, resolution: Resolution) -> list[RawMatch]:
        """The results of *resolution*'s expression, made what the resolution
        says (resolvefirst)."""
        expression = resolution["expression"] or ""
        text = urls_as_ids(self.db, resolution["input"])  # as a tag's value is
        found = read_from(self._resolve_declared(expression, resolved=True), text)
        if not found:  # no marker reader takes it: "MIT WITH AdditionRef-x"
            decided = decide_ids(self.db, expression)
            found = [match_of(decided, self.markers.license_flags(decided))]
            read_from(found, text)
            if decided != expression:  # a guess, said and not exact
                found[0]["exact"] = False
                mark_guessed(found[0], expression)
        return as_resolved(resolution, found)

    def _match_text(
        self, ctx: _MatchContext, whole: Resolution
    ) -> Sequence[RawMatch | InternalMatch]:
        """The tiers of an input resolve() did not read as a whole (*whole*):
        its markers, a manifest's field, Tier 0's names, then Tiers 1 and 2."""
        target_text = ctx.target_text

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
        # threshold are resolved without entering Tiers 1 and 2.
        # A short input is matched without its tags, read above: one left
        # named no license, and is no text to match.
        ctx = self._without_tags(ctx)
        # Free text from here: upgrade the options' deprecated IDs, once.
        ctx = replace(ctx, request=upgraded_options(ctx.request))
        if is_qualified_plus(ctx.target_text) or is_plus_refusal(whole["reason"]):
            # "GPL-2.0-only+", "MIT +": no license, nor a near one, whatever
            # the length once normalised; say why
            too_short(whole, ctx.norm_input, whole=ctx.target_text == target_text)
            return []
        # *whole* is the resolution of the input, unless a tag was taken out.
        short_text_result = self._try_tier0_short_text(
            ctx, whole if ctx.target_text == target_text else None
        )
        if short_text_result:  # a name hit is free text: exclude drops it
            excluded = excluded_ids(ctx.request.get("exclude", []))
            short_text_result = free_text_hits(short_text_result, excluded) or None
        pop = ctx.request.get("enable_popularity", self.enable_popularity)
        if short_text_result is not None:
            return settle_free_text(
                short_text_result,
                ctx.target_text,
                ctx.is_pure,
                ctx.request,
                popular=pop,
            )

        # Tier 1: Broad Recall, then Tier 2: Precision Ranking; not for a
        # short input resolve() refused (resolvefirst).
        if too_short(whole, ctx.norm_input, whole=ctx.target_text == target_text):
            return []
        ranked, texts = self._run_tier1_and_tier2(ctx, marker_candidates, marker_boosts)

        # Tiebreaker: -only vs -or-later when scores are identical
        ranked = apply_version_suffix_tiebreaker(
            ranked, ctx.target_text, ctx.is_pure, enable_pop=pop
        )
        settled = settle_free_text(
            ranked, ctx.target_text, ctx.is_pure, ctx.request, popular=pop
        )
        # In a file of several licence texts, a text answer stands only when
        # its text comes first (firsttext); its search gives TEXTS (none past
        # the bound of grams read).
        settled, found = settle_texts(settled, texts, self.db)
        return self._with_texts(settled, ctx, found)

    def _with_texts(
        self,
        settled: list[RawMatch | InternalMatch],
        ctx: _MatchContext,
        found: Found | None,
    ) -> list[RawMatch | InternalMatch]:
        """*settled*, each result given the List texts the input holds whole
        (``textnames``, from the search *found*): a fact about the input, so
        every result has it."""
        texts = held_texts(self.db, settled, ctx.request.get("variant", DEFAULT), found)
        if texts is not None:
            for match in settled:
                match["texts"] = texts
        return settled

    def texts(
        self,
        text: str | None = None,
        *,
        file_path: PathInput | None = None,
        variant: Variant = DEFAULT,
    ) -> list[str] | None:
        """The List IDs whose whole text (or core) the input holds, one per
        text, in the order the input gives them: ``TEXTS`` of a record of no
        answer. A group of licences
        with one text is named as ``detect()`` names a text whose variant is
        not stated under *variant*. None when no text is found, the input has
        under 40 tokens, or it is too large to search. Give one of *text* and
        *file_path*; raises what :meth:`detect` raises for them."""
        file_path = check_request(text, None, file_path, {"variant": variant})
        target_text = target_text_of(text, file_path)
        with snapshot(self.db):
            texts = text_candidates(self.db, target_text)
            return input_texts(self.db, texts, variant)

    def _resolve_record(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
    ) -> Detection | None:
        """The top match of the input (score 0.85 or more), or None. The
        is_*() predicates and the CLI's is-* commands both answer from this,
        so they cannot disagree with detect(), and raise what it raises. The
        bar reads the public score, as --threshold does: rounded to 4 places,
        so a raw 0.84995 passes."""
        with skipped():  # is-* never prints TEXTS
            results = self.detect(text, license_id=license_id, file_path=file_path)
        if not results or results[0]["score"] < 0.85:
            return None
        return results[0]

    def _diff_pair(self, text: str, license_id: str) -> tuple[str, str]:
        """The two sides of a word diff of *text* against *license_id*: the
        normalised input Tier 2 read (a short one without its tags) and the
        part of the license's normalised text it aligned with, widened to
        whole words. ("", "") if the license has no text. The alignment Tier
        2 makes, made again for one license."""
        with snapshot(self.db):
            # A "WITH Font-exception-2.0" the License List has no row for is
            # ranked on its license's text (markers, the font-exception rule).
            details = self.db.get_license_details(
                license_id
            ) or self.db.get_license_details(license_id.split(" WITH ")[0])
            if not details:
                return "", ""
            ctx = self._build_match_context(text, None, DetectOptions())
            candidate = with_core(
                self.markers.to_candidate(details, 0.0),
                text_parts(self.db).get(details["license_id"]),
            )
            norm_input = self._without_tags(ctx).norm_input
            # Read here, in the one transaction.
            corpus = text_source(self.db).corpus([details["license_id"]])
        regions = WordRegions(norm_input, lambda: corpus)
        query = query_of(norm_input, regions, snap=True)
        return norm_input, calculate_base_similarity(query, candidate)[2]

    def is_spdx(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
    ) -> bool | None:
        """True if every licence and exception of the license is on the SPDX
        License List (a ``LicenseRef-*`` is not); None when no license is
        found, as for every flag: not found is no "no". Takes and raises what
        detect() takes and raises, without its options."""
        record = self._resolve_record(text, license_id=license_id, file_path=file_path)
        return None if record is None else record["is_spdx"]

    def is_osi(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
    ) -> bool | None:
        """True if the license is OSI-approved; for an expression, every
        operand of an AND, any of an OR. None for no license, or when an
        operand not judged decides it (``MIT AND LicenseRef-x``, not ``MIT
        OR LicenseRef-x``). Takes and raises what :meth:`is_spdx` does."""
        record = self._resolve_record(text, license_id=license_id, file_path=file_path)
        return None if record is None else record["is_osi_approved"]

    def is_fsf(
        self,
        text: str | None = None,
        *,
        license_id: str | None = None,
        file_path: PathInput | None = None,
    ) -> bool | None:
        """True if the license is FSF-libre, judged as :meth:`is_osi` is.
        Takes and raises what :meth:`is_spdx` does."""
        record = self._resolve_record(text, license_id=license_id, file_path=file_path)
        return None if record is None else record["is_fsf_libre"]

    def _get_candidates(self, data: DetectOptions, text: str) -> Candidates:
        """Tier 1 retrieval for *text* (see licenseid.retrieval)."""
        return get_candidates(self.db, data, text)

    def _rank_candidates(
        self,
        candidates: list[CandidateMatch],
        texts: TextCandidates,
        data: DetectOptions,
        marker_boosts: dict[str, float] | None = None,
        is_pure: bool = True,
    ) -> list[InternalMatch]:
        """Rank candidates using dynamic sliding window and
        marker-boosted scoring; *texts* is the whole-text search of the
        normalised input (``TextCandidates.norm_input``)."""
        norm_input = texts.norm_input
        enable_popularity = data.get("enable_popularity", self.enable_popularity)
        parts = text_parts(self.db)
        # The candidates' texts, read at the first a word region is asked of
        # (already read where the caller prepared them).
        ids = [c["license_id"] for c in candidates]
        regions = WordRegions(norm_input, lambda: texts.scored(ids))
        ranked = score_candidates(
            [with_core(c, parts.get(c["license_id"])) for c in candidates],
            query_of(norm_input, regions),
            marker_boosts or {},
            is_pure,
            enable_popularity,
        )
        ranked = doubt_floors(ranked, texts, self.db)
        boost_by_fingerprint(ranked, self.db.find_fingerprint_hits(norm_input))
        ranked.sort(key=ranking_key(enable_popularity))
        return ranked

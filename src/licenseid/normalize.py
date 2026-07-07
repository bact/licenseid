# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""License text normalisation per SPDX License List Matching Guidelines.

Reference:
https://spdx.github.io/spdx-spec/v3.0.1/annexes/license-matching-guidelines-and-templates/
"""

import re
from typing import Final

from bs4 import BeautifulSoup

# Guideline 0 (practical): HTML detection heuristic.
# Closing tags (</p>, </div>, ...) appear only in real HTML — unlike opening
# tags, they are never used as plain-text placeholders such as <year> or
# <organization> that appear in license templates.
_HTML_TAG: Final = re.compile(r"</[a-z][a-z0-9]*\s*>", re.IGNORECASE)

# Guideline 2: Collapse any sequence of whitespace to a single space.
_WHITESPACE: Final = re.compile(r"\s+")

# Final punctuation sweep: remove anything left that is not alphanumeric or
# whitespace, after the specific equivalence normalisations below have run.
_NON_WORD: Final = re.compile(r"[^\w\s]")

# Guideline 4 (hyphens): any hyphen, dash, en dash, em dash, or similar
# variant is considered equivalent.  The final punctuation sweep (step 12)
# strips hyphens entirely regardless, so there is no information kept by
# preserving "-" as a distinct character — fold straight to a space here.
# This must include the plain ASCII hyphen-minus itself (not just the
# fancy Unicode variants), otherwise a hyphenated spelling such as
# "copyright-owner" survives varietal-word matching (step 11, which only
# matches space-separated phrases) on this pass, and only gets split into
# "copyright owner" by the final punctuation strip afterwards — causing a
# second call to normalize_text() to behave differently from the first
# (non-idempotent).  Folding hyphens to spaces here, before varietal
# matching runs, keeps normalize_text() idempotent.
_DASHES: Final = re.compile(r"[‐‑‒–—―−﹘﹣－-]")

# Guideline 4 (quotes): any variation of quotations is considered
# equivalent.  Normalise to ASCII single quote before stripping punctuation.
_QUOTES: Final = re.compile(
    r'["«»'  # " « »
    r"‘’"  # ' '
    r"‚‛"  # ‚ ‛
    r"“”"  # " "
    r"„‟"  # „ ‟
    r"‹›"  # ‹ ›
    r"′″‴"  # ′ ″ ‴
    r"ʹʺ"  # ʹ ʺ
    r"ʻʼʽ"  # ʻ ʼ ʽ
    r"]"
)

# Guideline 5a: code comment prefixes at the start of a line.
# Covers: // /* ** * # ' (VB) REM -- -} *)
_COMMENT_PREFIX: Final = re.compile(
    r"(?m)^[ \t]*"
    r"(?://|/\*+|\*\)"  # C/Java-style open & Pascal close
    r"|\*(?![\w*])"  # lone * continuation, but not ** or *word
    r"|#+"  # shell / Python / Markdown-as-comment
    r"|'(?=[ \t])"  # VB-style (apostrophe then space)
    r"|REM(?=[ \t])"  # BASIC
    r"|--(?=[ \t])"  # Lua / SQL / Haskell
    r"|-\})"  # Haskell block close
    r"[ \t]*"
)

# A second, narrower comment-prefix stripper for a different call site:
# matcher.py runs strip_comment_prefixes() on raw (not yet normalized) text
# before FTS5 indexing/querying, to improve recall on Type 5 (comment-
# wrapped) license notices — separately from _COMMENT_PREFIX above, which
# only runs inside normalize_text() itself as one step of the guideline
# pipeline.  They are intentionally not merged into one regex: this one
# covers fewer comment styles (no VB/BASIC/Lua/Haskell — not expected in
# the source files this targets) but additionally strips trailing "*/"
# block-comment closers, which _COMMENT_PREFIX has no equivalent for.
_LINE_COMMENT_PREFIX: Final = re.compile(
    r"^[ \t]*(?://+|#+|;+|\*(?!/)|/\*)[ \t]?",
    re.MULTILINE,
)
_BLOCK_COMMENT_CLOSER: Final = re.compile(r"^[ \t]*\*/[ \t]*$", re.MULTILINE)


def strip_comment_prefixes(text: str) -> str:
    """Remove leading comment characters from every line.

    Strips ``//``, ``#``, ``;``, ``*`` (Javadoc continuation), and
    ``/*`` prefixes.  Trailing ``*/`` block-comment closers are also
    removed.  Applied before FTS5 on source-file inputs to improve
    recall for Type 5 (comment-wrapped) license notices.
    """
    stripped = _LINE_COMMENT_PREFIX.sub("", text)
    stripped = _BLOCK_COMMENT_CLOSER.sub("", stripped)
    return stripped


# Guideline 5b: runs of 3+ identical non-alphanumeric characters used as
# visual separators (---, ===, ***, ___) carry no meaning.
_SEPARATOR: Final = re.compile(r"([^\w\s])\1{2,}")

# Guideline 6: bullets and list-item markers at the start of a line are
# ignored.  Covers symbol bullets, "1." / "a." / "1)" style, "(1)" / "(a)"
# style, and short roman numerals ("iv.").
_BULLETS: Final = re.compile(
    r"(?m)^[ \t]*"
    r"(?:"
    r"[*\-•◦‣▪▸]"  # symbol bullets
    r"|(?:[0-9]{1,3}|[a-zA-Z])[.)]"  # 1. / a. / 1) / a)
    r"|\([0-9]{1,3}\)|\([a-zA-Z]\)"  # (1) / (a)
    r"|[ivxlcdmIVXLCDM]{1,6}\."  # roman numerals
    r")"
    r"[ \t]+"
)

# Guideline 7: varietal word spelling.
# Generated from the official SPDX equivalent-words list
# (https://raw.githubusercontent.com/spdx/license-list-XML/main/equivalentwords.txt,
# format "canonical,variant"): each variant maps to its canonical form.
# "&" -> "and" is included here (guideline list entry "and,&") and must run
# before the final punctuation sweep would delete the ampersand.
_VARIETAL_WORDS: Final[dict[str, str]] = {
    "acknowledgment": "acknowledgement",
    "analogue": "analog",
    "&": "and",
    "analyse": "analyze",
    "artefact": "artifact",
    "authorisation": "authorization",
    "authorised": "authorized",
    "calibre": "caliber",
    "cancelled": "canceled",
    "capitalisations": "capitalizations",
    "catalogue": "catalog",
    "categorise": "categorize",
    "centre": "center",
    "copyright owner": "copyright holder",
    "emphasised": "emphasized",
    "favour": "favor",
    "favourite": "favorite",
    "fulfil": "fulfill",
    "fulfilment": "fulfillment",
    "initialise": "initialize",
    "judgment": "judgement",
    "labelling": "labeling",
    "labour": "labor",
    "licence": "license",
    "maximise": "maximize",
    "merchantibility": "merchantability",
    "modelled": "modeled",
    "modelling": "modeling",
    "non commercial": "noncommercial",
    "offence": "offense",
    "optimise": "optimize",
    "organisation": "organization",
    "organise": "organize",
    "per cent": "percent",
    "practise": "practice",
    "programme": "program",
    "realise": "realize",
    "recognise": "recognize",
    "signalling": "signaling",
    "sub license": "sublicense",
    "utilisation": "utilization",
    "whilst": "while",
    "wilful": "wilfull",
}

# Single-pass alternation over all variants.  Longest-first ordering so that
# multiword phrases ("copyright owner", "per cent") win over any single-word
# prefix; lookarounds instead of \b so the "&" entry (a non-word character)
# also anchors correctly.
_VARIETAL_RE: Final = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(v) for v in sorted(_VARIETAL_WORDS, key=len, reverse=True))
    + r")(?!\w)"
)

# Guideline 8: copyright symbol equivalence — © Ⓒ ⓒ and "(c)" are the same.
_COPYRIGHT_SYMBOL: Final = re.compile(r"[©Ⓒⓒ]")

# Guideline 9: copyright notices are not part of the matchable text.
# Two cases:
#   - © / (c) is always a notice cue;
#   - the bare word "copyright" is removed only when a further notice cue
#     (a digit, a copyright mark, or a <year>-style template placeholder)
#     appears within the next few words.  This guard is what keeps license
#     body sentences that merely contain the word "copyright" (e.g. CC0's
#     "Copyright and Related Rights ...") intact — not line position.
# Deliberately NOT anchored to line start ("^"): a real notice is very often
# preceded by something else on the same line — a source comment marker
# ("# Copyright ..."), a heading ("ISC License: Copyright ..."), or simply
# text whose original line breaks were removed by some upstream step (HTML
# flattening, a benchmark's character-distortion pass, a tool that
# rewraps paragraphs).  Anchoring to "^" made the rule silently no-op in
# all of these common cases.  The guard above is what discriminates real
# notices from body text, not position, so dropping the anchor is safe.
# The consumed span is bounded both by word count and by real newlines,
# whichever comes first:
#   - Word count, because some real license texts (confirmed in fixtures —
#     e.g. BSD-3-Clause) are stored as one long paragraph with almost no
#     internal newlines, so relying on "[^\n]*" alone is not a safe stand-in
#     for "the short notice sentence" — it can consume most of the document.
#   - Real newlines, because a plain word-count cap with no regard for line
#     breaks can equally overreach on genuinely short texts (confirmed in
#     fixtures — e.g. "fwlw") where a notice is followed a few real lines
#     later by unrelated grant language, all within the word budget.
# "(?:[ \t]+\S+)" (horizontal whitespace, not \s) is what enforces the
# newline stop: a "\n" can't satisfy "[ \t]+", so the repetition can't
# continue past one even when the word-count budget isn't exhausted.
_COPYRIGHT_NOTICE: Final = re.compile(
    r"(?:"
    r"(?:[©Ⓒⓒ]|\(c\))(?:[ \t]+\S+){0,25}"
    r"|copyright(?=[ \t]+(?:\S+[ \t]+){0,10}?\S*(?:\d|[©Ⓒⓒ]|\(c\)|<year>))"
    r"(?:[ \t]+\S+){0,25}"
    r")",
    re.IGNORECASE,
)

# Guideline 12: http:// and https:// are equivalent.
_HTTPS: Final = re.compile(r"https://")

# Guideline 9 (copyright notice removal) is implemented (_COPYRIGHT_NOTICE
# above) but OFF by default.  A full corpus benchmark (bench_compare.py,
# main vs a branch with this step enabled) showed a broad recall regression
# (-0.72% overall; worst on mixed content and Tier 0.5/Tier 1 recall,
# several categories down 5-7%). Disabling just this one step and
# re-running the same benchmark flipped the result to a net improvement
# (+0.51% overall). Root cause: this codebase's matching pipeline (FTS5 +
# RapidFuzz + word-level fingerprints) partly relies on copyright-notice
# boilerplate as *accidental* discriminative signal between near-duplicate
# license bodies (e.g. ISC vs Python-2.0) — guideline-9 compliance removes
# that signal faster than the rest of the pipeline can replace it.
# Revisit enabling this once there's a real (non-accidental) mechanism for
# that discrimination — e.g. fingerprints tuned to survive copyright
# removal, or better marker-based disambiguation — verified by re-running
# the full bench_compare before flipping the default.
_STRIP_COPYRIGHT_NOTICE: Final[bool] = False


def normalize_text(text: str) -> str:
    """Normalise license text per SPDX License List Matching Guidelines.

    Transformations, in order:

    1.  HTML to plain text (when HTML markup is detected).
    2.  Code comment prefix removal (guideline 5a).  Must run before
        copyright notice removal (step 3): a source-embedded notice like
        "# Copyright (c) ..." has the comment marker before the word
        "Copyright", so the notice's line-start anchor cannot match until
        the marker is gone.  Running these in the other order means
        comment-wrapped copyright headers — a very common real-world
        pattern — are silently never recognised as notices.
    3.  Copyright notice line removal (guideline 9) — OFF by default, see
        _STRIP_COPYRIGHT_NOTICE.
    4.  Repeated separator removal — --- / === / *** (guideline 5b).
    5.  Bullet and list-marker removal (guideline 6).
    6.  URL protocol normalisation — https:// to http:// (guideline 12).
    7.  Copyright symbol normalisation — © Ⓒ ⓒ to (c) (guideline 8).
    8.  Dash/hyphen normalisation — all variants (including plain "-")
        folded to a space (guideline 4).
    9.  Quote normalisation — all variants to "'" (guideline 4).
    10. Lowercasing (guideline 3).
    11. Whitespace collapse, ahead of schedule.  Steps 2-9 above are all
        line- or character-anchored and need real line breaks intact, but
        step 12 (varietal word spelling) matches literal space-separated
        phrases — a phrase split across a line break or joined by a
        (now-folded) hyphen would otherwise survive this pass and only
        get joined by the final whitespace collapse afterwards, making a
        second call to normalize_text() behave differently from the
        first.  Collapsing whitespace before step 12 avoids that.
    12. Varietal word spelling normalisation (guideline 7).
    13. Remaining punctuation removal.
    14. Final whitespace collapse (guideline 2) — punctuation removal in
        step 13 can reintroduce runs of spaces.

    Call once per raw input; do not feed the return value back in. With
    _STRIP_COPYRIGHT_NOTICE at its default (False), normalize_text() is
    idempotent (confirmed empirically over all fixture variants). If step
    3 is re-enabled, it stops being idempotent: copyright-notice detection
    is a bounded heuristic, not an exact parse of "the notice line" — it
    matches a "copyright"/"(c)"/"©" cue anywhere in the text (deliberately
    not anchored to line start — see the _COPYRIGHT_NOTICE comment for
    why) and then deletes up to 25 following words, stopping early only if
    a real newline is hit first. On ordinary multi-line input this
    reliably isolates just the notice. But because normalize_text()
    already collapses whitespace before its own return, a second call
    sees a single-line, punctuation-free string with no real newlines
    left as a stopping point — so the same 25-word cap can consume
    genuine body text following an unrelated occurrence of "copyright"
    instead of the just-emitted notice being gone already (confirmed:
    ~2% of fixture variants normalise differently on a second pass with
    the step enabled). Every caller in this codebase normalizes fresh raw
    text exactly once (see database.py, matcher.py); if you add a new
    caller, do the same rather than chaining through the result.
    """
    # 1. HTML to plain text.  Newline separator preserves line structure for
    # the line-based rules below (copyright notices, comments, bullets).
    if _HTML_TAG.search(text):
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator="\n")

    # 2. Code comment prefixes (per-line; must run before copyright notice
    # removal so a "# Copyright ..." header's line-start anchor is reachable)
    text = _COMMENT_PREFIX.sub("", text)

    # 3. Copyright notice removal (before lowercasing/punctuation strip so
    # the (c) / © / digit cues are still present).  See
    # _STRIP_COPYRIGHT_NOTICE for why this is off by default.
    if _STRIP_COPYRIGHT_NOTICE:
        text = _COPYRIGHT_NOTICE.sub("", text)

    # 4. Repeated separator characters
    text = _SEPARATOR.sub(" ", text)

    # 5. Bullets and list markers (per-line)
    text = _BULLETS.sub("", text)

    # 6. URL protocol
    text = _HTTPS.sub("http://", text)

    # 7. Copyright symbol
    text = _COPYRIGHT_SYMBOL.sub("(c)", text)

    # 8. Dashes / hyphens
    text = _DASHES.sub(" ", text)

    # 9. Quotes
    text = _QUOTES.sub("'", text)

    # 10. Case
    text = text.lower()

    # 11. Whitespace collapse (see docstring: must run before step 12)
    text = _WHITESPACE.sub(" ", text).strip()

    # 12. Varietal word spelling (single pass; input is lowercase by now)
    text = _VARIETAL_RE.sub(lambda m: _VARIETAL_WORDS[m.group(0)], text)

    # 13. Remaining punctuation
    text = _NON_WORD.sub(" ", text)

    # 14. Final whitespace collapse
    return _WHITESPACE.sub(" ", text).strip()

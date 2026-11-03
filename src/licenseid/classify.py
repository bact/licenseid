# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Content classification heuristics: what kind of input is this?

Pure regex-based text classification with no database or detector instance
dependency -- distinct from markers.py, which extracts license *identity*
from structured markers (headings, SPDX tags, field values). These
functions instead classify the input's *shape* (standalone license
document vs. source file/README; explicit -or-later grant present or not),
which LicenseDetector uses to choose a matching strategy. Where a grant
stands in an expression (:func:`grant_at`) and where one after an ID ends
(:func:`grant_end`, the one probe of both ``detect()`` and ``match()``) are
read here too.
"""

import bisect
import os
import re

from licenseid.dropguard import dropped
from licenseid.normalize import strip_comment_prefixes

# The phrases that grant "or any later version", the one detector for prose:
# the -only / -or-later tie-breaker (ranking), the bare-ID disambiguation
# (identifiers) and the GPL header marker (markers) all use it, so a header
# reads the same on every path.
#   - "or [(at your option)] a|any later": the words stand alone ("ora
#     later" is none, "or\b"). Comment
#     characters and commas may sit between them, so a header wrapped over
#     "// ", " * " or "# " lines is read.
#   - "or newer" on its own; "or later" only after a number ("version 2 or
#     later", "version 2 (or later)", "GPL-2.0+ or later"), or "sooner or
#     later" would count.
#   - "any later version" on its own, unless negated ("not any later version").
#   - "or-later" as a word of its own after a number ("GPL-2.0 or-later",
#     decision Q14); "or-later" inside an ID such as GPL-2.0-or-later is not
#     a phrase, as a hyphen or a letter stands right before it there.
# A word with an "i", "s" or "k" ignores case in ASCII only ("(?a:"):
# Python's IGNORECASE alone folds "\u0130", "\u0131", "\u017f" and the
# Kelvin sign into them (tests/test_readers_case.py). White space stays
# Unicode's.
_GAP = r"[\s/*#;,-]*"
# The words that take back a phrase right after them.
_NEGATIONS = ("not", "no")
_NOT_NEGATED = "".join(rf"(?<!\b{word} )" for word in _NEGATIONS)
_RE_NEGATED_END = re.compile(rf"\b(?:{'|'.join(_NEGATIONS)}) \Z", re.IGNORECASE)
OR_LATER_PHRASE = re.compile(
    rf"{_NOT_NEGATED}\bor\b{_GAP}"
    rf"(?:\([^)]{{0,50}}\){_GAP}|at\s+your\s+(?a:option){_GAP})?"
    rf"(?:a|any)\s{_GAP}(?:later|newer)\b"
    rf"|\d[\s,()\[\]+/*#;-]*\bor\s+later\b"
    rf"|\d[\s,()\[\]+/*#;-]*(?<![\w-])or-later\b"
    rf"|{_NOT_NEGATED}\bor\s+newer\b"
    rf"|{_NOT_NEGATED}\bany\s+later\s+(?a:version)\b",
    re.IGNORECASE,
)


# How far past the white space after its "or" a grant read after an ID may
# go (grant_end). Read as after a number, the phrase
# is "or", white space, then "later": a few characters past that run.
_GRANT_WINDOW = 200
# The qualifier an ID states at its end (plusoperator.states_qualifier).
_RE_STATED_QUALIFIER = re.compile(r"-(?:only|or-later)\Z", re.IGNORECASE | re.ASCII)


def grant_spans(text: str) -> tuple[list[int], list[int]]:
    """The starts and the ends of the "or later" phrases of *text*, for
    :func:`grant_at`."""
    spans = [m.span() for m in OR_LATER_PHRASE.finditer(text)]
    return [a for a, _ in spans], [b for _, b in spans]


def grant_at(
    text: str,
    operator: re.Match[str],
    spans: tuple[list[int], list[int]],
    qualified: bool,
) -> int | None:
    """The end of the "or later" grant the *operator* of an expression in
    *text* stands in, if it stands in one: a phrase of *spans*
    (:func:`grant_spans`), found by a binary search, not a scan, as a
    minified line can hold thousands of each. After a licence that states
    its qualifier (*qualified*), the operator is read as after a number, as
    ``match()`` reads a declared value (:func:`grant_end`), so "GPL-2.0-only
    or later" is a grant too, and a qualifier stated twice."""
    start = operator.start()
    index = bisect.bisect_right(spans[0], start) - 1
    if index >= 0 and start < spans[1][index]:
        return spans[1][index]
    return grant_end(text, start) if qualified else None


def grant_end(text: str, start: int) -> int | None:
    """Where the "or later" grant whose "or" is at *start* of *text* ends,
    or None if no grant starts there: the one reading of a grant after an
    ID, as after a number (a declared value has its ID before the "or";
    OR_LATER_PHRASE wants a number before a bare "or later", as prose also
    says "sooner or later"), unless a negation right before it takes it
    back ("not or later"). The compound reader of ``match()`` asks it at
    each "or" (decision Q14, through ``looseid``), the tag at an "or" after
    a licence that states its qualifier (:func:`grant_at`).

    The probe reads the white space after the "or" and a window past it,
    not the rest of the text: one probe per "or" must not copy the line
    ("A-only OR B-only OR ..." would be quadratic), and the runs after two
    "or"s do not overlap. The phrases that need no number are matched where
    they stand."""
    grant = OR_LATER_PHRASE.match(text, start)  # sees "not" before it
    if grant is not None:
        return grant.end()
    if is_negated(text[max(0, start - 5) : start]):  # "xnot ": enough to judge
        return None
    run_end = start + 2  # after the "or"
    while run_end < len(text) and text[run_end].isspace():
        run_end += 1
    probe = OR_LATER_PHRASE.match("1 " + text[start : run_end + _GRANT_WINDOW])
    return None if probe is None else start + probe.end() - 2


def grant_follows(tail: str, rest: str) -> bool | None:
    """Whether *rest*, the text after the last ID *tail* of an expression (a
    licence or its exception), grants "or later": the phrase in it with no
    number between the ID and the phrase, which would be another licence's.
    A qualifier the ID states is left off first, so "GPL-2.0-only (or
    later)" reads as "GPL-2.0 (or later)" does.

    An "or" after the ID, past white space and marks only, is read as after
    a number, by :func:`grant_end` ("MIT or later", "GPL-2.0, or later"), a
    phrase with no "or" where it stands ("MIT, any later version"), and what
    stands between is judged as ``match()`` judges it: white space,
    one "." or "," and a "(" or "[" before the "or" pass, and a mark it
    would drop (``MIT; or later``, ``MIT - or later``, ``MIT,or later``)
    makes the value no reading at all: None. Elsewhere a number the phrase
    starts with must be the ID's version (:func:`another_version`): in
    "GPL-2.0, version 3 or later" the grant is version 3's."""
    stem = _RE_STATED_QUALIFIER.sub("", tail)
    text = stem + rest
    bare = len(stem)  # past white space and marks, never a word
    while bare < len(text) and not text[bare].isalnum():
        bare += 1
    # A phrase with no "or" too ("MIT; any later version"), not a number's.
    if bare > len(stem) and not text[bare : bare + 1].isdigit():
        at_or = text[bare : bare + 2].lower() == "or"
        found = grant_end(text, bare) if at_or else OR_LATER_PHRASE.match(text, bare)
        if found is not None:
            return _kept(text[len(stem) : bare])
    grant = OR_LATER_PHRASE.search(text)
    if grant is None:
        return False
    start = grant.start()
    end = _number_start(text, start) if text[start].isdigit() else start
    return not any(char.isdigit() for char in text[len(stem) : end]) and not (
        another_version(stem, text, start)
    )


def grant_head(before: str) -> str | None:
    """*before*, the text before the "or" of a declared grant, without the
    white space and the "(" or "[" that stand right before the "or"; None
    if neither does ("MIT,or later": no word "or"). The one rule of
    ``looseid.declared_grant_id_text`` and of the gap a tag's grant crosses
    (:func:`grant_follows`)."""
    if not before or not (before[-1].isspace() or before[-1] in "(["):
        return None
    return before.rstrip().rstrip("([").rstrip()


_RE_LINE_BREAK = re.compile(r"\r\n?|\n")


def _kept(gap: str) -> bool | None:
    """True if ``match()`` reads past *gap*, what stands between an ID and
    the "or" of its grant (:func:`grant_head`, then ``dropguard`` judges
    the marks); None if it would drop one. A grant wrapped onto a comment
    line ("GPL-2.0\n * or later") is judged after the last line break, its
    comment prefix taken off: ``match()`` never sees a line break."""
    marks = grant_head(gap)
    lines = _RE_LINE_BREAK.split(gap)
    if marks is not None and len(lines) > 1:
        marks = grant_head(f" {strip_comment_prefixes(lines[-1])} ")  # a break
    return None if marks is None or dropped(f"x{marks}") else True


def another_version(licence: str, text: str, start: int) -> bool:
    """Whether the "or later" phrase at *start* of *text*, after *licence*,
    starts at a number that is no version of *licence*, so the grant is
    another licence's: "GPL-2.0, version 3 or later" grants version 3, and
    in "GPL-2.0, LGPL-2.0 or later" the number is joined to another word.
    "GPL-2.0, version 2.0 or later" restates its own. The phrase starts at a
    number when it reads "3 or later", at its last digit."""
    if not text[start].isdigit():
        return False
    begin = _number_start(text, start)
    if begin and (text[begin - 1].isalnum() or text[begin - 1] in "-_"):
        return True
    own = _RE_VERSION_NUMBER.findall(licence)
    return not own or _version(own[-1]) != _version(text[begin : start + 1])


_RE_VERSION_NUMBER = re.compile(r"\d+(?:\.\d+)*")


def _number_start(text: str, end: int) -> int:
    """Where the number whose last digit is at *end* of *text* starts."""
    begin = end
    while begin and (text[begin - 1].isdigit() or text[begin - 1] == "."):
        begin -= 1
    return begin


def _version(number: str) -> tuple[int, ...]:
    """*number* ("2.0", "2") as the parts of a version, with no zeros at the
    end: "2.0" and "2" are one version."""
    parts = [int(part) for part in number.split(".") if part]
    while len(parts) > 1 and not parts[-1]:
        parts.pop()
    return tuple(parts)


def is_negated(before: str) -> bool:
    """Whether a phrase right after *before* is taken back, as
    OR_LATER_PHRASE reads "not any later version"."""
    return _RE_NEGATED_END.search(before) is not None


# "GPLv2+" style notices; only meaningful in source files (the ID path reads
# "+" itself, with plusoperator.PLUS_OPERATOR). Prose, so a comma or a
# full stop may follow the "+"; otherwise it agrees with that reader, for the
# spellings Tier 0's version key accepts ("GPL 2+", "GPL-v2+", "GPL_2.0+"):
# a "+" touches its version and ends the word ("GPLv2++", "GPL-2.0+foo" are
# no grant). tests/test_plus_readers.py holds the two together.
_RE_OR_LATER_SHORTHAND = re.compile(
    r"(?:lgpl|gpl|agpl)(?:[-_ ]?v)?[-_ ]?\d+(?:\.\d+){0,2}\+(?![\w+])",
    re.IGNORECASE,
)

# Markdown section headers that indicate the surrounding document is a
# README/project file, not a standalone license document.
_RE_NON_LICENSE_SECTION = re.compile(
    r"^#{1,6}\s*"
    r"((?a:installation|usage|contributing|"
    r"prerequisites|requirements|setup|build|deploy|example|overview|features|"
    r"changelog|roadmap|faq|support|credits|acknowledgements?)|"
    r"(?a:getting)\s+(?a:started)|(?a:quick)\s+(?a:start)|"
    r"table\s+of\s+(?a:contents))",
    re.IGNORECASE,
)
# Openers that appear at the START of a full license document
# (not inside source files).
# "apache license" removed — too broad; it appears in license
# notice headers too.
# "mozilla public license" removed for the same reason.
# These files are caught by filename (LICENSE, COPYING) or by
# high FTS5 similarity.
_RE_LICENSE_OPENER = re.compile(
    r"(permission is hereby granted|permission to use, copy|"
    r"common development and distribution license|"
    r"creative commons attribution|redistribution and use in source|"
    r"everyone is permitted to copy)",
    re.IGNORECASE | re.ASCII,
)
# Positive signals that a file is SOURCE CODE, not a license document.
_RE_CODE_SIGNAL = re.compile(
    r"^(?:package\s+\w|import\s+\w|from\s+\w+\s+import\b|"
    r"#include\s+[<\"]|class\s+\w+[(\s{:]|public\s+class\s+\w|"
    r"def\s+\w+\s*\(|function\s+\w+\s*\()",
    re.MULTILINE,
)
# A numbered section: "1. Definitions". The indent is white space other
# than a line break: `\s*` after `^` reaches across line breaks, so a run of
# blank lines was scanned once per line (6 s of detect() at 20,000), as in
# licenseid.bsdclauses.
_RE_NUMBERED_SECTION = re.compile(r"^[^\S\r\n]*\d+\.\s+\w", re.MULTILINE)
_RE_MD_HEADER = re.compile(r"^#{1,6}\s+\S")


def has_or_later_language(text: str) -> bool:
    """Return True if text contains -or-later granting language.

    Only meaningful for non-pure input (source files, READMEs).  The GPL
    license body itself contains the same phrase in its 'How to Apply'
    appendix, so this must NOT be called on pure license text.
    """
    return bool(OR_LATER_PHRASE.search(text) or _RE_OR_LATER_SHORTHAND.search(text))


def is_pure_license_text(file_path: str | None, text: str) -> bool:
    """Return True if the content appears to be a standalone
    license document.

    Uses filename as a strong positive signal, then falls back to
    content heuristics so plain-text license input (no file_path) is
    also classified correctly.
    """
    if file_path:
        basename = os.path.basename(file_path).upper()
        if basename in (
            "LICENSE",
            "COPYING",
            "UNLICENSE",
            "LICENCE",
        ) or any(
            basename.startswith(p)
            for p in (
                "LICENSE.",
                "COPYING.",
                "LICENCE.",
            )
        ):
            return True

    if len(text.split()) < 30 or "```" in text or "~~~" in text:
        return False

    # Source code signals override other heuristics
    if _RE_CODE_SIGNAL.search(text[:2000]):
        return False

    md_headers = [line for line in text.splitlines() if _RE_MD_HEADER.match(line)]
    if len(md_headers) > 3 or any(_RE_NON_LICENSE_SECTION.match(h) for h in md_headers):
        return False

    # Positive indicators: numbered sections or known preamble.
    # Threshold >= 5 avoids mis-classifying BSD notices (3 conditions)
    # embedded in copyright headers as standalone license text.
    return len(_RE_NUMBERED_SECTION.findall(text)) >= 5 or bool(
        _RE_LICENSE_OPENER.search(text[:1000])
    )

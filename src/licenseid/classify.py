# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Content classification heuristics: what kind of input is this?

Pure regex-based text classification with no database or matcher instance
dependency -- distinct from markers.py, which extracts license *identity*
from structured markers (headings, SPDX tags, field values). These
functions instead classify the input's *shape* (standalone license
document vs. source file/README; explicit -or-later grant present or not),
which AggregatedLicenseMatcher uses to choose a matching strategy.
"""

import os
import re

# The phrases that grant "or any later version", the one detector for prose:
# the -only / -or-later tie-breaker (ranking), the bare-ID disambiguation
# (identifiers) and the GPL header marker (markers) all use it, so a header
# reads the same on every path.
#   - "or [(at your option)] a|any later": the words stand alone. Comment
#     characters and commas may sit between them, so a header wrapped over
#     "// ", " * " or "# " lines is read.
#   - "or newer" on its own; "or later" only after a number ("version 2 or
#     later", "version 2 (or later)", "GPL-2.0+ or later"), or "sooner or
#     later" would count.
#   - "any later version" on its own, unless negated ("not any later version").
# "or-later" inside an ID such as GPL-2.0-or-later is not a phrase.
_GAP = r"[\s/*#;,-]*"
_NOT_NEGATED = r"(?<!\bnot )(?<!\bno )"
OR_LATER_PHRASE = re.compile(
    rf"{_NOT_NEGATED}\bor{_GAP}"
    rf"(?:\([^)]{{0,50}}\){_GAP}|at\s+your\s+option{_GAP})?"
    rf"(?:a|any)\s{_GAP}(?:later|newer)\b"
    rf"|\d[\s,()\[\]+/*#;-]*\bor\s+later\b"
    rf"|{_NOT_NEGATED}\bor\s+newer\b"
    rf"|{_NOT_NEGATED}\bany\s+later\s+version\b",
    re.IGNORECASE,
)
# "GPLv2+" style notices; only meaningful in source files (the ID path reads
# "+" itself).
_RE_OR_LATER_SHORTHAND = re.compile(
    r"(?:lgpl|gpl|agpl)[-v]?\d+(?:\.\d+)?\+", re.IGNORECASE
)

# Markdown section headers that indicate the surrounding document is a
# README/project file, not a standalone license document.
_RE_NON_LICENSE_SECTION = re.compile(
    r"^#{1,6}\s*"
    r"(installation|usage|getting\s+started|contributing|"
    r"prerequisites|requirements|setup|build|deploy|example|"
    r"quick\s+start|table\s+of\s+contents|overview|features|"
    r"changelog|roadmap|faq|support|credits|acknowledgements?)",
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
    re.IGNORECASE,
)
# Positive signals that a file is SOURCE CODE, not a license document.
_RE_CODE_SIGNAL = re.compile(
    r"^(?:package\s+\w|import\s+\w|from\s+\w+\s+import\b|"
    r"#include\s+[<\"]|class\s+\w+[(\s{:]|public\s+class\s+\w|"
    r"def\s+\w+\s*\(|function\s+\w+\s*\()",
    re.MULTILINE,
)
_RE_NUMBERED_SECTION = re.compile(r"^\s*\d+\.\s+\w", re.MULTILINE)
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

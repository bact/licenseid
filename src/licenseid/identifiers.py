# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX Identifier and Expression normalization and validation.
"""

import re
from typing import cast

import py_spdx_license

from licenseid.database import LicenseDatabase

# Defensive cap on the number of AND/OR/WITH operators an expression may
# have before we attempt py_spdx_license's structural sort()/dedup pass.
# sort() has been observed to blow up well past polynomially — seconds of
# CPU time past roughly 150 unique AND/OR operands in an otherwise flat
# chain — for large expressions; this is not an SPDX grammar limit. Real
# SPDX expressions are virtually never this large, so expressions past the
# cap just skip canonicalization rather than risking a slow/blocking call
# on a pathological or adversarial one.
_MAX_CANONICALIZE_OPERATORS = 40

# Deprecated SPDX License IDs using the '+' expression token.
# The SPDX '+' operator means "or any later version" (SPDX Spec §10.1).
# These can be resolved to canonical form with certainty because the '+'
# unambiguously indicates the -or-later variant.
#
# Reference: SPDX Specification v3.0, Annex D — SPDX License Expressions
#   https://spdx.github.io/spdx-spec/v3.0/annexes/spdx-license-expressions/
DEPRECATED_SPDX_LICENSE_IDS: dict[str, str] = {
    "GPL-1.0+": "GPL-1.0-or-later",
    "GPL-2.0+": "GPL-2.0-or-later",
    "GPL-3.0+": "GPL-3.0-or-later",
    "LGPL-2.0+": "LGPL-2.0-or-later",
    "LGPL-2.1+": "LGPL-2.1-or-later",
    "LGPL-3.0+": "LGPL-3.0-or-later",
    "AGPL-1.0+": "AGPL-1.0-or-later",
    "AGPL-3.0+": "AGPL-3.0-or-later",
}

# Conservative last-resort fallback for bare deprecated IDs (no '+' suffix).
# These IDs are technically ambiguous: GPL-2.0 could be either GPL-2.0-only
# or GPL-2.0-or-later, as both share the same license text.  Strict resolution
# requires the granting declaration in the source file (e.g. "version 2 only"
# or "any later version").
#
# When no granting context is available this tool maps bare IDs to '-only'
# as the conservative interpretation, consistent with common practice in the
# FOSS ecosystem where an unqualified GPL-2.0 reference is usually treated as
# version-only.  This fallback is applied last, after DB and '+'-form checks.
DEPRECATED_BARE_LICENSE_IDS: dict[str, str] = {
    "GPL-1.0": "GPL-1.0-only",
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "LGPL-2.0": "LGPL-2.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPL-3.0": "LGPL-3.0-only",
    "AGPL-1.0": "AGPL-1.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
}

# Mapping of deprecated "-with-" IDs to their modern counterparts
DEPRECATED_WITH_IDS: dict[str, str] = {
    "GPL-2.0-with-font-exception": "GPL-2.0-only WITH Font-exception-2.0",
    "GPL-2.0-with-GCC-exception": "GPL-2.0-only WITH GCC-exception-2.0",
    "GPL-2.0-with-autoconf-exception": "GPL-2.0-only WITH Autoconf-exception-2.0",
    "GPL-2.0-with-bison-exception": "GPL-2.0-only WITH Bison-exception-2.2",
    "GPL-3.0-with-autoconf-exception": "GPL-3.0-only WITH Autoconf-exception-3.0",
    "GPL-3.0-with-GCC-exception": "GPL-3.0-only WITH GCC-exception-3.1",
}

# Lookup: bare deprecated ID → canonical or-later form.
# Derived from DEPRECATED_SPDX_LICENSE_IDS by stripping the trailing "+".
_BARE_TO_OR_LATER: dict[str, str] = {
    k[:-1]: v for k, v in DEPRECATED_SPDX_LICENSE_IDS.items()
}

# Compiled regexes for prose disambiguation of bare deprecated IDs.
# or-later patterns cover common GPL boilerplate phrasings:
#   "or later", "or any later", "or a later",
#   "or (at your option) any later", "or newer",
#   "any later version" (standalone)
# Reference: GPL preamble boilerplate and SPDX matching guidelines
_RE_OR_LATER = re.compile(
    r"\bor\s+(?:\([^)]{0,50}\)\s+)?(?:a\s+|any\s+)?(?:later|newer)\b"
    r"|\bany\s+later\s+version\b",
    re.IGNORECASE,
)
# "only" is a common English word; it is checked in a narrow 50-char window
# AFTER the ID to avoid false positives from unrelated uses.
_RE_ONLY = re.compile(r"\bonly\b", re.IGNORECASE)

# Tokenizer for SPDX license expressions: reserved operators/parens, or a
# run of identifier characters (letters, digits, dots, hyphens).
_RE_TOKEN = re.compile(r"\(|\)|AND|OR|WITH|\+|[a-zA-Z0-9.-]+", re.IGNORECASE)


def disambiguate_deprecated_id(text: str) -> str | None:
    """
    Scan *text* for a bare deprecated SPDX ID and a surrounding prose phrase
    that resolves the ``-only`` / ``-or-later`` ambiguity.

    Returns the canonical SPDX ID when a phrase is found::

        disambiguate_deprecated_id("GPL-2.0 or later version")
        # → "GPL-2.0-or-later"

        disambiguate_deprecated_id("GPL-2.0 only")
        # → "GPL-2.0-only"

    Returns ``None`` when no bare deprecated ID is present or when the ID is
    found but no disambiguating phrase exists in the surrounding text.  Callers
    should then apply the conservative ``DEPRECATED_BARE_LICENSE_IDS`` fallback.

    This function must be called *before* SPDX expression tokenisation because
    ``"or"`` in ``"or later"`` is prose, not an SPDX OR operator.
    """
    # Sort longest IDs first so e.g. "LGPL-2.1" is tried before "LGPL-2".
    for dep_id in sorted(DEPRECATED_BARE_LICENSE_IDS, key=len, reverse=True):
        # (?![\w-]) (not just \b) so a bare ID isn't matched as a prefix of
        # an already-canonical suffixed ID it's contained in, e.g. "GPL-2.0"
        # inside "GPL-2.0-only" or "GPL-2.0-or-later" — "\b" alone treats
        # the boundary before "-" as a word boundary and would match, then
        # the "-only"/"-or-later" suffix itself falsely satisfies the prose
        # disambiguation checks below. "." is deliberately not excluded here:
        # both real suffixes start with "-", and excluding "." too would
        # reject a bare ID immediately followed by sentence punctuation
        # (e.g. "...licensed under GPL-2.0. This version only.").
        m = re.search(r"\b" + re.escape(dep_id) + r"(?![\w-])", text, re.IGNORECASE)
        if not m:
            continue

        # Wide window (±150 chars) for or-later phrases, which can appear
        # several words before or after the ID.
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 150)
        window = text[start:end]
        if _RE_OR_LATER.search(window):
            return _BARE_TO_OR_LATER.get(dep_id)

        # Narrow window (50 chars after the ID) for "only" to reduce false
        # positives from common uses like "only if", "not only", etc.
        after = text[m.end() : m.end() + 50]
        if _RE_ONLY.search(after):
            return DEPRECATED_BARE_LICENSE_IDS[dep_id]

        # ID found but no disambiguating phrase — caller applies fallback.
        return None

    return None


def normalize_identifier(identifier: str, db: LicenseDatabase | None = None) -> str:
    """
    Normalises a single SPDX License ID or a full License Expression.
    """
    if not identifier:
        return identifier

    # Pre-check: bare deprecated ID + prose disambiguation context.
    # e.g. "GPL-2.0 or later version" → "GPL-2.0-or-later"
    # Must run before the AND/OR/WITH check because "or" in "or later" is
    # prose, not an SPDX OR operator.
    disambiguated = disambiguate_deprecated_id(identifier)
    if disambiguated:
        return disambiguated

    # 1. Handle full expression parsing if AND/OR/WITH/+/( are present as
    # genuine operators/parens, not merely as a substring of a single ID's
    # own name (e.g. the "or" in "GPL-2.0-or-later", or "and"/"or"/"with"
    # occurring inside a LicenseRef- name).
    if _is_expression(identifier):
        return _normalize_expression(identifier, db)

    # 2. Handle single ID normalization
    return _normalize_single_id(identifier, db)


# pylint: disable=too-many-branches
def _normalize_single_id(
    lic_id: str,
    db: LicenseDatabase | None = None,
) -> str:
    """Normalises a single license or exception ID."""
    # 1. Database lookup (most accurate/up-to-date)
    if db:
        mappings = db.get_deprecated_mappings()
        normalized = mappings.get(lic_id)
        if not normalized:
            # Case-insensitive search in mappings
            lic_id_upper = lic_id.upper()
            for dep_id, canonical in mappings.items():
                if dep_id.upper() == lic_id_upper:
                    normalized = canonical
                    break

        if normalized:
            return normalized

    # 2. Hardcoded fallback (fast path and legacy "+" conventions)
    normalized = DEPRECATED_SPDX_LICENSE_IDS.get(lic_id)
    lic_id_upper = lic_id.upper()

    if not normalized:
        for dep_id, canonical in DEPRECATED_SPDX_LICENSE_IDS.items():
            if dep_id.upper() == lic_id_upper:
                normalized = canonical
                break

    if not normalized:
        normalized = DEPRECATED_WITH_IDS.get(lic_id)
        if not normalized:
            lic_id_lower = lic_id.lower()
            for dep_id, canonical in DEPRECATED_WITH_IDS.items():
                if dep_id.lower() == lic_id_lower:
                    normalized = canonical
                    break

    if not normalized:
        # Conservative last resort: bare deprecated IDs default to '-only'.
        normalized = DEPRECATED_BARE_LICENSE_IDS.get(lic_id)
        if not normalized:
            for dep_id, canonical in DEPRECATED_BARE_LICENSE_IDS.items():
                if dep_id.upper() == lic_id_upper:
                    normalized = canonical
                    break

    if normalized:
        return normalized

    # 3. Canonical-case lookup: the DB uses COLLATE NOCASE, so we can retrieve
    # the correctly-cased ID for any known (non-deprecated) license.
    if db:
        details = db.get_license_details(lic_id)
        if details:
            return details["license_id"]

    # 4. '+'-suffixed ID not handled by any mapping (e.g. "CDDL-1.0+",
    # "Apache-2+"): strip '+', resolve the base to its canonical DB ID — first
    # by exact lookup, then by prefix — then re-attach '+'.
    # This preserves the "or later" intent for licenses whose '+' form is not
    # listed in DEPRECATED_SPDX_LICENSE_IDS.
    if lic_id.endswith("+") and db:
        base = lic_id[:-1]
        base_details = db.get_license_details(base)
        if not base_details:
            base_details = db.get_license_by_id_prefix(base)
        if base_details:
            return base_details["license_id"] + "+"

    return lic_id


def _normalize_exception_id(exc_id: str, db: LicenseDatabase | None = None) -> str:
    """Normalises a single SPDX License Exception ID (the right-hand side of
    a ``WITH`` operator).

    Unlike license IDs, exceptions have their own DB table
    (``get_exception_details`` / the exception half of
    ``get_deprecated_mappings``); looking them up via the license-oriented
    ``_normalize_single_id`` would never find a match and silently return the
    ID unchanged, including its casing.
    """
    if not db:
        return exc_id

    mappings = db.get_deprecated_mappings()
    normalized = mappings.get(exc_id)
    if not normalized:
        exc_id_upper = exc_id.upper()
        for dep_id, canonical in mappings.items():
            if dep_id.upper() == exc_id_upper:
                normalized = canonical
                break
    if normalized:
        return normalized

    details = db.get_exception_details(exc_id)
    if details:
        return details["exception_id"]

    return exc_id


def _tokenize_expression(expression: str) -> list[str]:
    """Tokenize an SPDX license expression into reserved tokens
    (``(``, ``)``, ``AND``, ``OR``, ``WITH``, ``+``) and identifiers.

    Identifiers can contain letters, numbers, dots, and hyphens; the
    identifier alternative's greedy ``+`` quantifier always consumes a full
    contiguous run of those characters starting from its first character,
    so a real ID that contains "and"/"or"/"with" as a substring of its own
    name (e.g. the "-or-later" suffix, or a custom LicenseRef- name) is
    always captured whole, never split at the embedded operator word.
    """
    return _RE_TOKEN.findall(expression)


def _is_expression(identifier: str) -> bool:
    """True if *identifier* is a real SPDX expression — contains AND/OR/WITH
    as a genuine operator, ``+``, or parentheses — rather than a single
    plain ID or unrecognised garbage.

    A plain substring check (e.g. ``"OR" in identifier.upper()``) misfires
    on single IDs that happen to contain "and"/"or"/"with" inside their own
    name (``GPL-2.0-or-later``, or a LicenseRef name like
    ``LicenseRef-BRANDing-1.0``). Tokenizing first avoids that: such names
    always come back as a single token.

    Checking for *any* reserved token — not just "more than one token" —
    also keeps malformed multi-word input with no real operator (e.g.
    ``"n M z"``, or whitespace-/symbol-only garbage, which tokenizes to
    zero tokens) on the single-ID passthrough path, matching the previous
    substring-check behaviour, rather than having it silently reformatted
    (or reduced to "") by ``_normalize_expression``.
    """
    return any(
        token in ("(", ")", "+") or token.upper() in ("AND", "OR", "WITH")
        for token in _tokenize_expression(identifier)
    )


def _normalize_expression(expression: str, db: LicenseDatabase | None = None) -> str:
    """Parses and normalises an SPDX License Expression."""
    tokens = _tokenize_expression(expression)

    # 1. Pre-process to attach "+" to identifiers
    # This ensures "GPL-2.0" "+" becomes "GPL-2.0+" before normalization
    combined_tokens = []
    i = 0
    while i < len(tokens):
        if (
            i + 1 < len(tokens)
            and tokens[i + 1] == "+"
            and tokens[i] not in ("(", ")", "AND", "OR", "WITH")
        ):
            combined_tokens.append(tokens[i] + "+")
            i += 2
        else:
            combined_tokens.append(tokens[i])
            i += 1

    normalized_tokens = []
    prev_upper = ""
    for token in combined_tokens:
        upper_token = token.upper()
        if upper_token in ("AND", "OR", "WITH"):
            normalized_tokens.append(upper_token)
        elif token in ("(", ")"):
            normalized_tokens.append(token)
        elif prev_upper == "WITH":
            # The right-hand side of WITH is an exception ID, not a license
            # ID — it has its own DB table/casing and must not be run
            # through the license-oriented normalizer.
            normalized_tokens.append(_normalize_exception_id(token, db))
        else:
            # It's an identifier (possibly with + already attached)
            normalized_tokens.append(_normalize_single_id(token, db))
        prev_upper = upper_token

    # Reconstruct the expression with proper spacing,
    # handling parentheses without extra spaces.
    expr = ""
    for i, part in enumerate(normalized_tokens):
        if i == 0:
            expr = part
        elif part == ")" or normalized_tokens[i - 1] == "(":
            expr += part
        else:
            expr += " " + part

    operator_count = sum(1 for t in normalized_tokens if t in ("AND", "OR", "WITH"))
    if operator_count > _MAX_CANONICALIZE_OPERATORS:
        return expr

    return _canonicalize_expression(expr)


def _canonicalize_expression(expr: str) -> str:
    """Best-effort structural canonicalization via ``py_spdx_license``.

    Builds a real AST from the (already ID-normalized) expression and uses
    its ``sort()`` to de-duplicate identical AND/OR operands and produce a
    consistent operand ordering (e.g. ``MIT AND MIT`` -> ``MIT``).

    ``py_spdx_license`` doesn't support every string ``_normalize_expression``
    can produce — notably the legacy ``license-id"+"`` form (e.g.
    ``CDDL-1.0+``) that has no ``-or-later`` equivalent — and its bundled
    license/exception list is a point-in-time snapshot that can lag behind
    this project's live-downloaded database. Any failure here just means the
    string keeps its original (non-deduplicated, non-reordered) form.

    The ``"+"`` limitation is tracked upstream at
    https://github.com/JPEWdev/py-spdx-license/issues/1 — once it's natively
    supported there, this fallback (and CDDL-1.0-style test cases) can be
    revisited.
    """
    try:
        ast = py_spdx_license.parse(expr, allow_unknown=True)
        return cast(str, ast.sort().to_string())
    except Exception:  # pylint: disable=broad-exception-caught
        return expr

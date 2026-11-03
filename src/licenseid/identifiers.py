# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX Identifier and Expression normalization and validation.
"""

import re
from itertools import dropwhile, pairwise
from typing import cast

import py_spdx_license

from licenseid.classify import (
    OR_LATER_PHRASE,
    another_version,
    grant_at,
    grant_follows,
    grant_spans,
)
from licenseid.deprecatedids import (
    BARE_TO_OR_LATER,
    DEPRECATED_BARE_LICENSE_IDS,
    DEPRECATED_SPDX_LICENSE_IDS,
    DEPRECATED_WITH_IDS,
)
from licenseid.dropguard import trim_end_mark
from licenseid.exprtokens import (
    OPERAND_START,
    OPERATORS,
    RE_OPERATOR,
    RE_TOKEN,
    canonical_ref,
    closing_brackets_end,
    continues_after,
    continues_word,
    cut_inside_word,
    is_license_ref,
    licence_after,
    token_kind,
)
from licenseid.listlookup import ListLookup
from licenseid.plusoperator import (
    LICENSE_REF_PREFIX,
    plus_after_qualifier,
    plus_apart,
    states_qualifier,
    strip_plus_operator,
)
from licenseid.versionkey import named_row

# Defensive cap on the number of AND/OR/WITH operators an expression may
# have before we attempt py_spdx_license's structural sort()/dedup pass.
# sort() has been observed to blow up well past polynomially — seconds of
# CPU time past roughly 150 unique AND/OR operands in an otherwise flat
# chain — for large expressions; this is not an SPDX grammar limit. Real
# SPDX expressions are virtually never this large, so expressions past the
# cap just skip canonicalization rather than risking a slow/blocking call
# on a pathological or adversarial one.
_MAX_CANONICALIZE_OPERATORS = 40

# Compiled regexes for prose disambiguation of bare deprecated IDs.
# The or-later phrases are read by classify.OR_LATER_PHRASE, shared with the
# -only / -or-later tie-breaker.
# "only" is a common English word; it is checked in a narrow 50-char window
# AFTER the ID to avoid false positives from unrelated uses. The "only" of
# an ID ("GPL-2.0-only") is that ID's, not a word about the one before it.
#: The prose word "only", never the end of an ID.
ONLY_WORD = re.compile(r"(?<![\w-])only\b", re.IGNORECASE)


def _lookup_case_insensitive(mapping: dict[str, str], key: str) -> str | None:
    """Look up *key* in *mapping*; if the exact-case lookup misses, retry
    with a case-insensitive scan (SPDX IDs are ASCII, so upper-casing
    both sides is safe)."""
    value = mapping.get(key)
    if value is not None:
        return value
    key_upper = key.upper()
    for candidate, mapped in mapping.items():
        if candidate.upper() == key_upper:
            return mapped
    return None


def normalize_operator_casing(expression: str) -> str:
    """Normalize the casing of SPDX operators (AND, OR, WITH) to uppercase,
    avoiding matching them inside license identifiers (like LGPL-2.0-or-later).
    """
    return RE_OPERATOR.sub(lambda m: m.group(0).upper(), expression)


# The most an expression may cost the parser, as the sum of its tokens'
# squared lengths. py_spdx_license's tokenizer is quadratic in a token's
# length (7 s at 1,000,000 characters); at this budget it takes about 8 ms
# (one token of 31,622 characters). SPDX sets no length on a LicenseRef-*,
# so a budget on the cost, not a cap on a token, keeps every real one. A
# workaround: drop it once the parser reads in linear time (tech-debt
# roadmap, item 26).
_MAX_PARSE_COST = 10**9
# A token as the parser sees it: a run between space, tab, line feed,
# carriage return and brackets. Not \s: the parser does not break at other
# white space (no-break space, vertical tab), so a run joined by it is one
# token there. "+" breaks there too; counting it in only refuses more.
_RE_PARSER_TOKEN = re.compile(r"[^ \t\n\r()]+")
# The largest expression read, in operators and in depth of brackets. The
# parser walks its tree by recursion, with no guard, so where it gives up
# depended on the interpreter: Python 3.10 at 335 operators in a row or 250
# brackets with an operator in each, Python 3.14 at 500 and 335. Under both,
# every supported version answers alike (tech-debt roadmap, item 19). Real
# expressions hold a few dozen operators at most.
MAX_PARSE_OPERATORS = 150
MAX_PARSE_DEPTH = 150
_RE_PARSER_PART = re.compile(r"[()]|[^ \t\n\r()]+")


def parse_expression(expression: str) -> py_spdx_license.Node | None:
    """Parse an SPDX license expression into a ``py_spdx_license`` tree, with
    any operator casing and any (unknown) IDs allowed; None if it is not a
    well-formed expression, or would cost the parser more than
    _MAX_PARSE_COST.

    Catches broadly, not just ``ParseError``: the parser is a plain recursive
    tree walk with no depth guard. An expression over MAX_PARSE_OPERATORS
    or MAX_PARSE_DEPTH is refused before it, so the answer does not depend
    on where the interpreter's recursion limit falls.
    """
    cost = sum(
        (token.end() - token.start()) ** 2
        for token in _RE_PARSER_TOKEN.finditer(expression)
    )
    if cost > _MAX_PARSE_COST or _too_large_to_parse(expression):
        return None
    try:
        return py_spdx_license.parse(
            normalize_operator_casing(expression), allow_unknown=True
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def parse_declared(value: str) -> py_spdx_license.Node | None:
    """Parse a declared *value*, its "+" operators read as the "or later" of
    the ID before them; None as parse_expression gives it, and for a "+"
    after a stated qualifier ("GPL-2.0-only+"), which no ID takes."""
    if plus_after_qualifier(value):
        return None
    return parse_expression(strip_plus_operator(value))


def is_qualified_plus(value: str) -> bool:
    """Whether *value*, whole (one end mark after it aside, as ``resolve()``
    reads ``GPL-2.0-only+,``), is shaped as an SPDX expression but for a "+"
    after a stated qualifier ("GPL-2.0-only+", "MIT OR GPL-2.0-or-later+").
    It names no license, so no license may answer in its place: a near name
    ("LGPL-3.0-only") is not what the value says either. Not parsed, so an
    expression too large to parse is one too."""
    value = value.strip()
    value = trim_end_mark(value) or value
    return plus_after_qualifier(value) and leading_expression(value) == value


def is_stray_plus(value: str) -> bool:
    """Whether *value*, whole (one end mark after it aside: ``MIT +,``), is
    one simple expression but for the "+" signs that end it, none of which
    is the operator: one apart from its ID (plusoperator.plus_apart:
    ``MIT +``, ``(MIT)+``) or more than one (``MIT++``, ``MIT + +``). It
    names no license, as ``resolve()`` refuses it (``malformed``): read
    without them, it would drop them in silence."""
    value = value.strip()
    value = trim_end_mark(value) or value
    end = len(value)  # past the "+" and white space at the end: no regex,
    while end and (value[end - 1].isspace() or value[end - 1] == "+"):
        end -= 1  # which a long run of spaces would make quadratic
    core = value[:end]
    if core == value:
        return False
    stray = plus_apart(value, len(value) - 1) or value[len(core) :].count("+") > 1
    return stray and is_simple_expression(core)


def _too_large_to_parse(expression: str) -> bool:
    """Whether *expression* holds more operators or deeper brackets than the
    parser is given (MAX_PARSE_OPERATORS, MAX_PARSE_DEPTH). One pass, which
    stops at the first part over either."""
    operators = depth = 0
    for part in _RE_PARSER_PART.finditer(expression):
        word = part.group(0)
        if word == "(":
            depth += 1
        elif word == ")":
            depth -= 1
        elif word.upper() in OPERATORS:
            operators += 1
        if operators > MAX_PARSE_OPERATORS or depth > MAX_PARSE_DEPTH:
            return True
    return False


def qualify_trailing_grant(expression: str, value: str) -> str:
    """*expression* with the ID it ends in qualified "or later", when the
    prose right after it in *value* grants it: a bare deprecated ID by its
    ``-or-later`` form, any other by the "+" operator ("MIT or later" is
    MIT+, as ``resolve()`` reads it, P35). One that takes no grant (``-only``,
    a reference) is left as it is; a tag refused it (leading_expression).

    "or later" is a grant, not the OR operator, and it qualifies the ID
    beside it: "MIT OR GPL-2.0 or later" is "MIT OR GPL-2.0-or-later". The
    grant of a WITH belongs to its license, not to its exception. A version
    number between the ID and the grant means another license stands in
    between, so the grant is that one's (classify.grant_follows). A mark
    between the ID and its grant that ``resolve()`` would drop (``MIT; or
    later``) leaves no expression: ``""``."""
    # Closing brackets stand between the ID and the grant: "(GPL-2.0) or later".
    tokens = [t for t in RE_TOKEN.finditer(expression) if t.group(0) != ")"]
    if not tokens:
        return expression
    target = tokens[-1]
    if len(tokens) >= 3 and tokens[-2].group(0).upper() == "WITH":
        target = tokens[-3]
    licence = target.group(0)
    if token_kind(licence) != "ID" or _takes_no_grant(licence):
        return expression  # a "+" before the grant, or no licence takes one
    # The expression is a prefix of the value up to its last ID; the closing
    # brackets it has come next, and any other one is a mark ("MIT) or").
    rest = value[tokens[-1].end() :]
    closed = closing_brackets_end(rest, 0, expression.count(")", tokens[-1].end()))
    follows = grant_follows(tokens[-1].group(0), rest[closed or 0 :])
    if follows is None:
        return ""  # a mark resolve() would drop: no reading at all
    if not follows:
        return expression
    or_later = _lookup_case_insensitive(BARE_TO_OR_LATER, licence) or f"{licence}+"
    return expression[: target.start()] + or_later + expression[target.end() :]


def _takes_no_grant(licence: str) -> bool:
    """Whether *licence* states its qualifier or is a reference."""
    return states_qualifier(licence) or LICENSE_REF_PREFIX.match(licence) is not None


def _ended_by_grant(value: str, ends: tuple[int, int], depth: int, licence: str) -> str:
    """:func:`leading_expression` of *value* that ends at ``ends[0]``, before
    a grant that ends at ``ends[1]``, in *depth* brackets, after *licence*.
    The grant qualifies the ID before it (qualify_trailing_grant), so it
    ends the expression; a value that goes on past it (operands would be
    lost), or a grant after a stated qualifier, is no evidence at all."""
    close_end = closing_brackets_end(value, ends[1], depth)
    if (
        close_end is None
        or continues_after(value, close_end)
        or _takes_no_grant(licence)
    ):
        return ""
    return value[: ends[0]] + ")" * depth


def leading_expression(value: str) -> str:
    """The longest prefix of *value* that can still be an SPDX expression.

    A tag runs to the end of its line, so its value can trail off into prose
    ("CAL-1.0 Licensed under the ..."). Only AND, OR and WITH join two parts,
    so a token none of them bridges ends the expression. A value that ends
    dangling, or with unbalanced brackets, is no expression at all: answering
    with a shorter prefix of one would name a license the value does not.

    An "or later" grant ends the expression, but not the brackets it stands
    in: "(GPL-2.0 or later)" gives "(GPL-2.0)", for qualify_trailing_grant.
    An "or" is read as after a number (``MIT or later`` is a grant, as
    ``resolve()`` reads it, not MIT OR a licence "later"), but after a "+":
    "GPL-2.0-only+ or later" is refused for its "+" (``is_qualified_plus``).
    After an ID that states its qualifier (``GPL-2.0-only or later``) the
    grant states a second: no expression, as ``resolve()`` refuses it. An ID
    cut inside a word (``LicenseRef-café``) is no expression either
    (:func:`licenseid.exprtokens.cut_inside_word`).
    """
    # "or any later version" is a grant, not the OR operator, and the phrase
    # can start before the "or" ("GPL-2.0 or later" needs the version).
    grants = grant_spans(value)
    depth = 0
    expect_operand = True
    complete = None  # end of the longest complete, bracket-balanced prefix
    end = 0
    licence = before = ""  # the last licence (no exception), the last token
    for token in RE_TOKEN.finditer(value):
        kind = token_kind(token.group(0))
        if expect_operand != (kind in OPERAND_START):
            break
        gap = value[end : token.start()]
        if gap.strip():
            break  # only white space separates the parts of an expression
        if kind == "+" and plus_apart(value, token.start()):
            # A "+" touches the ID it follows (plusoperator.PLUS_OPERATOR);
            # after a space or a bracket it is none, and may say "and": no
            # expression, as resolve() refuses it, rather than one without it.
            return ""
        grant_end = (
            grant_at(value, token, grants, before != "+") if kind == "OP" else None
        )
        if grant_end is not None and not continues_word(value, grant_end):
            return _ended_by_grant(value, (end, grant_end), depth, licence)
        licence = licence_after(licence, before, token)
        before = token[0]
        end = token.end()
        if kind == "(":
            depth += 1
        elif kind == ")":
            if not depth:
                break
            depth -= 1
        if kind in ("ID", "OP"):
            expect_operand = kind == "OP"
        if not depth and not expect_operand:
            complete = token.end()
    if expect_operand or depth or complete is None or cut_inside_word(value, complete):
        return ""
    return "" if _granted_twice(value[:complete], value, licence) else value[:complete]


def _granted_twice(expression: str, value: str, licence: str) -> bool:
    """Whether the prose after *expression*, a prefix of *value* whose last
    licence is *licence*, grants "or later" to a licence that takes none
    (``GPL-2.0-only, or any later version``, ``LicenseRef-a (or later)``)."""
    if not _takes_no_grant(licence):
        return False
    tail = [t for t in RE_TOKEN.finditer(expression) if t.group(0) != ")"][-1]
    return grant_follows(tail[0], value[tail.end() :]) is not False


# An ID, then at most one "+", then at most one WITH an exception.
_SIMPLE_SHAPES = (
    ("ID",),
    ("ID", "+"),
    ("ID", "WITH", "ID"),
    ("ID", "+", "WITH", "ID"),
)


def is_simple_expression(value: str) -> bool:
    """Whether *value* names one license: an ID, optionally with "+" (not
    after ``-only`` or ``-or-later``), or a ``LicenseRef-*``, either ``WITH``
    an exception, in any number of brackets.

    What a declaration may hold. A tag carries whatever its author wrote, but
    "MIT OR Apache-2.0" declares neither license, and a name or an SPDX URL
    is not an ID, so those are a mistake to declare rather than a value to
    resolve.
    """
    value = value.strip()
    if not value or leading_expression(value) != value:
        return False
    if plus_after_qualifier(value):
        return False  # "GPL-2.0-only+": no ID takes both
    tokens = [token.group(0) for token in RE_TOKEN.finditer(value)]
    if any(
        token == "+" and LICENSE_REF_PREFIX.match(before)
        for before, token in pairwise(tokens)
    ):
        return False  # a LicenseRef takes no "+"
    shape = tuple(
        "WITH" if token.upper() == "WITH" else token_kind(token) for token in tokens
    )
    # SPDX allows brackets around any expression: "(MIT)" is MIT. The value
    # is balanced (leading_expression), and a simple shape holds no bracket,
    # so all the leading ones must pair with as many trailing ones.
    pairs = len(shape) - len(tuple(dropwhile(lambda kind: kind == "(", shape)))
    if pairs and shape[len(shape) - pairs :] == (")",) * pairs:
        shape = shape[pairs : len(shape) - pairs]
    return shape in _SIMPLE_SHAPES


def simple_value(text: str) -> str | None:
    """*text* as one simple expression, or without the one end mark after it
    ("GPL-2.0+," is GPL-2.0+, as a tag and ``resolve()`` read it), or None.
    The mark goes, not the "+" before it: the version key would read
    "GPL-2.0+," as GPL-2.0."""
    if is_simple_expression(text):
        return text
    trimmed = trim_end_mark(text)
    return trimmed if trimmed is not None and is_simple_expression(trimmed) else None


def disambiguate_deprecated_id(text: str) -> str | None:
    """
    Scan *text* for a bare deprecated SPDX ID and a surrounding prose phrase
    that resolves the ``-only`` / ``-or-later`` ambiguity.

    Returns the canonical SPDX ID when a phrase is found::

        disambiguate_deprecated_id("GPL-2.0 or later version")
        # → "GPL-2.0-or-later"

        disambiguate_deprecated_id("GPL-2.0 only")
        # → "GPL-2.0-only"

    ``None`` for no bare deprecated ID, or no phrase about it: the caller
    applies the conservative ``DEPRECATED_BARE_LICENSE_IDS`` fallback. Call
    it *before* SPDX expression tokenisation: "or later" is prose, not OR.
    """
    bare = bare_deprecated(text)
    if bare is None:
        return None
    dep_id, m = bare
    # Wide window (±150 chars) for or-later phrases, which can appear
    # several words before or after the ID.
    start = max(0, m.start() - 150)
    end = min(len(text), m.end() + 150)
    window = text[start:end]
    grant = OR_LATER_PHRASE.search(window)
    if grant:  # a phrase after another version is another licence's
        phrase = (start + grant.start(), start + grant.end())
        other = phrase[0] >= m.end() and another_version(dep_id, text, phrase[0])
        if other or _joins_another(text, phrase):
            return None
        return BARE_TO_OR_LATER.get(dep_id)

    # Narrow window (50 chars after the ID) for "only" to reduce false
    # positives from common uses like "only if", "not only", etc.
    only = ONLY_WORD.search(text, m.end(), m.end() + 50)
    if only:
        if _joins_another(text, only.span()):
            return None
        return DEPRECATED_BARE_LICENSE_IDS[dep_id]

    # ID found but no disambiguating phrase — caller applies fallback.
    return None


def bare_deprecated(text: str) -> tuple[str, re.Match[str]] | None:
    """The first bare deprecated ID of *text* (DEPRECATED_BARE_LICENSE_IDS),
    the longest tried first, and where it is."""
    for dep_id in sorted(DEPRECATED_BARE_LICENSE_IDS, key=len, reverse=True):
        m = _bare_id(dep_id).search(text)
        if m:
            return dep_id, m
    return None


def _bare_id(dep_id: str) -> re.Pattern[str]:
    """*dep_id* as a word of its own: no word character or "-" after it, so
    "GPL-2.0" is not found in "GPL-2.0-only", whose suffix would read as the
    phrase; a "." may follow ("GPL-2.0. This version only."), not a "+"."""
    pattern = r"(?<![\w.:-])" + re.escape(dep_id) + r"(?![\w+-])"
    return re.compile(pattern, re.IGNORECASE)


def _joins_another(text: str, phrase: tuple[int, int]) -> bool:
    """Whether an operator outside *phrase* (the span of the qualifier
    read) joins another licence to the ID: then the phrase qualifies one
    operand, and answering it alone would drop the others ("MIT AND GPL-2.0
    only" is not GPL-2.0-only). The "or" of "or later" is the phrase's own."""
    return any(
        not phrase[0] <= op.start() < phrase[1] for op in RE_OPERATOR.finditer(text)
    )


def names_only_listed(expression: str, db: ListLookup) -> bool:
    """Whether each ID of *expression* is a licence or an exception of the
    List, or a reference: a word that is none ("later", the "Apache" of
    "Apache 2.0", a typo) is no operand to answer, as ``resolve()`` refuses
    it, not an unknown licence to keep."""
    return all(
        token_kind(token) != "ID"
        or is_license_ref(token)
        or db.get_license_details(token) is not None
        or db.get_exception_details(token) is not None
        for token in RE_TOKEN.findall(expression)
    )


def normalize_identifier(identifier: str, db: ListLookup | None = None) -> str:
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


def _normalize_single_id(
    lic_id: str,
    db: ListLookup | None = None,
) -> str:
    """Normalises a single license or exception ID. A reference names
    itself, its prefixes in SPDX's case (``licenseref-x`` is
    ``LicenseRef-x``), as ``resolve()`` reads it."""
    if is_license_ref(lic_id):
        return canonical_ref(lic_id)
    # 1. List lookup (most accurate/up-to-date)
    if db is not None:
        normalized = _lookup_case_insensitive(db.get_deprecated_mappings(), lic_id)
        if normalized:
            return normalized

    # 2. Hardcoded fallback (fast path and legacy "+" conventions)
    normalized = _lookup_case_insensitive(DEPRECATED_SPDX_LICENSE_IDS, lic_id)

    if not normalized:
        normalized = _lookup_case_insensitive(DEPRECATED_WITH_IDS, lic_id)

    if not normalized:
        # Conservative last resort: bare deprecated IDs default to '-only'.
        normalized = _lookup_case_insensitive(DEPRECATED_BARE_LICENSE_IDS, lic_id)

    if normalized:
        return normalized

    # 3. Canonical-case lookup: the DB uses COLLATE NOCASE, so we can retrieve
    # the correctly-cased ID for any known (non-deprecated) license.
    if db is not None:
        details = db.get_license_details(lic_id)
        if details:
            return details["license_id"]

    # 4. '+'-suffixed ID not handled by any mapping (e.g. "CDDL-1.0+",
    # "Apache-2+", "GPL-2+"): see _plus_id.
    if lic_id.endswith("+") and db is not None:
        return _plus_id(lic_id, db) or lic_id

    return lic_id


def _plus_id(lic_id: str, db: ListLookup) -> str | None:
    """*lic_id*, an ID and a "+", with its base read by ID or as a loosely
    written ID ("Apache-2", "GPL-2"), as resolve() reads it; never by a bare
    prefix, which made "MI+" MIT+. The "+" becomes the base's -or-later ID
    where the List has one in use ("GPL-2+" is GPL-2.0-or-later), and stays
    otherwise ("Apache-2+" is Apache-2.0+), after the rename of a deprecated
    base, as resolve() follows it ("StandardML-NJ+" is SMLNJ+). None for no
    base, or one that states its qualifier already ("GPL-2.0-only+"): no
    valid ID takes it. A deprecated ID with an exception in it gives the "+"
    to its licence ("GPL-2.0-with-classpath-exception+" is GPL-2.0-or-later
    WITH Classpath-exception-2.0), a reading resolve() does not make
    (``looseid.read_inexactly``)."""
    base = lic_id[:-1]
    redirect = _lookup_case_insensitive(DEPRECATED_WITH_IDS, base)
    if redirect is not None:
        licence, exception = redirect.split(" WITH ")
        granted = _plus_id(licence.removesuffix("-only") + "+", db)
        return None if granted is None else f"{granted} WITH {exception}"
    details = db.get_license_details(base)
    if details is None:
        row = named_row(db, base)
        if row is None:
            return None
        found = row["license_id"]
    else:
        found = details["license_id"]
    if found.endswith(("-only", "-or-later", "+")):
        return None
    or_later = db.get_license_details(f"{found}-or-later")
    if or_later is not None:
        return or_later["license_id"]
    renamed = _lookup_case_insensitive(db.get_deprecated_mappings(), found)
    return f"{renamed or found}+"


def _normalize_exception_id(exc_id: str, db: ListLookup | None = None) -> str:
    """Normalises a single SPDX License Exception ID (the right-hand side of
    a ``WITH`` operator).

    Unlike license IDs, exceptions have their own DB table
    (``get_exception_details`` / the exception half of
    ``get_deprecated_mappings``); looking them up via the license-oriented
    ``_normalize_single_id`` would never find a match and silently return the
    ID unchanged, including its casing.
    """
    if db is None:
        return exc_id

    normalized = _lookup_case_insensitive(db.get_deprecated_mappings(), exc_id)
    if normalized:
        return normalized

    details = db.get_exception_details(exc_id)
    if details:
        return details["exception_id"]

    return exc_id


def _is_expression(identifier: str) -> bool:
    """True if *identifier* is a real SPDX expression — contains AND/OR/WITH
    as a genuine operator, ``+``, or parentheses — rather than a single
    plain ID or unrecognised garbage. Tokens, not substrings: "or" inside
    ``GPL-2.0-or-later`` or ``LicenseRef-BRANDing-1.0`` is no operator. Any
    reserved token, not "more than one token": multi-word input with no
    operator (``"n M z"``) passes through as a single ID, rather than being
    reformatted (or reduced to "") by ``_normalize_expression``."""
    return any(
        token in ("(", ")", "+") or token.upper() in OPERATORS
        for token in RE_TOKEN.findall(identifier)
    )


def _normalize_expression(expression: str, db: ListLookup | None = None) -> str:
    """Parses and normalises an SPDX License Expression."""
    # RE_TOKEN takes an ID whole, so "or" inside GPL-2.0-or-later or a
    # LicenseRef-* name is never an operator.
    tokens = RE_TOKEN.findall(expression)

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
        if upper_token in OPERATORS:
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

    # Brackets around the whole go first, whatever happens next: the sort
    # would drop them, but it is skipped past the cap or for a "+", and the
    # parser gives up on thousands of them.
    expr = without_outer_brackets(expr)
    operator_count = sum(1 for t in normalized_tokens if t in OPERATORS)
    if operator_count > _MAX_CANONICALIZE_OPERATORS:
        return expr

    return _canonicalize_expression(expr)


def _canonicalize_expression(expr: str) -> str:
    """Best-effort structural canonicalization via ``py_spdx_license``: its
    ``sort()`` de-duplicates identical AND/OR operands and orders them
    (``MIT AND MIT`` -> ``MIT``). Any failure keeps the string as it is:
    the parser cannot read the legacy ``license-id"+"`` form (``CDDL-1.0+``;
    https://github.com/JPEWdev/py-spdx-license/issues/1), and its bundled
    list can lag behind the database."""
    ast = parse_expression(expr)
    if ast is None:
        return expr
    try:
        return cast(str, ast.sort().to_string())
    except Exception:  # pylint: disable=broad-exception-caught
        return expr


def without_outer_brackets(expr: str) -> str:
    """*expr* without brackets around the whole of it, as the sort in
    _canonicalize_expression drops them: "(Apache-2.0+)" is "Apache-2.0+"
    (and as looseid.loose_with reads a bracketed expression).

    One pass, as a tag can nest thousands deep: an outer pair holds the whole
    only while no bracket between the leading and trailing runs closes it, so
    the shallowest depth there is how many pairs go ("(A) OR (B)": none).
    """
    lead = len(expr) - len(expr.lstrip("("))
    trail = len(expr) - len(expr.rstrip(")"))
    depth = shallowest = lead
    for char in expr[lead : len(expr) - trail]:
        depth += {"(": 1, ")": -1}.get(char, 0)
        shallowest = min(shallowest, depth)
    pairs = min(shallowest, trail)
    return expr[pairs : len(expr) - pairs]

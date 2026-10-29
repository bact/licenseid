# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Resolve a declared licence value to an SPDX expression and say how.

``match`` answers "which licence is this text"; ``resolve`` answers "which
SPDX expression does this *declared value* stand for, and what did the
resolver do to get there". A caller that records the result needs the second
part: a changed case is no decision, a re-spelt ID is, and a qualifier
(``-only``) the author never wrote is a guess that must not be applied.

This release resolves a value that names one licence, with its exception if
it has one. An expression of several (``MIT OR Apache2``) is reported as
category ``expression`` with no resolution. A step that rests on a list cites
it.

No database is needed: with none, ``resolve`` reads the SPDX License List
shipped in the wheel, in memory, and gives the answer a database built from
that list would give (``licenseid.listsource`` chooses, ``licenseid.listindex``
reads). ``lists[*].source`` says which was read.
"""

import re
import unicodedata

from licenseid.database import LicenseDatabase
from licenseid.identifiers import parse_expression, without_outer_brackets
from licenseid.listlookup import ListLookup
from licenseid.listsource import choose_list
from licenseid.plusoperator import plus_after_qualifier, strip_plus_operator
from licenseid.quotes import unquote
from licenseid.resolvecompound import operand_of
from licenseid.resolveleaf import Found, category_of, read_leaf
from licenseid.resolverinfo import list_info, parser_info, resolver_info
from licenseid.resolvertypes import (
    SCHEMA,
    TRUST,
    Category,
    ListInfo,
    ListSource,
    Operand,
    Resolution,
    Source,
    step,
)
from licenseid.textinput import has_lone_surrogate

_OPERATORS = frozenset({"AND", "OR", "WITH"})
_JOINS = frozenset({"AND", "OR"})
_RE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")
_RE_IDLIKE = re.compile(r"[\d.-]")
_RE_SQUARE = re.compile(r"[\[\]{}]")
# The longest expression read; one licence is MAX_KEY_INPUT or less (versionkey).
_MAX_EXPRESSION_CHARS = 2000


def resolve(
    value: str, db: LicenseDatabase | None = None, *, source: Source = "auto"
) -> Resolution:
    """Resolve the declared licence *value*.

    Never raises on content: a value that names nothing is category
    ``unresolved``.

    The list read is *db*, else the one *source* names: ``auto`` (the
    default) reads the database at the default path or the bundle shipped
    in the wheel, whichever holds the newer List; with no database file, the
    bundle; ``database`` the database at the default path; ``packaged`` the
    bundle (:mod:`licenseid.listsource`). ``lists[*].source`` says which.
    :class:`licenseid.errors.DatabaseNotReadyError` is raised when the list
    cannot be read: with ``auto``, only when there is neither.

    A deprecated ID that the List split into ``-only`` and ``-or-later`` is
    never narrowed: ``GPL-3.0`` comes back as written, category
    ``assumed_only``, with both candidates.
    """
    lookup, where = choose_list(db, source)
    return resolve_with(lookup, value, where)


def resolve_with(
    lookup: ListLookup, value: str, where: ListSource = "database"
) -> Resolution:
    """:func:`resolve` on a list the caller holds: any
    :class:`licenseid.listlookup.ListLookup`, read as it is; *where* is what
    ``lists[0].source`` says."""
    with lookup.reading():
        found, operands, parsed = _read(lookup, value)
        lists = [list_info(lookup, where)]
    return _resolution(value, (found, operands, parsed), lists)


def _read(db: ListLookup, value: str) -> tuple[Found, list[Operand], bool]:
    """Read one declared *value*: what was found for the whole, its operands,
    and whether the expression parser ran."""
    found = Found()
    text, start = _prepared(value, found)
    if not text or len(text) > _MAX_EXPRESSION_CHARS:
        found.category = "unresolved"
        return found, [], False
    found.reason = _refusal(text)
    if found.reason is not None:
        found.category, found.steps = "unresolved", []  # no step was taken
        return found, [], False
    leaf = Found()
    if read_leaf(db, text, leaf):
        _absorb(found, leaf)
        return found, [operand_of(text, start, leaf)], False
    found.category = _expression_category(db, text)
    return found, [], False


def _absorb(found: Found, leaf: Found) -> None:
    """Put the reading of the one *leaf* into *found*, after the steps taken
    on the whole value. A leaf that resolved to nothing keeps only its own
    steps (a refusal's ``drop``), as no step before it led anywhere."""
    found.steps = found.steps + leaf.steps if leaf.expression else list(leaf.steps)
    found.expansions += leaf.expansions
    found.candidates = list(leaf.candidates)
    found.expression, found.category = leaf.expression, leaf.category
    found.reason = leaf.reason


def _prepared(value: str, found: Found) -> tuple[str, int]:
    """*value* trimmed, and without the quotes and brackets around the whole
    of it (``"MIT"``, ``(MIT)``, ``("MIT")``), each as a step, and where that
    text starts in *value* (a code point). The quotes are taken off the
    whole value, once (:mod:`licenseid.quotes`)."""
    text = value.strip()
    start = len(value) - len(value.lstrip())
    if text != value:
        found.steps.append(step("trim", True, value, text))
    text, start = _unquoted(text, start, found)
    inner, inner_start = _unbracketed(text, start, found)
    if inner == text:
        return text, start
    return _unquoted(inner, inner_start, found)


def _unquoted(text: str, start: int, found: Found) -> tuple[str, int]:
    """*text* without quote marks around the whole of it, as an ``unquote``
    step whose detail says whether they were balanced, and where it starts
    (*text* starts at *start*)."""
    unquoted = unquote(text)
    if unquoted is None:
        return text, start
    found.steps.append(step("unquote", True, text, unquoted.text, unquoted.detail))
    if not unquoted.balanced:
        found.floor = "separator"  # the value may be cut: a rule of the resolver
    return unquoted.text, start + unquoted.start


def _unbracketed(text: str, start: int, found: Found) -> tuple[str, int]:
    """*text* without brackets around the whole of it, as a ``brackets``
    step, and where it starts (*text* starts at *start*)."""
    inner = without_outer_brackets(text)
    if inner == text:
        return text, start
    found.steps.append(step("brackets", True, text, inner))
    lead = (len(text) - len(inner)) // 2 + len(inner) - len(inner.lstrip())
    return inner.strip(), start + lead


def _expression_category(db: ListLookup, text: str) -> Category:
    """``expression`` for an SPDX expression of several licences,
    ``malformed`` for one with a "+" after a stated qualifier
    (``MIT OR GPL-2.0-only+``), as on its own; else ``unresolved``."""
    if not _is_expression(db, text):
        return "unresolved"
    return "malformed" if plus_after_qualifier(text) else "expression"


def _is_expression(db: ListLookup, text: str) -> bool:
    """Whether *text* is an SPDX expression of several licences: it parses (a
    "+" operator aside), and every operand is a listed ID or looks like one
    (a digit, a hyphen or a full stop in it). ``MIT OR Apache2`` is;
    ``Proprietary or custom``, ``GPL-3.0 or higher`` and ``Licensed with love``
    name one licence, or none, and are not."""
    if _RE_SQUARE.search(text) or parse_expression(strip_plus_operator(text)) is None:
        return False
    tokens = _RE_TOKEN.findall(text)
    operands = [
        token.rstrip("+") for token in tokens if token.upper() not in _OPERATORS
    ]
    # Only AND and OR join several licences: one ID-shaped word (Foo-1.0) is
    # one licence, and WITH qualifies one (with_exception).
    return any(token.upper() in _JOINS for token in tokens) and all(
        _RE_IDLIKE.search(token) or db.get_license_details(token) for token in operands
    )


def _refusal(text: str) -> str | None:
    """Why *text* is no licence value, or None. A control or format
    character other than white space (a NUL, a zero-width space, a bidi
    override) must not be dropped as a separator, since that would resolve
    text that shows other than it reads; a lone surrogate
    (:func:`licenseid.textinput.has_lone_surrogate`) SQLite cannot bind."""
    if has_lone_surrogate(text):
        return "lone surrogate"
    for char in text:
        if unicodedata.category(char) in ("Cc", "Cf") and not char.isspace():
            return f"control or format character: U+{ord(char):04X}"
    return None


def _resolution(
    value: str, reading: tuple[Found, list[Operand], bool], lists: list[ListInfo]
) -> Resolution:
    found, operands, parsed = reading
    category = category_of(found)
    if found.expression is None and found.reason is None:
        found.steps, found.expansions = [], []  # nothing resolved: no step taken
    return {
        "schema": SCHEMA,
        "input": value,
        "expression": found.expression,
        "category": category,
        "trust": TRUST[category],
        "steps": found.steps,
        "expansions": found.expansions,
        "candidates": found.candidates,
        "operands": operands,
        "resolver": resolver_info(),
        "components": [parser_info()] if parsed else [],
        "lists": lists,
        "reason": found.reason,
    }

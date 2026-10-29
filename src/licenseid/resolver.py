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

A value that names one licence, with its exception if it has one, is read
by ``licenseid.resolveleaf``; an expression of several (``MIT OR Apache2``)
by ``licenseid.resolvecompound``, each operand as it would be read alone,
and written in canonical order (``licenseid.exprcanon``); a trove classifier
(``License :: OSI Approved :: MIT License``) or a name with its short form
(``MIT License (MIT)``) by ``licenseid.resolvetrove``; the prose form of one
ID (``BSD 3-Clause License``, ``Apache License, Version 2.0``) by
``licenseid.resolveprose``; licences joined by ``;``, which states no
operator, are listed as operands and no expression
(``licenseid.resolvesemicolon``). A step that rests on a list cites it.

No database is needed: with none, ``resolve`` reads the SPDX License List
shipped in the wheel, in memory, and gives the answer a database built from
that list would give (``licenseid.listsource`` chooses, ``licenseid.listindex``
reads). ``lists[*].source`` says which was read.
"""

import unicodedata

from licenseid.database import LicenseDatabase
from licenseid.exprcanon import unbracketed
from licenseid.listlookup import ListLookup
from licenseid.listsource import choose_list
from licenseid.quotes import unquote
from licenseid.resolvecompound import (
    absorb,
    not_an_operator,
    operand_of,
    read_compound,
)
from licenseid.resolveleaf import Found, category_of, read_leaf
from licenseid.resolveprose import read_by_name
from licenseid.resolverinfo import (
    list_info,
    parser_info,
    resolver_info,
    trove_list_info,
)
from licenseid.resolvertypes import (
    SCHEMA,
    TROVE_LIST,
    TRUST,
    ListInfo,
    ListSource,
    Operand,
    Resolution,
    Source,
    step,
)
from licenseid.resolvesemicolon import read_semicolon_list, semicolon_parts
from licenseid.textinput import has_lone_surrogate

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
    resolution = _resolution(value, (found, operands, parsed), lists)
    if any(s["list"] == TROVE_LIST for s in resolution["steps"]):
        resolution["lists"].append(trove_list_info())  # a name rests on it too
    return resolution


def _read(
    db: ListLookup, value: str, *, lists: bool = True
) -> tuple[Found, list[Operand], bool]:
    """Read one declared *value*: what was found for the whole, its operands,
    and whether the expression parser ran. With *lists* false a ``;`` between
    licences is not split: a part is not read as a list again."""
    found = Found()
    text, start = _prepared(value, found)
    if not text or len(text) > _MAX_EXPRESSION_CHARS:
        found.category = "unresolved"
        return found, [], False
    found.reason = _refusal(text)
    if found.reason is not None:
        found.category, found.steps = "unresolved", []  # no step was taken
        return found, [], False
    return _read_text(db, text, start, found, lists)


def _read_text(
    db: ListLookup, text: str, start: int, found: Found, lists: bool
) -> tuple[Found, list[Operand], bool]:
    """:func:`_read` on *text*, which starts at code point *start* and has
    the steps of its preparation in *found*."""
    leaf = Found()
    if read_leaf(db, text, leaf):  # one licence first
        absorb(found, leaf)
        return found, [operand_of(text, start, leaf)], False
    prepared = Found(steps=list(found.steps), floor=found.floor)
    compound = read_compound(db, text, start, found)
    if compound.claimed and found.expression is not None:
        return found, compound.operands, compound.parsed
    listed = _read_list(db, text, start, prepared) if lists else None
    if listed is not None:  # several licences, no operator stated (T8b)
        return prepared, listed[0], listed[1]
    if compound.claimed:
        return found, compound.operands, compound.parsed
    named = Found()
    # A trove name or path, a name and its short form, then the prose form of
    # one ID (T8: P1 to P3)
    if read_by_name(db, text, named):
        absorb(found, named)
        return found, [operand_of(text, start, named)], False
    # One leaf that names nothing, or prose in compound form, with its first
    # refused operand's reason.
    found.category, found.reason = "unresolved", not_an_operator(text)
    if compound.fallback is not None:
        found.reason, found.steps = compound.fallback.reason, compound.fallback.steps
    nothing = Found(category="unresolved", reason=found.reason)
    return found, [operand_of(text, start, nothing)], False  # no parse used


def _read_list(
    db: ListLookup, text: str, start: int, found: Found
) -> tuple[list[Operand], bool] | None:
    """*text* as licences joined by ``;`` (:mod:`licenseid.resolvesemicolon`):
    its operands and whether the parser ran, with *found* made the refusal;
    None for any other value."""
    parts = semicolon_parts(text)
    if parts is None:
        return None

    def read(part: str) -> tuple[Found, bool]:
        read_found, _, parsed = _read(db, part, lists=False)
        return read_found, parsed

    return read_semicolon_list(parts, start, read, found)


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
    inner = unbracketed(text)
    if inner == text:
        return text, start
    found.steps.append(step("brackets", True, text, inner))
    lead = (len(text) - len(inner)) // 2 + len(inner) - len(inner.lstrip())
    return inner.strip(), start + lead


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

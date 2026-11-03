# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Resolve a declared licence value to an SPDX expression and say how.

``detect`` answers "which licence is this text"; ``match`` answers "which
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

No database is needed: with none, ``match`` reads the SPDX License List
shipped in the wheel, in memory, and gives the answer a database built from
that list would give (``licenseid.listsource`` chooses, ``licenseid.listindex``
reads). ``lists[*].source`` says which was read.
"""

import re
import unicodedata
from typing import Final

from licenseid.dropguard import marks_at_end, trim_end_mark
from licenseid.exprcanon import unbracketed
from licenseid.exprtokens import RE_OPERATOR, WHITE_SPACE, is_white_space
from licenseid.listlookup import ListLookup
from licenseid.listsource import GivenDatabase, choose_list
from licenseid.quotes import ended_quote, unquote
from licenseid.resolvecompound import (
    absorb,
    not_an_operator,
    operand_of,
    read_compound,
)
from licenseid.resolveleaf import Found, category_of, read_leaf, refuse_dropped
from licenseid.resolveprose import read_by_name
from licenseid.resolvereason import EMPTY, no_reading, too_long
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

#: The longest value read, once trimmed and unquoted; one licence is
#: MAX_KEY_INPUT or less (versionkey). ``licenseid match`` refuses a longer
#: argument (``climatch``).
MAX_EXPRESSION_CHARS: Final = 2000
# A surrogate code point: alone, no UTF-8 encoder takes it.
_RE_SURROGATE = re.compile("[\ud800-\udfff]")
# One end mark: an ending, which a value is not refused for (dropguard).
_END_MARKS = frozenset(".,;:")


def match(
    value: str, db: GivenDatabase | None = None, *, source: Source = "auto"
) -> Resolution:
    """Resolve the declared licence *value*.

    Never raises on content: a value that names nothing is category
    ``unresolved``. A *value* that is no :class:`str` (``None``,
    :class:`bytes`, a number) is no content but a mistake of the caller:
    :class:`TypeError`, naming the type, before anything is read.

    *db* is a :class:`licenseid.database.LicenseDatabase` or the path of
    one (:class:`str` or :class:`os.PathLike`), opened read-only: a missing
    file is :class:`licenseid.errors.DatabaseNotReadyError` (``not found``),
    never created; any other *db* is :class:`TypeError`. Every database is
    checked ready before it is read.

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
    _require_text(value)
    lookup, where = choose_list(db, source)
    return match_with(lookup, value, where)


def match_with(
    lookup: ListLookup, value: str, where: ListSource = "database"
) -> Resolution:
    """:func:`match` on a list the caller holds: any
    :class:`licenseid.listlookup.ListLookup`, read as it is; *where* is what
    ``lists[0].source`` says. Raises :class:`TypeError` for a *value* that is
    no :class:`str`, as :func:`match` does."""
    _require_text(value)
    with lookup.reading():
        found, operands, parsed = _read(lookup, value)
        _explain(lookup, value, found, operands)
        lists = [list_info(lookup, where)]
    resolution = _resolution(value, (found, operands, parsed), lists)
    if TROVE_LIST in _cited(resolution):
        resolution["lists"].append(trove_list_info())  # a name rests on it too
    return resolution


def _cited(resolution: Resolution) -> set[str | None]:
    """The lists the steps of *resolution* rest on: those of the value and
    those of each operand, which a refused list of licences (``MIT; ISC
    License (ISCL)``) does not repeat at the top."""
    readings = [resolution, *resolution["operands"]]
    return {
        entry["list"]
        for reading in readings
        for entry in [*reading["steps"], *reading["expansions"]]
    }


def _explain(
    lookup: ListLookup, value: str, found: Found, operands: list[Operand]
) -> None:
    """Give a reason to the refusal of *value* and to each refused operand
    that no reader gave one (:func:`licenseid.resolvereason.no_reading`), so
    an answer with no expression always says why (P5). The steps of such a
    refusal are not kept: no step led anywhere (P11)."""

    def names(text: str) -> bool:
        return read_leaf(lookup, text, leaf := Found()) and leaf.expression is not None

    if found.expression is None and found.reason is None:
        found.steps, found.expansions = [], []
        text = _prepared(value, Found())[0]
        if not _marks_refusal(lookup, text, found):
            found.reason = no_reading(lookup, text, names)
    for index, operand in enumerate(operands):
        if operand["expression"] is None and operand["reason"] is None:
            text, refused = operand["text"], Found()
            if _marks_refusal(lookup, text.strip(), refused):
                operands[index] = operand_of(text, operand["span"][0], refused)
            else:
                operand["reason"] = no_reading(lookup, text.strip(), names)


def _marks_refusal(lookup: ListLookup, text: str, found: Found) -> bool:
    """Make *found* the refusal of *text*, a value no reader read, that names
    a licence once the marks at its end are left off, inside closing
    brackets and quote marks too (``(MIT)-``, ``"(MIT;)".``): a ``drop`` and
    ``character dropped: U+...``, as for a mark after an ID (P137). Where
    what is left is malformed (``LicenseRef-a+-``), its reason is the
    value's. One end mark alone (``(MIT).``) is an ending, not a dropped
    mark: no reason here. False when nothing is made."""
    ended = marks_at_end(text)
    if ended is None:
        return False
    core, marks = ended
    again = _read(lookup, core, lists=False)[0]
    if again.expression is None:
        if again.category != "malformed":
            return False
        found.category, found.reason = again.category, again.reason
        return True
    if len(marks) == 1 and marks in _END_MARKS:
        return False
    refuse_dropped(found, text, "".join(dict.fromkeys(marks)), again.expression)
    return True


def _require_text(value: object) -> None:
    """Raise :class:`TypeError` unless *value* is a :class:`str` (P130): a
    call that cannot be a declared value is not an unresolved one."""
    if not isinstance(value, str):
        raise TypeError(f"value must be str, not {type(value).__name__}")


def read_length(value: str) -> int:
    """The length of *value* as :data:`MAX_EXPRESSION_CHARS` counts it:
    trimmed, without the quotes and brackets around the whole of it (one
    pass over it)."""
    return len(_prepared(value, Found())[0])


def _read(
    db: ListLookup, value: str, *, lists: bool = True
) -> tuple[Found, list[Operand], bool]:
    """Read one declared *value*: what was found for the whole, its operands,
    and whether the expression parser ran. With *lists* false a ``;`` between
    licences is not split: a part is not read as a list again."""
    found = Found()
    text, start = _prepared(value, found)
    if not text or len(text) > MAX_EXPRESSION_CHARS:
        found.category, found.steps = "unresolved", []  # nothing was read
        found.reason = too_long(len(text)) if text else EMPTY
        return found, [], False
    found.reason = _refusal(value)  # before any reader drops a character
    if found.reason is not None:
        found.category, found.steps = "unresolved", []  # no step was taken
        return found, [], False
    ending = Found(steps=list(found.steps), floor=found.floor)
    read = _read_text(db, text, start, found, lists)
    if read[0].expression is None and read[0].reason is None:
        return _ended(db, text, start, ending, lists) or read
    return read


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
    named = Found()
    # A trove name or path, a name and its short form, then the prose form of
    # one ID (T8: P1 to P3). A name that reads is read before a list
    # (``MIT; (MIT)`` is the name and its short form, P87).
    by_name = not compound.claimed and read_by_name(db, text, named)
    resolved = by_name and named.expression is not None
    listed = _read_list(db, text, start, prepared) if lists and not resolved else None
    if listed is not None:  # several licences, no operator stated (T8b)
        return prepared, listed[0], listed[1]
    if compound.claimed:
        return found, compound.operands, compound.parsed
    if by_name:
        absorb(found, named)
        return found, [operand_of(text, start, named)], False
    # One leaf that names nothing, or prose in compound form, with its first
    # refused operand's reason.
    found.category, found.reason = "unresolved", not_an_operator(text)
    if compound.fallback is not None:
        found.reason, found.steps = compound.fallback.reason, compound.fallback.steps
    nothing = Found(category="unresolved", reason=found.reason)
    return found, [operand_of(text, start, nothing)], False  # no parse used


def _ended(
    db: ListLookup, text: str, start: int, found: Found, lists: bool
) -> tuple[Found, list[Operand], bool] | None:
    """*text*, which no reader read and none gave a reason, read without the
    one end mark that ends it, as an ending ``separator`` step after the
    steps in *found* (``(MIT).``, ``The Unlicense.``): the readers that take
    one off themselves read an ID or a prose form, not brackets or a name.
    Read once: what is left is not read for an ending again. None when that
    names nothing, or when a mark is left at the end inside the brackets or
    quote marks (``(MIT.).``: two marks, refused for them)."""
    trimmed = trim_end_mark(text)
    if trimmed is None or marks_at_end(trimmed) is not None:
        return None
    found.steps.append(step("separator", True, text, trimmed, "end mark"))
    inner, offset = _prepared(trimmed, found)
    read = _read_text(db, inner, start + offset, found, lists)
    return read if read[0].expression is not None else None


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
    text = value.strip(WHITE_SPACE)
    start = len(value) - len(value.lstrip(WHITE_SPACE))
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
    (*text* starts at *start*). One end mark after the closing marks
    (``"MIT".``) comes off first, as a ``separator`` step. Marks around an
    operator alone (``"" OR ""``) are the operands' quotes, not the value's:
    they pair as layers, but no value is an operator."""
    ended = ended_quote(text)
    if ended is not None:
        found.steps.append(step("separator", True, text, ended, "end mark"))
        text = ended
    unquoted = unquote(text)
    if unquoted is None or RE_OPERATOR.fullmatch(unquoted.text):
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
    inside = inner.lstrip(WHITE_SPACE)
    lead = (len(text) - len(inner)) // 2 + len(inner) - len(inside)
    return inside.rstrip(WHITE_SPACE), start + lead


def _refusal(text: str) -> str | None:
    """Why *text* is no licence value, or None. A control or format
    character other than white space (a NUL, a zero-width space, a bidi
    override, the information separators U+001C to U+001F, which
    ``str.isspace()`` takes for white space) must not be dropped as a
    separator, since that would resolve text that shows other than it
    reads; a lone surrogate
    (:func:`licenseid.textinput.has_lone_surrogate`) SQLite cannot bind."""
    if has_lone_surrogate(text):
        return "lone surrogate"
    for char in text:
        if unicodedata.category(char) in ("Cc", "Cf") and not is_white_space(char):
            return f"control or format character: U+{ord(char):04X}"
    return None


def _encodable(text: str) -> str:
    """*text* with each surrogate code point made U+FFFD, one code point for
    one, so a span still indexes it: the result is written as UTF-8 (RFC
    8785), which no surrogate is. Only a value :func:`_refusal` refused
    holds one."""
    return _RE_SURROGATE.sub("\ufffd", text)


def _resolution(
    value: str, reading: tuple[Found, list[Operand], bool], lists: list[ListInfo]
) -> Resolution:
    found, operands, parsed = reading
    category = category_of(found)
    return {
        "schema": SCHEMA,
        "input": _encodable(value),
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

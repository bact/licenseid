# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules that read the prose form of one licence ID (task T8; 0.7.0 plan,
rules P1 to P3).

``resolver`` calls :func:`read_prose` last, after the one-licence, compound
and trove readers (decisions Q18, Q22): a name the trove table reads as
``none`` (``BSD License``, ``W3C license``) was claimed before, so no rule
here guesses at it. Each rule reduces the text and hands the reduction to
:func:`licenseid.resolveleaf.read_leaf`, which proves it as it proves any
value, so there is no second reader of IDs, names, ``+`` or grants.

P1, a trailing word ``license`` or ``licence`` in any case, after a value
that reads alone (``BSD 3-Clause License``, ``Apache-2.0 license``). The word
names the kind of document, not the licence. ``BSD License`` reduces to
``BSD``, which names no licence, so it stays unresolved.

P2, ``<name> License[,] (Version|v) N`` is ``<name> N`` (``Apache License,
Version 2.0`` is ``Apache 2.0``): how the licence text titles itself. The
reduction is read as it would be alone, through the loose key; it never
becomes a List name the author did not write (``GNU General Public License
v3`` is ``GNU General Public 3``, which names nothing).

P3, a leading ``The``, only together with P1, P2 or a listed name (``The
MIT License``). ``The MIT`` is no prose form of anything.

One mark at the end (``.``, ``,``, ``;`` or ``:``:
:func:`licenseid.dropguard.trim_end_mark`) is left off first, as for a leaf;
any other mark stays on the reduction, which the drop guard refuses
(``MIT License;;``, ``MIT License...``, ``MIT License?``). The reading is a
``prose_form`` step from the value to the reduction, then the steps of the
reduction; the category is the weakest of them (``prose_form`` at the least).

A prose form is several words, so it is no operand of a compound (P43).
:func:`read_alone` tells the compound reader whether a leaf of several words
reads alone, for its reason.
"""

import re

from licenseid.dropguard import end_dashes, trim_end_mark
from licenseid.listlookup import ListLookup
from licenseid.normalize import RE_DASHES
from licenseid.resolveleaf import Found, read_leaf, refuse_dropped
from licenseid.resolvertypes import Step, step
from licenseid.resolvetrove import is_no_licence, read_named, trailing_parts

_KIND = "prose_form"
_LICENCE_WORDS = frozenset({"license", "licence"})
# From the white space before "License" to the end. A run of white space is
# tried one character at a time, and fails at the first that is no "l", so
# its cost is linear (tests/test_resolver_prose.py times it).
_RE_VERSION_TAIL = re.compile(
    r"[ \t]licen[cs]e,?[ \t]+(?:version[ \t]*|v[ \t]?)(?P<number>\d+(?:\.\d+)*)\Z",
    re.IGNORECASE,
)


def read_prose(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a value no leaf, compound or trove reader reads, as the
    prose form of one licence ID into *found*, or as one with its short form
    in brackets (``The MIT License (MIT)``, as T3 reads a listed name). False
    if no rule is for it or its reduction names no licence."""
    parts = trailing_parts(text)
    if parts is None:
        return _prose(db, text, found)
    head, inside = parts
    named, alone = Found(), Found()
    if not _prose(db, head, named) or not read_leaf(db, inside, alone):
        return False
    if named.expression is None or named.expression != alone.expression:
        return False
    _fill(found, [step("trailing_name", True, text, head)], named)
    return True


def _prose(db: ListLookup, text: str, found: Found) -> bool:
    """P1 to P3 on *text* with no bracket at its end."""
    # One mark at the end is an ending, as for a leaf (P77); other marks stay
    # on the reduction, which the drop guard refuses.
    body = trim_end_mark(text) or text.strip()
    if is_no_licence(body):  # a name that states no licence stays so (Q22)
        return False
    rest = _after_article(body)
    # A second article (``The The MIT License``) is no prose form (P75)
    if rest is not None and _after_article(rest) is None and not is_no_licence(rest):
        lead = step(_KIND, True, text, rest, "leading article")
        if _by_name(db, rest, lead, found) or _by_rule(db, rest, rest, [lead], found):
            return True
    return _by_rule(db, text, body, [], found)  # P1, P2


def read_by_name(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a value no leaf and no compound reads, by the name it
    carries: a trove name, path or agreeing short form
    (:func:`licenseid.resolvetrove.read_named`), else as a prose form
    (:func:`read_prose`). A name that states no licence is claimed first, so
    no prose rule reads it (Q22)."""
    return read_named(db, text, found) or read_prose(db, text, found)


def read_alone(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text* as ``match`` reads a value of no operator: one licence
    (:func:`licenseid.resolveleaf.read_leaf`), else by a name
    (:func:`read_by_name`). The compound reader asks it whether a leaf of
    several words reads alone (P43, P62), so it never judges by the leaf
    reader only."""
    return read_leaf(db, text, found) or read_by_name(db, text, found)


def _by_rule(
    db: ListLookup, source: str, body: str, before: list[Step], found: Found
) -> bool:
    """P1 or P2 on *body* (*source* with its end marks off): its reductions
    read as they are alone, after the steps *before*. Marks after the last
    word (``MIT License;``) stay on the reduction, so that the drop guard
    refuses it with its reason (P64); they never help a reading. P2 has two
    reductions, which must agree (P68)."""
    core = body[: _word_end(body)].rstrip()
    marks = _marks_after(body[len(core) :])
    readings = []
    for word, detail in _reductions(db, core):
        reading = Found()
        if not read_leaf(db, word + marks, reading):
            continue
        if reading.expression is None and _refused(found, reading):
            return True
        if reading.expression is not None:
            readings.append((word, detail, reading))
    if len({r.expression for _, _, r in readings}) != 1:
        return False
    if marks:  # marks never help a reading; a dash it would drop is said (P121)
        lost = end_dashes(marks)
        if lost:
            refuse_dropped(found, source, lost, str(readings[0][2].expression))
        return bool(lost)
    word, detail, reading = readings[0]
    _fill(found, [*before, step(_KIND, True, source, word, detail)], reading)
    return True


def _marks_after(rest: str) -> str:
    """The marks after the last word, with the white space before them only
    for a run of dots or dashes (``MIT -`` is dangling, ``MIT &`` is not
    otherwise changed)."""
    marks = rest.strip()
    if marks and all(c == "." or RE_DASHES.match(c) for c in marks):
        return rest.rstrip()
    return marks


def _word_end(text: str) -> int:
    """Where the last word of *text* ends: the marks after it are not part
    of a word or white space."""
    end = len(text)
    while end and not (text[end - 1].isalnum() or text[end - 1].isspace()):
        end -= 1
    return end


def _reductions(db: ListLookup, core: str) -> list[tuple[str, str]]:
    """The texts P1 or P2 reduce *core* to, each with the detail of its
    step: P1 the head of a final licence word; P2 ``<name> N`` and, where the
    List has a name exactly so, ``<name> License N`` (an exact name lookup,
    never a loose key over names)."""
    head = _licence_word(core)
    if head is not None:
        return [(head, "licence word")]
    tail = _RE_VERSION_TAIL.search(core)
    name = "" if tail is None else core[: tail.start()].rstrip()
    if tail is None or not name:
        return []
    reductions = [(f"{name} {tail['number']}", "version")]
    named = f"{name} License {tail['number']}"
    if len(db.get_active_ids_by_name().get(named.casefold(), [])) == 1:
        reductions.append((named, "version"))
    return reductions


def _by_name(db: ListLookup, rest: str, lead: Step, found: Found) -> bool:
    """P3 with a listed name: *rest* after its article is a name the List
    lists (``The Unlicense`` is read before, as an ID); an ID alone is not
    (``The MIT``)."""
    reading = Found()
    if not read_leaf(db, rest, reading):
        return False
    if reading.expression is None:
        return _refused(found, reading)
    if not any(s["kind"] == "listed_name" for s in reading.steps):
        return False
    _fill(found, [lead], reading)
    return True


def _refused(found: Found, reading: Found) -> bool:
    """Make *found* the refusal *reading* is, if it is one (a mark or a word
    the reduction would drop, with its ``reason``): True. A reduction that
    only names nothing is no refusal: False."""
    if reading.reason is None:
        return False
    found.steps, found.reason = list(reading.steps), reading.reason
    found.expression, found.category = None, "unresolved"
    return True


def _fill(found: Found, steps: list[Step], reading: Found) -> None:
    """Put the *steps* taken on the text, then the *reading* of what they
    led to, in *found*."""
    found.steps = [*steps, *reading.steps]
    found.expansions = list(reading.expansions)
    found.candidates = list(reading.candidates)
    found.expression, found.category = reading.expression, reading.category
    found.reason = reading.reason


def _licence_word(body: str) -> str | None:
    """*body* without a final ``license`` or ``licence`` (P1), or None. A
    head that ends in one itself (``MIT License License``) is no prose form
    (P75)."""
    head = _without_word(body)
    if head is None or _without_word(head) is not None:
        return None
    return head


def _without_word(text: str) -> str | None:
    """*text* without a final licence word that stands alone, or None."""
    head = text[:-7]
    if text[-7:].casefold() not in _LICENCE_WORDS or not head[-1:].isspace():
        return None
    return head.rstrip() or None


def _after_article(body: str) -> str | None:
    """*body* without a leading ``The`` in any case (P3), or None."""
    if body[:3].casefold() != "the" or not body[3:4].isspace():
        return None
    return body[3:].lstrip() or None

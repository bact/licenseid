# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules that read a value by the name it carries (task T9; 0.7.0 plan,
rules T1 to T3): a trove classifier, and a name with its abbreviation.

``resolver`` calls :func:`read_named` after a value is read as one licence
and as a compound, and before any rule of prose (decisions Q18, Q22), so a
trove name the table reads as ``none`` is not read by the rules after it.

T1, a path ``License :: OSI Approved :: X``, in its real form
(:func:`licenseid.trovenames.strip_trove_path`), is read as ``X`` is read
alone, plus a ``trove_path`` step. ``OSI Approved`` alone names no licence.

T2, a name of the table (:data:`licenseid.trovenames.TROVE_NAMES`): the
``stated`` or ``assumed`` ID it records is read through the leaf lookup, as
the author's own ID would be, so a bare deprecated ID (``GPL-3.0``) stays
``assumed_only`` with its candidates, and an ID this list lacks names
nothing. A ``trove_name`` step cites the trove vocabulary. A ``none`` name is
refused here, so that no later rule guesses at it.

T3, ``<head> (<inside>)``: the parenthesis is dropped only when the head and
the inside, each read alone, are the same expression (``MIT License
(MIT)``); two readings that agree choose nothing. If they differ, or only
one reads, nothing is read.

Every rule reads through :func:`licenseid.resolveleaf.read_leaf`: there is no
second reader of IDs, names, ``+`` or grants.
"""

from licenseid.listlookup import ListLookup
from licenseid.resolveleaf import Found, read_leaf
from licenseid.resolvertypes import step
from licenseid.trovenames import TROVE_NAMES, strip_trove_path

#: The names that state no licence, folded: no later rule may read one.
_NO_LICENCE = frozenset(
    " ".join(name.split()).casefold()
    for name, entry in TROVE_NAMES.items()
    if entry.reading == "none"
)


def read_named(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a value no leaf and no compound reads, by its trove path,
    trove name or agreeing trailing name into *found*. False if no rule is
    for it; True with ``unresolved`` for a name the table reads as ``none``."""
    name = strip_trove_path(text)
    if name is None:
        return _by_name(db, text, found)
    reading = Found()
    if not read_leaf(db, name, reading):  # X, read as it is alone
        reading = Found()
        _by_name(db, name, reading)
    if reading.expression is None:
        _nothing(found)
        return True
    found.steps = [step("trove_path", True, text, name), *reading.steps]
    _copy(found, reading)
    return True


def read_alone(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text* as ``resolve`` reads a value of no operator: one licence
    (:func:`licenseid.resolveleaf.read_leaf`), else by a name
    (:func:`read_named`). The compound reader asks it whether a leaf of
    several words reads alone (P43, P62), so it never judges by the leaf
    reader only."""
    return read_leaf(db, text, found) or read_named(db, text, found)


def _by_name(db: ListLookup, text: str, found: Found) -> bool:
    """The rules of a name, in order: a name that states no licence is
    claimed first (Q22), however it is written; then a name and a parenthesis
    that agree (T3), since a reading the List backs is stronger than the
    table's; then the table (T2)."""
    if _folded(text) in _NO_LICENCE:
        _nothing(found)
        return True
    return _trailing(db, text, found) or _name(db, text, found)


def _folded(text: str) -> str:
    """*text* in lower case with its white space collapsed: a looser match
    than the table's, used only to refuse (a ``none`` name is never read)."""
    return " ".join(text.split()).casefold()


def _name(db: ListLookup, text: str, found: Found) -> bool:
    """T2: *text* is a name of the table."""
    entry = TROVE_NAMES.get(text)
    if entry is None:
        return False
    reading = Found()
    if (
        not entry.ids
        or not read_leaf(db, entry.ids[0], reading)
        or reading.expression is None  # the list lacks the ID
    ):
        _nothing(found)
        return True
    found.steps = [step("trove_name", True, text, entry.ids[0]), *reading.steps]
    _copy(found, reading)
    return True


def _trailing(db: ListLookup, text: str, found: Found) -> bool:
    """T3: ``head (inside)`` whose two parts are one expression."""
    if not text.endswith(")"):
        return False
    opening = text.rfind("(")
    # Spaces and tabs only: a value is one line, so no other white space
    head, inside = text[:opening].rstrip(" \t"), text[opening + 1 : -1].strip(" \t")
    if (
        opening < 1
        or head == text[:opening]  # a name, white space, then the bracket
        or not head
        or not inside
        or any(mark in head + inside for mark in "()")
    ):
        return False
    named, alone = Found(), Found()
    if not (read_leaf(db, head, named) and read_leaf(db, inside, alone)):
        return False
    if named.expression is None or named.expression != alone.expression:
        return False
    found.steps = [step("trailing_name", True, text, head), *named.steps]
    _copy(found, named)
    return True


def _copy(found: Found, reading: Found) -> None:
    """Put the expansions, candidates and expression of *reading* in *found*;
    its steps are set by the caller."""
    found.expression = reading.expression
    found.expansions = list(reading.expansions)
    found.candidates = list(reading.candidates)
    found.category = reading.category
    found.reason = reading.reason


def _nothing(found: Found) -> None:
    """Make *found* a name that names no licence."""
    found.expression, found.category = None, "unresolved"

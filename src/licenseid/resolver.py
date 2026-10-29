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

import importlib
import re
import unicodedata

from licenseid.database import LicenseDatabase
from licenseid.identifiers import parse_expression, without_outer_brackets
from licenseid.listlookup import ListLookup
from licenseid.listsource import choose_list
from licenseid.plusoperator import plus_after_qualifier, strip_plus_operator
from licenseid.resolveleaf import Found, read_leaf
from licenseid.resolvertypes import (
    CATEGORY_ORDER,
    LEXICAL_KINDS,
    SPDX_LIST,
    TRUST,
    Category,
    ListInfo,
    ListSource,
    Resolution,
    Resolver,
    Source,
    step,
)
from licenseid.textinput import has_lone_surrogate

# The kinds of step the SPDX License List supports; see ListInfo.provides.
_PROVIDES = ["deprecation", "ids", "names", "texts"]
_OPERATORS = frozenset({"AND", "OR", "WITH"})
_JOINS = frozenset({"AND", "OR"})
_RE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")
_RE_IDLIKE = re.compile(r"[\d.-]")
_RE_SQUARE = re.compile(r"[\[\]{}]")
# The longest expression read; one licence is MAX_KEY_INPUT or less (versionkey).
_MAX_EXPRESSION_CHARS = 2000
# A step kind that is not also a category name, mapped to the one it counts as.
_AS_CATEGORY = {kind: "lexical" for kind in LEXICAL_KINDS}


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
    with lookup.reading():
        found = _lookup(lookup, value)
        lists = [_list_info(lookup, where)]
    return _resolution(value, found, lists)


def _lookup(db: ListLookup, value: str) -> Found:
    """Read one declared *value* into a :class:`Found`: the leaf, else the
    category of the expression."""
    found = Found()
    text = value.strip()
    if text != value:
        found.steps.append(step("trim", True, value, text))
    text = _unbracketed(text, found)
    if not text or len(text) > _MAX_EXPRESSION_CHARS or _is_refused(text):
        found.category = "unresolved"
        return found
    if read_leaf(db, text, found):
        return found
    found.category = _expression_category(db, text)
    return found


def _unbracketed(text: str, found: Found) -> str:
    """*text* without brackets around the whole of it, as a ``brackets`` step."""
    inner = without_outer_brackets(text)
    if inner == text:
        return text
    found.steps.append(step("brackets", True, text, inner))
    return inner.strip()


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


def _is_refused(text: str) -> bool:
    """Whether *text* holds a character that makes it no licence value: a
    control or format character other than white space (a NUL, a zero-width
    space, a bidi override), which must not be dropped as a separator, since
    that would resolve text that shows other than it reads; or a lone
    surrogate (:func:`licenseid.textinput.has_lone_surrogate`), which SQLite
    cannot bind. T6 names the reason (``lone surrogate``,
    ``Resolution.reason``)."""
    return has_lone_surrogate(text) or any(
        unicodedata.category(c) in ("Cc", "Cf") and not c.isspace() for c in text
    )


def _category(found: Found) -> Category:
    """The category of an answer: the one the lookup set, else the highest
    ranked kind among its steps."""
    if found.category is not None:
        return found.category
    kinds = {_AS_CATEGORY.get(s["kind"], s["kind"]) for s in found.steps}
    kinds |= {s["kind"] for s in found.expansions}
    ranked = [c for c in CATEGORY_ORDER if c in kinds]
    return ranked[-1] if ranked else "exact"


def _list_info(db: ListLookup, source: ListSource) -> ListInfo:
    """The description of the SPDX License List the lookup reads, and where
    it was read."""
    version = db.get_metadata().get("license_list_version")
    return {
        "id": SPDX_LIST,
        "name": "SPDX License List",
        "version": version,
        "source": source,
        "url": (
            None
            if version is None
            else f"https://github.com/spdx/license-list-data/releases/tag/v{version}"
        ),
        "license": "CC0-1.0",
        "provides": list(_PROVIDES),
        "id_authority": True,
    }


def _resolver_info() -> Resolver:
    """Who resolved. The version is read at call time, as
    ``spdx_source`` reads it (``importlib``, not an import statement): the
    package exports this module, so a static import of the package here would
    be a cycle."""
    version = str(importlib.import_module("licenseid").__version__)
    return {
        "name": "licenseid",
        "version": version,
        "url": f"https://github.com/bact/licenseid/releases/tag/v{version}",
        "purl": f"pkg:pypi/licenseid@{version}",
    }


def _resolution(value: str, found: Found, lists: list[ListInfo]) -> Resolution:
    category = _category(found)
    if found.expression is None:  # nothing was resolved: no step was taken
        found.steps, found.expansions = [], []
    return {
        "input": value,
        "expression": found.expression,
        "category": category,
        "trust": TRUST[category],
        "steps": found.steps,
        "expansions": found.expansions,
        "candidates": found.candidates,
        "resolver": _resolver_info(),
        "lists": lists,
    }

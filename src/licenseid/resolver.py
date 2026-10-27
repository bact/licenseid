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

This release resolves a value that names one licence. An expression of
several (``MIT OR Apache2``) is reported as category ``expression`` with no
resolution. A step that rests on a list cites it.
"""

import importlib
import re
import unicodedata
from dataclasses import dataclass, field

from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.identifiers import (
    parse_expression,
    strip_plus_operator,
    without_outer_brackets,
)
from licenseid.looseid import (
    MAX_KEY_INPUT,
    declared_grant_id_text,
    granted_id_text,
    loose_id,
)
from licenseid.resolvertypes import (
    CATEGORY_ORDER,
    LEXICAL_KINDS,
    LIST_PROVIDES,
    TRUST,
    Category,
    ListInfo,
    Resolution,
    Resolver,
    Step,
)

SPDX_LIST = "spdx-license-list"
# The kinds of step the SPDX License List supports; see ListInfo.provides.
_PROVIDES = ["deprecation", "ids", "names", "texts"]
_RE_NUMBERS = re.compile(r"\d+(?:\.\d+)*")
_RE_VERSION = re.compile(r"[vV]?\d+(?:\.\d+)*")
_OPERATORS = frozenset({"AND", "OR", "WITH"})
_RE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")
_RE_IDLIKE = re.compile(r"[\d.-]")
# Brackets other than around the whole value: "[MIT]", "MIT)" are no ID.
_RE_BRACKET = re.compile(r"[()\[\]{}]")
_RE_SQUARE = re.compile(r"[\[\]{}]")
# Characters that end a value after its last "+": white space and "+" itself.
_RE_TRAILING = re.compile(r"[\s+]+\Z")
# The longest expression read; one licence is MAX_KEY_INPUT characters or less.
MAX_EXPRESSION_CHARS = 2000
# A step kind that is not also a category name, mapped to the one it counts as.
_AS_CATEGORY = {kind: "lexical" for kind in LEXICAL_KINDS}


@dataclass
class _Found:
    """What the lookup decided, before it is put in the public shape."""

    expression: str | None = None
    steps: list[Step] = field(default_factory=list)
    expansions: list[Step] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    category: Category | None = None  # set where the lookup knows better


def resolve(value: str, db: LicenseDatabase | None = None) -> Resolution:
    """Resolve the declared licence *value*.

    Never raises on content: a value that names nothing is category
    ``unresolved``. A missing or unusable database raises
    :class:`licenseid.errors.DatabaseNotReadyError`, as ``match`` does.
    *db* defaults to the database at the default path.

    A deprecated ID that the List split into ``-only`` and ``-or-later`` is
    never narrowed: ``GPL-3.0`` comes back as written, category
    ``assumed_only``, with both candidates.
    """
    db = db or LicenseDatabase(get_default_db_path(), create=False)
    with db.reading():
        found = _lookup(db, value)
        lists = [_list_info(db)]
    return _resolution(value, found, lists)


def _lookup(db: LicenseDatabase, value: str) -> _Found:
    found = _Found()
    text = value.strip()
    if text != value:
        found.steps.append(_step("trim", True, value, text))
    text = _unbracketed(text, found)
    if not text or len(text) > MAX_EXPRESSION_CHARS or _has_control(text):
        found.category = "unresolved"
        return found
    if len(text) > MAX_KEY_INPUT:  # no ID is this long: only an expression is
        found.category = "expression" if _is_expression(db, text) else "unresolved"
        return found
    if text.endswith("+") and _plus(db, text, found):
        return found
    if _single(db, text, found):
        return found
    found.category = "expression" if _is_expression(db, text) else "unresolved"
    return found


def _unbracketed(text: str, found: _Found) -> str:
    """*text* without brackets around the whole of it, as a ``brackets`` step."""
    inner = without_outer_brackets(text)
    if inner == text:
        return text
    found.steps.append(_step("brackets", True, text, inner))
    return inner.strip()


def _is_expression(db: LicenseDatabase, text: str) -> bool:
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
    # One ID-shaped word (Foo-1.0, LicenseRef-foo) is a single licence, not an
    # expression of several.
    return len(operands) < len(tokens) and all(
        _RE_IDLIKE.search(token) or db.get_license_details(token) for token in operands
    )


def _has_control(text: str) -> bool:
    """Whether *text* holds a control character other than white space: not
    dropped as a separator, but no licence value."""
    return any(unicodedata.category(c) == "Cc" and not c.isspace() for c in text)


def _plus(db: LicenseDatabase, text: str, found: _Found) -> bool:
    """``X+`` as ``X-or-later`` where the List has that ID. Otherwise ``X+`` as
    written, after the deprecation of ``X`` (a rename is followed, an ID with
    no known successor is offered, not changed). A qualifier already stated
    (``X-only+``, ``X++``, ``X + +``) is malformed. Nothing is recorded in
    *found* unless the value names a licence."""
    core = _RE_TRAILING.sub("", text)
    attempt = _Found()
    stripped = text[:-1].rstrip()
    if stripped != text[:-1]:
        attempt.steps.append(_step("whitespace", True, text, stripped + "+"))
    base = _base(db, _unbracketed(stripped, attempt).strip())
    if base is None:
        if text[len(core) :].count("+") > 1 and _base(db, core):
            found.category = "malformed"
            return True
        return False
    license_id, steps = base
    if license_id.endswith(("-only", "-or-later", "+")):
        found.category = "malformed"  # the qualifier is stated; "+" adds a second
        return True
    found.steps.extend(attempt.steps + steps)
    or_later = f"{license_id}-or-later"
    if _in_use(db, or_later):
        found.expansions.append(_step("plus_to_or_later", True, text, or_later))
        found.expression = _canonical(db, or_later)
        return True
    _deprecation(db, license_id, found)
    found.expression = f"{found.expression}+"
    return True


def _single(db: LicenseDatabase, text: str, found: _Found) -> bool:
    """A value that names one licence: a stated qualifier ("GPLv2 or later"),
    or an ID, a name or a loose ID, then its deprecation."""
    named = granted_id_text(text) or declared_grant_id_text(text)
    if named is not None:
        named = named.rstrip(" \t([")  # "GPL-3.0 (or later)": the "(" is the grant's
        twice = declared_grant_id_text(named) or granted_id_text(named)
        if twice is not None and _base(db, twice.rstrip(" \t([")):
            found.category = "malformed"  # "X or later or later"
            return True
        base = _base(db, named.strip())
        if base is not None:
            return _grant(db, text, base, found)
    base = _base(db, text)
    if base is None:
        return False
    found.steps.extend(base[1])
    _deprecation(db, base[0], found)
    return True


def _grant(
    db: LicenseDatabase, text: str, base: tuple[str, list[Step]], found: _Found
) -> bool:
    """An ID followed by an "or later" grant. The grant is applied where the
    List has the ``-or-later`` ID; a qualifier already stated (``X-only or
    later``) is malformed; an ID with no ``-or-later`` form is unresolved,
    not read without its grant."""
    license_id, steps = base
    granted = loose_id(db, text)
    if license_id.endswith(("-only", "-or-later", "+")):
        found.category = "malformed"
    elif granted is None:
        found.category = "unresolved"
    else:
        found.steps.extend(steps)
        found.expansions.append(
            _step("stated_qualifier", True, text, granted[1], "or later stated")
        )
        found.expression = granted[1]
    return True


def _base(db: LicenseDatabase, text: str) -> tuple[str, list[Step]] | None:
    """The listed ID *text* names, and the steps from *text* to it: its own
    ID in other case, a listed name, or a loosely written ID."""
    details = db.get_license_details(text)
    if details is not None:
        license_id = details["license_id"]
        same = license_id == text
        return license_id, [] if same else [_step("id_case", True, text, license_id)]
    names = [
        row["license_id"]
        for row in db.get_all_names_and_ids()
        if not row["is_deprecated"] and row["name"].casefold() == text.casefold()
    ]
    if len(names) == 1:
        return names[0], [_step("listed_name", True, text, names[0])]
    if "+" in text or _RE_BRACKET.search(text):
        return None  # "+" and brackets are read by the caller, not folded away
    loose = loose_id(db, text)
    if loose is None:
        return None
    license_id = loose[0]["license_id"]
    return license_id, _spelling(text, license_id)


def _spelling(text: str, license_id: str) -> list[Step]:
    """The steps from a loose *text* to the *license_id* it names: its form
    (``separator``), its number (``version_spelling``), or both. What was
    applied is read back from the two strings; it does not decide the match."""
    steps = []
    skeleton = _RE_VERSION.sub("#", text).casefold()
    if skeleton != _RE_VERSION.sub("#", license_id).casefold():
        steps.append(_step("separator", True, text, license_id))
    if _RE_NUMBERS.findall(text) != _RE_NUMBERS.findall(license_id):
        steps.append(_step("version_spelling", True, text, license_id))
    return steps or [_step("separator", True, text, license_id)]


def _deprecation(db: LicenseDatabase, license_id: str, found: _Found) -> None:
    """Set the expression for the listed *license_id*, following a rename and
    declining to narrow a split ID."""
    details = db.get_license_details(license_id)
    if details is None or not details.get("is_deprecated"):
        found.expression = license_id
        return
    successor = details.get("superseded_by")
    if successor:
        found.steps.append(
            _step("deprecated_equal_successor", True, license_id, successor)
        )
        found.expression = _canonical(db, successor)
        return
    found.expression = license_id
    found.candidates = sorted(
        c for c in (f"{license_id}-only", f"{license_id}-or-later") if _in_use(db, c)
    )
    kind = "assumed_only" if found.candidates else "deprecated_ambiguous"
    found.expansions.append(_step(kind, False, license_id, license_id))


def _in_use(db: LicenseDatabase, license_id: str) -> bool:
    details = db.get_license_details(license_id)
    return details is not None and not details.get("is_deprecated")


def _canonical(db: LicenseDatabase, license_id: str) -> str:
    details = db.get_license_details(license_id)
    return details["license_id"] if details else license_id


def _step(kind: str, applied: bool, source: str, target: str, detail: str = "") -> Step:
    return {
        "kind": kind,
        "applied": applied,
        "from": source,
        "to": target,
        "list": SPDX_LIST if kind in LIST_PROVIDES else "",
        "detail": detail,
    }


def _category(found: _Found) -> Category:
    if found.category is not None:
        return found.category
    kinds = {_AS_CATEGORY.get(s["kind"], s["kind"]) for s in found.steps}
    kinds |= {s["kind"] for s in found.expansions}
    ranked = [c for c in CATEGORY_ORDER if c in kinds]
    return ranked[-1] if ranked else "exact"


def _list_info(db: LicenseDatabase) -> ListInfo:
    version = db.get_metadata().get("license_list_version")
    return {
        "id": SPDX_LIST,
        "name": "SPDX License List",
        "version": version,
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


def _resolution(value: str, found: _Found, lists: list[ListInfo]) -> Resolution:
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

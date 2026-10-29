# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A license ID written loosely: "Apache2", "GPLv3", "Apache_2.0",
"CC by 3 nl", "GPLv2 or any later version".

A short input and every ID get one version key (version_key); the input names
the one ID with its key. Tier 0 (licenseid.shorttext) asks this before its
exact and fuzzy matches.
"""

import re

from licenseid.classify import OR_LATER_PHRASE, is_negated
from licenseid.console import warn
from licenseid.identifiers import (
    normalize_identifier,
    qualify_trailing_grant,
    without_outer_brackets,
)
from licenseid.listlookup import ListedName, ListLookup
from licenseid.versionkey import MAX_KEY_INPUT, keyed_row, named_row, version_key

# The word a grant starts with, where OR_LATER_PHRASE starts at the version
# before it ("2 or later").
_RE_GRANT_WORD = re.compile(r"\bor\b", re.IGNORECASE)
# The words that may follow a grant: "version", "of the License".
_GRANT_WORDS = r"(?:\s+versions?)?(?:\s+of\s+(?:the|this)\s+licen[cs]e)?"
#: The words that may end a grant, as a pattern to match where it ends.
RE_GRANT_WORDS = re.compile(_GRANT_WORDS, re.IGNORECASE)
# What may follow the grant at the end of the text: those words, then
# punctuation, the bracket that closes "(or later)" or "[or later]".
_RE_GRANT_TAIL = re.compile(_GRANT_WORDS + r"[\s.,;:)\]]*", re.IGNORECASE)
# The WITH of a simple expression ("GPL2 WITH Classpath-exception-2.0"). The
# match starts at the first white space of a run (lookbehind): without it,
# every offset of a long run of spaces is tried and a split is quadratic
# (1.6 s at 20,000 spaces).
WITH_OPERATOR = re.compile(r"(?<!\s)\s+WITH\s+", re.IGNORECASE)


def loose_id(db: ListLookup, text: str) -> tuple[ListedName, str] | None:
    """The row *text* names loosely, and the ID it answers: the row's own,
    its successor if deprecated, or its -or-later form for a grant after it
    ("GPLv2 or any later version"). None for no row, or for two rows in use.
    """
    text = text.strip()
    if len(text) > MAX_KEY_INPUT:
        return None
    row = named_row(db, text)
    if row is not None:
        return row, resolved_id(db, row)
    return _granted(db, text)


def resolved_id(db: ListLookup, row: ListedName) -> str:
    """The ID a hit on *row* answers. A deprecated ID goes through
    normalize_identifier() for the same canonical-successor redirect the
    license_id= path gets; it can resolve to an expression."""
    lid = row["license_id"]
    return normalize_identifier(lid, db) if row["is_deprecated"] else lid


def narrowed(row_id: str, resolved: str, text: str) -> bool:
    """Whether the deprecated *row_id* was redirected to an -only form that
    *text* did not state. A deprecated ID written as is ("GPL-2.0") is
    -only by the License List's own definition, not by a guess."""
    if "-only" not in resolved or "only" in row_id.lower():
        return False
    return text.strip().casefold() != row_id.casefold()


def warn_narrowed(text: str, resolved: str) -> None:
    """Say that *text* was read as the narrower -only grant *resolved*."""
    warn(f"match: variant not stated: {shown(text)}; using {resolved}")


def shown(text: str) -> str:
    """*text* fit for a diagnostic's DETAIL: one line, printable, and no ";"
    (which starts the ACTION), each other character as "?"."""
    line = " ".join(text.split())
    return "".join(c if c.isprintable() and c != ";" else "?" for c in line)


def loose_with(db: ListLookup, text: str) -> tuple[str, str | None] | None:
    """*text*, a license written loosely WITH an exception, as an expression
    of the ID ("GPL2 WITH Classpath-exception-2.0" is GPL-2.0-only WITH
    Classpath-exception-2.0), and the loose license text if it was narrowed
    to -only (the caller warns once the expression resolves). None if *text*
    is no such expression. The exception is the caller's to check. Brackets
    around the whole are no part of it ("(GPL2 WITH Classpath-exception-2.0)"),
    as for a declared expression. Any other bracket is none of this shape:
    WITH takes a license ID, not a bracketed one ("(GPL2) WITH x"), and an
    unbalanced one ("(GPL2 WITH x") is no expression.
    """
    inner = without_outer_brackets(text.strip())
    parts = WITH_OPERATOR.split(inner)
    if len(parts) != 2 or "(" in inner or ")" in inner:
        return None
    found = loose_id(db, parts[0])
    if found is None or " WITH " in found[1]:
        return None  # no license, or one that carries an exception already
    row, resolved = found
    loose = parts[0] if narrowed(row["license_id"], resolved, parts[0]) else None
    return f"{resolved} WITH {parts[1].strip()}", loose


def granted_id_text(text: str) -> str | None:
    """The part of *text* before an "or later" grant that ends it ("GPLv2 or
    any later version" gives "GPLv2 "), or None for a text without one. Read
    by the one reader of the phrase (classify.OR_LATER_PHRASE)."""
    grant = OR_LATER_PHRASE.search(text)
    if grant is None or not _RE_GRANT_TAIL.fullmatch(text, grant.end()):
        return None
    start = grant.start()
    if text[start].isdigit():  # the phrase starts at the version: "2 or later"
        word = _RE_GRANT_WORD.search(grant.group(0))
        start += word.start() if word else 0
    return text[:start]


# The word a declared grant starts with. Only a word boundary, so finding
# the last one is one pass over the text, whatever its white space.
_RE_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)


def declared_grant_id_text(text: str) -> str | None:
    """The part of a declared value before an "or later" grant that ends it,
    with or without a number before the grant: "GPL-3.0-only or later" and
    "GPL-3.0-only (or later)" give "GPL-3.0-only". None for a value without
    one.

    The grant starts at the last "or" after white space or a bracket, and
    classify.OR_LATER_PHRASE judges it. That reader wants a number before a
    bare "or later", as prose also says "sooner or later"; a declared value
    has its ID there, so the phrase is read as after a number, unless a
    negation takes it back."""
    last = None
    for last in _RE_OR_WORD.finditer(text):
        pass
    if last is None:
        return None
    before = text[: last.start()]
    if not before or not (before[-1].isspace() or before[-1] in "(["):
        return None
    end = grant_end(text, last.start())
    if end is None or not _RE_GRANT_TAIL.fullmatch(text, end):
        return None
    return before.rstrip().rstrip("([").rstrip()


def grant_end(text: str, start: int) -> int | None:
    """Where the "or later" grant whose "or" is at *start* of *text* ends,
    or None if no grant starts there. Read by classify.OR_LATER_PHRASE, as
    after a number (a declared value has its ID before the "or"), unless a
    negation right before it takes it back ("not or later"). The compound
    reader of resolve() asks it at each "or" (decision Q14)."""
    grant = OR_LATER_PHRASE.match(text, start)  # sees "not" before it
    if grant is not None:
        return grant.end()
    if is_negated(text[max(0, start - 5) : start]):  # "xnot ": enough to judge
        return None
    probe = OR_LATER_PHRASE.match("1 " + text[start:])
    return None if probe is None else start + probe.end() - 2


def _granted(db: ListLookup, text: str) -> tuple[ListedName, str] | None:
    """*text* as a loose ID and an "or later" grant that ends it, read by the
    one reader of the phrase (classify.OR_LATER_PHRASE, through
    identifiers.qualify_trailing_grant): "GPLv2 or any later version" is
    GPL-2.0-or-later. None if the ID has no -or-later form: the grant is not
    dropped in silence."""
    named = granted_id_text(text)
    if named is None:
        return None
    row = keyed_row(db, version_key(named))
    if row is None:
        return None
    lid = row["license_id"]
    or_later = qualify_trailing_grant(lid, f"{lid} {text[len(named) :]}")
    return None if or_later == lid else (row, or_later)

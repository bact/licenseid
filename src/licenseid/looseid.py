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

from licenseid.classify import OR_LATER_PHRASE, grant_end
from licenseid.exprtokens import RE_TOKEN
from licenseid.identifiers import (
    ONLY_WORD,
    normalize_identifier,
    qualify_trailing_grant,
    without_outer_brackets,
)
from licenseid.listlookup import ListedName, ListLookup
from licenseid.plusoperator import PLUS_OPERATOR
from licenseid.versionkey import MAX_KEY_INPUT, keyed_row, named_row, version_key
from licenseid.warning import warn

# grant_end is classify's, the one probe of a grant after an ID; the
# compound reader (exprcanon) imports it from here.
__all__ = [
    "RE_GRANT_WORDS",
    "WITH_OPERATOR",
    "declared_grant_id_text",
    "drops_words",
    "grant_end",
    "granted_id_text",
    "loose_id",
    "loose_with",
    "narrowed",
    "narrowed_ids",
    "resolved_id",
    "restates_qualifier",
    "shown",
    "warn_narrowed",
]

# The word a grant starts with, where OR_LATER_PHRASE starts at the version
# before it ("2 or later").
_RE_GRANT_WORD = re.compile(r"\bor\b", re.IGNORECASE)
# The words that may follow a grant: "version", "of the License". A word
# ignores case in ASCII only ("(?a:"), as every keyword here does: Python's
# IGNORECASE alone folds "\u0130", "\u0131", "\u017f" and the Kelvin sign
# into "i", "s" and "k"; the white space between them stays Unicode's.
_GRANT_WORDS = r"(?:\s+(?a:versions?))?(?:\s+of\s+(?a:the|this)\s+(?a:licen[cs]e))?"
#: The words that may end a grant, as a pattern to match where it ends.
RE_GRANT_WORDS = re.compile(_GRANT_WORDS, re.IGNORECASE)
# What may follow the grant at the end of the text: those words, then
# punctuation, the bracket that closes "(or later)" or "[or later]".
_RE_GRANT_TAIL = re.compile(_GRANT_WORDS + r"[\s.,;:)\]]*", re.IGNORECASE)
# The WITH of a simple expression ("GPL2 WITH Classpath-exception-2.0"). The
# match starts at the first white space of a run (lookbehind): without it,
# every offset of a long run of spaces is tried and a split is quadratic
# (1.6 s at 20,000 spaces).
WITH_OPERATOR = re.compile(r"(?<!\s)\s+(?a:WITH)\s+", re.IGNORECASE)


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


def narrowed(row_id: str, resolved: str) -> bool:
    """Whether the deprecated *row_id* was redirected to an -only form that
    was not stated. A deprecated ID written as is ("GPL-2.0") is narrowed
    too: the List split it into -only and -or-later, and the -only guess is
    the narrower grant, not the declared one (decision F3 of the contract
    batch: guess narrow, mark not exact, warn)."""
    return "-only" in resolved and "only" not in row_id.lower()


def narrowed_ids(db: ListLookup, text: str, expression: str) -> bool:
    """Whether *expression*, the reading of the declared *text*, narrowed a
    deprecated ID of *text* to an -only form it does not state ("MIT OR
    GPL-2.0" read as "GPL-2.0-only OR MIT", "GPL-2.0-with-classpath-exception"
    as "GPL-2.0-only WITH Classpath-exception-2.0"). Each ID word is read
    alone, as normalize_identifier() reads it, and judged by :func:`narrowed`,
    the judge of every other path; its licence must be in *expression*, case
    ignored. An ID with the "+" operator after it states its grant, as the
    one reader of that operator (plusoperator.PLUS_OPERATOR) says: a "+"
    after a space or before a comma is none."""
    words = {word.casefold() for word in RE_TOKEN.findall(expression)}
    granted = {
        plus.end("id") for plus in PLUS_OPERATOR.finditer(text) if not plus["with"]
    }
    for token in RE_TOKEN.finditer(text):
        # A bracket, a "+" or an operator is never narrowed; reading each
        # alone cost seconds on 40,000 brackets around one ID.
        if token.end() in granted or not token.group(0)[0].isalnum():
            continue
        reading = normalize_identifier(token.group(0), db)
        if narrowed(token.group(0), reading) and (
            RE_TOKEN.findall(reading)[0].casefold() in words
        ):
            return True
    return False


def drops_words(leading: str, expression: str, value: str, *, whole: bool) -> bool:
    """Whether reading the declared *value* as *expression* (its *leading*
    expression, with a grant that follows it applied) would drop words that
    must not go: any words left over when the value is *whole* (a manifest
    field holds nothing else, so "MIT/Apache-2.0" is not MIT, and "GPL-2.0
    or later, and also MIT" is not GPL-2.0-or-later), or words that state
    the qualifier of a "+" again (:func:`restates_qualifier`). Only a grant
    that ends the value is no word left over (:func:`granted_id_text`, or
    :func:`declared_grant_id_text` for a bare "MIT or later")."""
    if leading == value:
        return False
    left = expression == leading or (
        granted_id_text(value) is None and declared_grant_id_text(value) is None
    )
    return left and (whole or restates_qualifier(leading, value))


def restates_qualifier(expression: str, value: str) -> bool:
    """Whether *value* states again, after its leading *expression* that ends
    in the "+" operator, the qualifier the "+" states ("LGPL-2.1+ only",
    "GPL-2.0+ or later"). ``match()`` refuses such a value (``qualifier
    stated twice``), so no reading may answer it without the words that
    contradict it. An ID that ends in ``-only`` keeps its reading
    ("GPL-2.0-only or (at your option) any later version" is GPL-2.0-only
    in a tag, test_spdx_tag_adversarial)."""
    if (RE_TOKEN.findall(expression) or [""])[-1] != "+":
        return False
    rest = value[len(expression) :].lstrip()
    if ONLY_WORD.match(rest):
        return True
    return declared_grant_id_text(value) == expression.rstrip()


def warn_narrowed(text: str, resolved: str) -> None:
    """Say that *text* was read as the narrower -only grant *resolved*."""
    warn("input", "variant not stated", shown(text), f"using {resolved}")


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
    loose = parts[0] if narrowed(row["license_id"], resolved) else None
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


def _granted(db: ListLookup, text: str) -> tuple[ListedName, str] | None:
    """*text* as a loose ID and an "or later" grant that ends it, read by the
    one reader of the phrase (classify.OR_LATER_PHRASE, through
    identifiers.qualify_trailing_grant): "GPLv2 or any later version" is
    GPL-2.0-or-later. None if the ID has no -or-later form: the grant is not
    dropped in silence, and the "+" it takes is the caller's to give (the
    leaf reader of match() gives it after the ID's deprecation)."""
    named = granted_id_text(text)
    if named is None:
        return None
    row = keyed_row(db, version_key(named))
    if row is None:
        return None
    lid = row["license_id"]
    or_later = qualify_trailing_grant(lid, f"{lid} {text[len(named) :]}")
    return None if or_later in (lid, f"{lid}+") else (row, or_later)

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

from licenseid.classify import OR_LATER_PHRASE
from licenseid.console import warn
from licenseid.database import LicenseDatabase
from licenseid.identifiers import (
    normalize_identifier,
    qualify_trailing_grant,
    replace_plus_operator,
    without_outer_brackets,
)
from licenseid.normalize import normalize_text
from licenseid.types import LicenseNameId

# The longest input read as a loose ID: the longest SPDX ID has 36
# characters. A longer input names no ID, and its key would cost a second
# normalize_text() of a text that can be megabytes in one word.
MAX_KEY_INPUT = 100
# "v" directly before a digit is a version prefix: "GPLv3", "v2.0".
_RE_VERSION_PREFIX = re.compile(r"v(?=\d)", re.IGNORECASE)
# A boundary between a letter and a digit: "Apache2", "0BSD".
_RE_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
# A whole version number whose every part after the major is 0: "2.0" and
# "2.0.0", not "1.2.0", "2.0.1" or "2.00". The lookarounds keep it to the
# whole number: no digit, and no digit and full stop, before it ("1.2.0"
# keeps its "2.0"), while a full stop alone is a separator ("Apache.2.0").
# After it, a full stop ends a sentence.
_RE_ZERO_VERSION = re.compile(r"(?<!\d)(?<!\d\.)(\d+)(?:\.0){1,2}(?!\.?\d)")
# The word a grant starts with, where OR_LATER_PHRASE starts at the version
# before it ("2 or later").
_RE_GRANT_WORD = re.compile(r"\bor\b", re.IGNORECASE)
# What may follow the grant at the end of the text: "version", "of the
# License", punctuation.
_RE_GRANT_TAIL = re.compile(
    r"(?:\s+versions?)?(?:\s+of\s+(?:the|this)\s+licen[cs]e)?[\s.,;:)]*",
    re.IGNORECASE,
)
# The WITH of a simple expression ("GPL2 WITH Classpath-exception-2.0").
_RE_WITH = re.compile(r"\s+WITH\s+", re.IGNORECASE)


def version_key(text: str) -> str:
    """*text* as a version-tolerant ID: "Apache2", "apache 2", "Apache_2.0"
    and "Apache-2.0" all give "apache 2", and "CC by 3 nl" gives the key of
    CC-BY-3.0-NL.

    Order matters: the "+" operator becomes the "or later" it means while
    the ID it follows is still one token (identifiers.replace_plus_operator,
    the reader expressions use), or GPL-2.0+ and GPL-2.0 would share a key;
    "_" becomes a space, as normalize_text() keeps it; the prefix goes before
    the split, or "GPLv3" would become "gplv 3"; the split goes before the
    fold, or "Apache2.0" would keep its ".0"; the fold reads the full stops
    normalize_text() drops ("2.0" and "2 0" differ). normalize_text() then
    folds case, dashes and punctuation as for an ID.
    """
    text = replace_plus_operator(text, " or later").replace("_", " ")
    text = _RE_VERSION_PREFIX.sub(" ", text)
    text = _RE_LETTER_DIGIT.sub(" ", text)
    text = _RE_ZERO_VERSION.sub(r"\1", text)
    return normalize_text(text)


def loose_id(db: LicenseDatabase, text: str) -> tuple[LicenseNameId, str] | None:
    """The row *text* names loosely, and the ID it answers: the row's own,
    its successor if deprecated, or its -or-later form for a grant after it
    ("GPLv2 or any later version"). None for no row, or for two rows in use.
    """
    text = text.strip()
    if len(text) > MAX_KEY_INPUT:
        return None
    row = _keyed_row(db, version_key(text))
    if row is not None:
        return row, resolved_id(db, row)
    return _granted(db, text)


def resolved_id(db: LicenseDatabase, row: LicenseNameId) -> str:
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


def loose_with(db: LicenseDatabase, text: str) -> tuple[str, str | None] | None:
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
    parts = _RE_WITH.split(inner)
    if len(parts) != 2 or "(" in inner or ")" in inner:
        return None
    found = loose_id(db, parts[0])
    if found is None or " WITH " in found[1]:
        return None  # no license, or one that carries an exception already
    row, resolved = found
    loose = parts[0] if narrowed(row["license_id"], resolved, parts[0]) else None
    return f"{resolved} WITH {parts[1].strip()}", loose


def _keyed_row(db: LicenseDatabase, key: str) -> LicenseNameId | None:
    """The one row whose ID has *key*. A row in use wins over a deprecated
    one ("GPL2+" is GPL-2.0-or-later, not GPL-2.0+); two in use are none."""
    rows = db.get_names_by_key(version_key).get(key, []) if key else []
    rows = [row for row in rows if not row["is_deprecated"]] or rows
    return rows[0] if len(rows) == 1 else None


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


# A grant that ends a declared value, number or not: "MIT or later",
# "GPL-3.0-only or later". classify.OR_LATER_PHRASE wants a number before "or
# later" because prose also says "sooner or later"; a value that is only an
# ID and a grant has no such doubt. The lookbehind starts a match only at the
# start of a run of white space, so a long run is not rescanned from each of
# its characters.
_RE_DECLARED_GRANT = re.compile(
    r"(?<!\s)\s+or\s+(?:any\s+)?(?:later|newer)(?:\s+versions?)?[\s.]*\Z", re.IGNORECASE
)


def declared_grant_id_text(text: str) -> str | None:
    """The part of a declared value before an "or later" grant that ends it,
    with or without a number before the grant: "GPL-3.0-only or later" gives
    "GPL-3.0-only". None for a value without one."""
    grant = _RE_DECLARED_GRANT.search(text)
    if grant is None:
        return None
    return text[: grant.start()]


def _granted(db: LicenseDatabase, text: str) -> tuple[LicenseNameId, str] | None:
    """*text* as a loose ID and an "or later" grant that ends it, read by the
    one reader of the phrase (classify.OR_LATER_PHRASE, through
    identifiers.qualify_trailing_grant): "GPLv2 or any later version" is
    GPL-2.0-or-later. None if the ID has no -or-later form: the grant is not
    dropped in silence."""
    named = granted_id_text(text)
    if named is None:
        return None
    row = _keyed_row(db, version_key(named))
    if row is None:
        return None
    lid = row["license_id"]
    or_later = qualify_trailing_grant(lid, f"{lid} {text[len(named) :]}")
    return None if or_later == lid else (row, or_later)

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The words of an SPDX licence expression: its operators, its IDs and its
references, the one definition of each (review gap G11).

``licenseid.identifiers`` tokenises tags and declared expressions with
:data:`RE_TOKEN` (the kind of each token: :func:`token_kind`); the compound
reader of ``match()`` (``licenseid.exprcanon``) finds its operators with
:data:`RE_OPERATOR`. White space is :data:`WHITE_SPACE`. Standard library
only, so any module can import it.
"""

import re
import unicodedata
from typing import Final

# An identifier starts and ends alphanumeric, so a trailing full stop is
# punctuation, not part of it. A ":" joins two identifiers
# (DocumentRef-x:LicenseRef-y is one ID) and is nothing on its own. "_" is no
# part of an SPDX ID but is part of a word, so "and_mask" stays one token
# instead of becoming the AND operator.
ID_WORD: Final = r"[a-zA-Z0-9]+(?:[._-]+[a-zA-Z0-9]+)*"
OPERATOR: Final = r"(?<![a-zA-Z0-9._:-])(?:AND|OR|WITH)(?![a-zA-Z0-9._:-])"
#: An operator word in any case, never inside an ID ("GPL-2.0-or-later").
RE_OPERATOR: Final = re.compile(OPERATOR, re.IGNORECASE)
#: A token of an expression: a bracket, an operator, a "+" or an ID.
RE_TOKEN: Final = re.compile(
    rf"\(|\)|{OPERATOR}|\+|{ID_WORD}(?::{ID_WORD})*",
    re.IGNORECASE,
)
OPERATORS: Final = ("AND", "OR", "WITH")
#: What may stand where an operand is expected; everything else follows one.
OPERAND_START: Final = ("ID", "(")

#: White space as Unicode's White_Space property has it: the characters
#: ``str.isspace()`` takes (``str.split()`` and ``str.strip()`` with no
#: argument read the same set) but U+001C to U+001F, the information
#: separators, which are control characters. ``match()`` refuses those
#: before any reader sees the value (``resolver._refusal``), so a reader
#: after that gate may use the ``str`` methods.
WHITE_SPACE: Final = (
    "\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)


def is_white_space(char: str) -> bool:
    """Whether *char* is white space (:data:`WHITE_SPACE`)."""
    return char in WHITE_SPACE


def token_kind(text: str) -> str:
    """Which part of an expression a token can be: ``(``, ``)``, ``+``,
    ``OP`` or ``ID``."""
    if text in ("(", ")", "+"):
        return text
    return "OP" if text.upper() in OPERATORS else "ID"


def continues_after(value: str, end: int) -> bool:
    """Whether an expression goes on after *end*: an operator joined to what
    stands before it by white space alone."""
    token = RE_TOKEN.search(value, end)
    if token is None or token_kind(token.group(0)) != "OP":
        return False
    return not value[end : token.start()].strip()


def closing_brackets_end(value: str, pos: int, depth: int) -> int | None:
    """Where the *depth* closing brackets after *pos* end, when white space
    alone stands before each; None if they are not there."""
    for _ in range(depth):
        token = RE_TOKEN.search(value, pos)
        if token is None or token.group(0) != ")" or value[pos : token.start()].strip():
            return None
        pos = token.end()
    return pos


def licence_after(licence: str, before: str, token: re.Match[str]) -> str:
    """The licence an "or later" grant after *token* would qualify: *token*
    if it is an ID and no exception (*before*, the token before it, is no
    WITH), else *licence*, the one before it."""
    if token_kind(token[0]) == "ID" and before.upper() != "WITH":
        return token[0]
    return licence


def cut_inside_word(text: str, end: int) -> bool:
    """Whether a token of :data:`RE_TOKEN` that ends at *end* of *text* was
    cut inside a word: an ID ends there, and a letter, a digit or a
    combining mark follows it, after the ``.``, ``-``, ``_`` or ``:`` that
    join the parts of an ID (``LicenseRef-café`` gives ``LicenseRef-caf``,
    as an idstring holds ASCII only). A white space or another mark after
    the ID ends it whole (``MIT, with additions``, ``MIT€``)."""
    if not end or not text[end - 1].isalnum():
        return False  # a bracket or a "+" ends no word
    index = end
    while index < len(text) and text[index] in "._:-":
        index += 1
    if index == len(text):
        return False
    char = text[index]
    return char.isalnum() or unicodedata.category(char).startswith("M")


# A whole reference, its idstrings as SPDX defines them
# (idstring = 1*(ALPHA / DIGIT / "-" / "."); ABNF strings ignore case).
_DOCUMENT_REF = r"(?:DocumentRef-[A-Za-z0-9.-]+:)?"
_RE_WHOLE_LICENSE_REF = re.compile(
    rf"{_DOCUMENT_REF}LicenseRef-[A-Za-z0-9.-]+", re.IGNORECASE
)
_RE_WHOLE_ADDITION_REF = re.compile(
    rf"{_DOCUMENT_REF}AdditionRef-[A-Za-z0-9.-]+", re.IGNORECASE
)


#: The prefixes of a reference in SPDX's case, by their case-folded form.
_REF_PREFIXES: Final = {
    prefix.casefold(): prefix
    for prefix in ("DocumentRef-", "LicenseRef-", "AdditionRef-")
}


def canonical_ref(text: str) -> str:
    """*text*, one whole reference (:func:`is_license_ref` or
    :func:`is_addition_ref`), with its prefixes in SPDX's case and its
    idstrings as written: ``licenseref-Foo`` is ``LicenseRef-Foo``. The
    SPDX specification matches an identifier in any case (annex "SPDX
    license expressions", case sensitivity), and its grammar writes the
    prefixes as ABNF strings, which ignore case; an idstring is the
    author's own, so its case is kept, not guessed."""
    return ":".join(_canonical_prefix(part) for part in text.split(":"))


def _canonical_prefix(part: str) -> str:
    """*part*, one ``Prefix-idstring`` of a reference, its prefix in SPDX's
    case; as given if the prefix is none of :data:`_REF_PREFIXES`."""
    cut = part.find("-") + 1
    return _REF_PREFIXES.get(part[:cut].casefold(), part[:cut]) + part[cut:]


def is_license_ref(text: str) -> bool:
    """Whether *text* is one ``LicenseRef-*``, with its ``DocumentRef-*:`` if
    any, and nothing else."""
    return _RE_WHOLE_LICENSE_REF.fullmatch(text) is not None


def is_addition_ref(text: str) -> bool:
    """Whether *text* is one ``AdditionRef-*`` (SPDX 3: an exception of the
    author's own, beside ``LicenseRef-*``), with its ``DocumentRef-*:`` if
    any, and nothing else."""
    return _RE_WHOLE_ADDITION_REF.fullmatch(text) is not None

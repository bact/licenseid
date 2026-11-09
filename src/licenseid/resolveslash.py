# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A ``/`` between licence IDs, read as ``OR`` (roadmap item 43).

Cargo documents ``MIT/Apache-2.0`` as ``MIT OR Apache-2.0``, and the crates
that declare it are many. SPDX has no ``/``, so the reading is narrow: it
must never turn a name that holds a slash (``TCL/TK``, ``University of
Illinois/NCSA``) or a path (``LICENSE/MIT``) into two licences.

A value is read when it is the whole of a declared value and every piece
between its ``/`` is an operand:

- a List licence ID spelt exactly as listed (no case fold: ``zlib/libpng``
  would be ``Libpng OR Zlib``, and the author means the one licence
  ``zlib-acknowledgement``), with a ``+`` if the "+" reader takes one
  (:mod:`licenseid.plusoperator`; not after ``-only`` or ``-or-later``), or
- ``LicenseRef-`` and ``[A-Za-z0-9.-]`` characters, with no ``+``.

At least one operand is a List ID; an exception, ``NONE``, a name, a
version spelling (``Apache2``) or any other word is no operand. A piece is
cut at ``/`` and trimmed of spaces and tabs only, with no regular
expression (``[ \\t]*/[ \\t]*`` is quadratic on a long run of spaces); a
URL (:func:`licenseid.urlkey.is_url`) is never read. An empty piece
(``MIT//ISC``, ``/MIT``) refuses the value. The value is read as ``A OR B``
would be (:func:`licenseid.resolvecompound.read_compound`), so the order and
the duplicates are the compound reader's, with one ``separator`` step
(``slash as OR``) first.

:data:`REFUSED_PAIRS` holds a pair that is one licence under a name with a
slash that is also two IDs. Add one only with a measured count.

Standard library and ``licenseid`` modules only.
"""

import re
from typing import Final

from licenseid.listlookup import ListLookup
from licenseid.plusoperator import strip_plus_operator
from licenseid.resolvecompound import read_compound
from licenseid.resolveleaf import Found
from licenseid.resolvertypes import Operand, step
from licenseid.resolvesemicolon import Part
from licenseid.urlkey import is_url

#: The step ``detail`` of the reading.
DETAIL: Final = "slash as OR"
#: The most operands read (the compound reader's limit on operators).
MAX_OPERANDS: Final = 150
#: The longest value read, once the "/" are ``" OR "`` (the resolver's
#: ``MAX_EXPRESSION_CHARS``; a test holds them equal).
MAX_JOINED: Final = 2000
#: Pairs of IDs that are one licence's name (case folded): ``MIT/X11`` is the
#: Debian name of X11, and OSI calls Zlib "the zlib/libpng license". A value
#: with both IDs of a pair, anywhere, is refused (``docs/resolve.md``).
REFUSED_PAIRS: Final = frozenset({("mit", "x11"), ("libpng", "zlib")})
_RE_REF: Final = re.compile(r"LicenseRef-[A-Za-z0-9.-]+")
_TRIM: Final = " \t"


def slash_parts(text: str, db: ListLookup) -> list[Part] | None:
    """The operands of *text* if it is licence IDs joined by ``/`` (see the
    module docstring), each with where it starts in *text*, else None."""
    if "/" not in text or is_url(text):
        return None
    pieces = text.split("/")
    if not 2 <= len(pieces) <= MAX_OPERANDS:
        return None
    parts, offset, listed = [], 0, False
    for piece in pieces:
        part = piece.strip(_TRIM)
        if not part:
            return None
        kind = _operand_kind(part, db)
        if kind is None:
            return None
        listed = listed or kind
        parts.append(Part(part, offset + len(piece) - len(piece.lstrip(_TRIM))))
        offset += len(piece) + 1
    if not listed or _has_refused_pair(parts):
        return None
    too_long = len(" OR ".join(part.text for part in parts)) > MAX_JOINED
    return None if too_long else parts


def _has_refused_pair(parts: list[Part]) -> bool:
    """Whether *parts* hold both IDs of a pair of :data:`REFUSED_PAIRS`, in
    any order and place, a "+" left off."""
    named = {part.text.rstrip("+").casefold() for part in parts}
    return any(first in named and second in named for first, second in REFUSED_PAIRS)


def slash_expression(text: str, db: ListLookup) -> str | None:
    """*text*, which is a whole declared value, as the expression ``A OR B``
    its IDs joined by ``/`` stand for (``MIT/Apache-2.0`` is ``MIT OR
    Apache-2.0``), else None. The caller reads the expression: this does
    not judge it."""
    parts = slash_parts(text, db)
    if parts is None:
        return None
    return " OR ".join(dict.fromkeys(part.text for part in parts))


def _operand_kind(part: str, db: ListLookup) -> bool | None:
    """True for a List licence ID spelt as listed (with a "+" if it takes
    one), False for a ``LicenseRef-*``, None for anything else."""
    if _RE_REF.fullmatch(part):
        return False
    base = strip_plus_operator(part)
    if base != part and base.endswith(("-only", "-or-later")):
        return None
    row = db.get_license_details(base)
    return True if row and row.get("license_id") == base else None


def read_slash_list(
    db: ListLookup, text: str, start: int, found: Found
) -> tuple[list[Operand], bool] | None:
    """Read *text* (which starts at code point *start* of the raw input) as
    licences joined by ``/`` into *found*: the operands, one for each piece
    at its own span, and whether the parser ran. None, with *found* as it
    was, for any other value, or when the compound reader gives no
    expression."""
    parts = slash_parts(text, db)
    if parts is None:
        return None
    joined = " OR ".join(part.text for part in parts)
    read = Found(steps=list(found.steps), floor=found.floor)
    compound = read_compound(db, joined, 0, read)
    if not compound.claimed or read.expression is None:
        return None
    if len(compound.operands) != len(parts):
        return None
    operands = []
    for part, operand in zip(parts, compound.operands):
        if operand["text"] != part.text:
            return None
        operand["span"] = [start + part.start, start + part.start + len(part.text)]
        operands.append(operand)
    read.steps.insert(len(found.steps), step("separator", True, text, joined, DETAIL))
    found.expression, found.category = read.expression, read.category
    found.steps, found.expansions = read.steps, read.expansions
    found.candidates = read.candidates
    return operands, compound.parsed

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Read a declared value that is written in quotes: ``"MIT"``, ``'MIT'``,
``“MIT”``, ``"MIT`` (task T6b, decision Q12).

The rule: quote marks that delimit the whole value are removed, and the
value is read as what they enclose. The marks are those of
``normalize.QUOTE_KIND`` (the quotes of SPDX matching guideline 4, the ASCII
apostrophe and the grave accent), the one definition; a mark is "double" or
"single", and two marks of one kind pair, whichever opens.

1. White space at either end is skipped.
2. While the first and the last mark are of one kind, both are removed (one
   layer: ``""MIT""`` and ``'"MIT"'`` are two).
3. If one end still has a quotation mark (``STRAY_MARKS``: not a prime or
   a modifier letter) and the other has no mark, that mark is removed
   (``"MIT``, ``MIT"``: *unbalanced*). Marks of two kinds at the two ends
   (``"MIT'``) leave the value as it is: which of them is the stray one is
   not known.
4. What remains must hold no quote mark except an apostrophe inside a word
   (``AMD's``: a single mark with a letter or digit on both sides), and must
   not be empty. Otherwise the value is left as it is.

Why this asserts nothing the author did not write. A quote delimits a text;
it does not qualify it. ``"MIT"`` and ``MIT`` name the same licence in every
convention that has quotes (JSON, TOML and YAML strings, Markdown, prose),
so removing the marks that enclose the whole value drops no word, no doubt
and no condition. The marks that *do* qualify are the ones inside: ``MIT
"or" Apache-2.0``, ``GPL "2.0"`` and ``Apache "2.0"`` quote a word of a
longer text, and what a writer means by that (a term, a quotation, scare
quotes) is not known. Step 4 keeps them out: a value with a mark left is not
read here, and the drop guard (:mod:`licenseid.dropguard`) refuses it as
before. It is also what stops ``"MIT" or "Apache-2.0"`` from reading as the
text ``MIT" or "Apache-2.0`` inside one pair. A mark on one end only
(unbalanced) is a typo or a cut value; it is read, and says so in the step
detail, because the author's text was not complete.

The whole value first, then each operand. ``match()`` calls
:func:`unquote` on the whole value, once, before any other reading;
``GPL-2.0+``, ``X WITH Y`` and ``GPLv2 or later`` inside the quotes are then
read as they are outside, and ``"MIT OR Apache-2.0"`` is unquoted once. The
compound reader (``licenseid.resolvecompound``) then calls it on each
operand, so that ``MIT OR "Apache-2.0"`` reads as ``MIT OR Apache-2.0``. It
takes a balanced pair only: a mark on one end of an operand may be the
other end of a pair around several (``"MIT OR "Apache-2.0"``), and the drop
guard refuses it.

One end mark (``.``, ``,``, ``;`` or ``:``) after the closing marks
(``"MIT".``) is an ending, left off first (:func:`ended_quote`), as it is
before the marks (``MIT,"``). A mark inside the marks as well (``"MIT.".``)
is a second mark, and the value is refused.

Standard library, ``licenseid.dropguard`` and ``licenseid.normalize`` only.
"""

from typing import Final, NamedTuple

from licenseid.dropguard import ends_in_mark, trim_end_mark
from licenseid.normalize import QUOTE_KIND

#: The marks that may stand alone on one end (unbalanced): quotation
#: punctuation. The primes and the modifier letters (``GPL-2.0′``, ``ʻMIT``,
#: ``MITʼ``) are marks that pair but are too often a unit, a letter or a
#: footnote to be taken off alone.
STRAY_MARKS: Final = frozenset(QUOTE_KIND) - frozenset("′″‴ʹʺʻʼʽ")


class Unquoted(NamedTuple):
    """A value without the quotes around it, and how they stood."""

    text: str
    balanced: bool  # False: a mark on one end only
    detail: str  # "balanced", "balanced, N layers", "unbalanced, start|end"
    start: int  # where ``text`` starts in the value given to unquote


def unquote(text: str) -> Unquoted | None:
    """*text* without the quote marks that delimit all of it (see the module
    docstring), or None if there are none to remove or it is not safe to.
    Linear in the length of *text*: it moves two indices and slices once."""
    lo, hi = _skip_space(text, 0, len(text))
    layers = 0
    while hi - lo > 1:
        kind = QUOTE_KIND.get(text[lo])
        if kind is None or kind != QUOTE_KIND.get(text[hi - 1]):
            break
        lo, hi = _skip_space(text, lo + 1, hi - 1)
        layers += 1
    side = _stray_mark(text, lo, hi)
    if side == "start":
        lo = _skip_space(text, lo + 1, hi)[0]
    elif side == "end":
        hi = _skip_space(text, lo, hi - 1)[1]
    core = text[lo:hi]
    if not core or (layers == 0 and not side) or _has_inner_mark(core):
        return None
    if side:
        return Unquoted(core, False, f"unbalanced, {side}", lo)
    detail = "balanced" if layers == 1 else f"balanced, {layers} layers"
    return Unquoted(core, True, detail, lo)


def ended_quote(text: str) -> str | None:
    """*text* without the one end mark that follows its closing quote marks
    (``"MIT".``, ``“MIT”;``, and ``MIT".`` with a mark on that end only), or
    None. None when more than one mark ends *text* (``"MIT"..``,
    ``"MIT".,``), when the marks are not ones to take off, or when what they
    enclose ends in a mark too, behind a bracket or not (``"MIT.".``,
    ``"(MIT;)".``; the dot of a ``LicenseRef-a.`` is no mark). The end mark
    and the one inside are judged by :mod:`licenseid.dropguard`."""
    rest = trim_end_mark(text)
    if rest is None or rest[-1] not in QUOTE_KIND:
        return None
    inner = unquote(rest)
    if inner is None or ends_in_mark(inner.text):
        return None
    return rest


def _skip_space(text: str, lo: int, hi: int) -> tuple[int, int]:
    """*lo* and *hi* moved in over white space."""
    while lo < hi and text[lo].isspace():
        lo += 1
    while hi > lo and text[hi - 1].isspace():
        hi -= 1
    return lo, hi


def _stray_mark(text: str, lo: int, hi: int) -> str:
    """Which end of ``text[lo:hi]`` alone has a quote mark: ``start``,
    ``end`` or empty. Marks at both ends that did not pair (``"MIT'``) are
    empty too: which is the stray one is not known, and the mark left in
    the value makes :func:`_has_inner_mark` refuse it."""
    if lo >= hi:
        return ""
    start, end = text[lo] in STRAY_MARKS, text[hi - 1] in STRAY_MARKS
    if start and not end:
        return "start"  # a prime at the other end stays, and is refused
    if end and not start:
        return "end"
    return ""


def _has_inner_mark(core: str) -> bool:
    """Whether *core* holds a quote mark that is not an apostrophe inside a
    word (a single mark with a letter or digit on each side)."""
    for index, char in enumerate(core):
        kind = QUOTE_KIND.get(char)
        if kind is None:
            continue
        inside_word = (
            kind == "single"
            and 0 < index < len(core) - 1
            and core[index - 1].isalnum()
            and core[index + 1].isalnum()
        )
        if not inside_word:
            return True
    return False

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Control and format characters at the ends of a declared value, and
beside its white space.

``MIT\\u202e`` or ``\\ufeffMIT`` is the value ``MIT`` with a character that
shows nothing. Such a character at an *end* changes nothing that is shown:
no text stands beyond it for a bidirectional (bidi) control to reorder. So
:func:`strip_hidden` leaves it off, as white space is left off.

Not at the start, for a bidi control: ``\\u202eMIT`` shows as ``TIM``, text
that reads other than it shows. Nor inside a word (:func:`space_out_hidden`
makes only a format character beside white space a space), nor NUL (a sign
of binary data): ``resolve()`` refuses those (``resolver._refusal``).

Inside the quote marks around the whole value (``"MIT\\u200b"``) the same
reading holds for a *plain* format character (:func:`strip_plain_format`): the
closing mark stands beyond it, so a bidi control there could still reorder
what follows, and a control character (``Cc``) there is no format.

A *zero-width* character (:data:`ZERO_WIDTH`) left off is white space: the
value is the one written. Any other is a cut, as a dropped mark is: a bidi
control can still reorder what a reader shows after the value, a control
character may stand for a lost field, and a run of Unicode tag characters is
text no one sees (``MIT`` with "GPL-3.0" after it in tag characters).

Standard library only.
"""

import unicodedata
from typing import Final

from licenseid.exprtokens import is_white_space

#: Bidi controls: the Arabic letter mark, the left-to-right and
#: right-to-left marks, the embeddings and overrides (U+202A to U+202E) and
#: the isolates (U+2066 to U+2069).
BIDI_CONTROLS: Final = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)

#: The zero-width characters a paste, an editor or a byte order mark leaves:
#: zero width space, zero width non-joiner and joiner, word joiner, the byte
#: order mark (zero width no-break space) and the soft hyphen. Each is
#: Default_Ignorable (Unicode Standard Annex 44), carries no text and reorders
#: nothing.
ZERO_WIDTH: Final[frozenset[str]] = frozenset("\u200b\u200c\u200d\u2060\ufeff\u00ad")


def only_zero_width(removed: str) -> bool:
    """Whether every character of *removed*, what was left off a value, is
    white space or in :data:`ZERO_WIDTH` (True for nothing)."""
    return all(char in ZERO_WIDTH or is_white_space(char) for char in removed)


def left_off(value: str, kept: str, start: int) -> str:
    """What :func:`strip_hidden` or :func:`strip_plain_format` left off the
    ends of *value* to keep *kept*, which starts at *start* in it."""
    return value[:start] + value[start + len(kept) :]


def spaced_out(value: str, spaced: str) -> str:
    """The characters :func:`space_out_hidden` made spaces in *value* to give
    *spaced*."""
    return "".join(old for old, new in zip(value, spaced) if old != new)


def cuts_hidden(value: str) -> bool:
    """Whether reading *value* as ``resolve()`` does, without the hidden
    characters at its ends and beside white space, leaves off one that is not
    zero-width: the value read is then a cut, not the one written."""
    shown, start = strip_hidden(value)
    removed = left_off(value, shown, start) + spaced_out(shown, space_out_hidden(shown))
    return not only_zero_width(removed)


def is_hidden(char: str) -> bool:
    """Whether *char* is a control or format character that is not white
    space and not NUL (categories ``Cc`` and ``Cf``)."""
    return (
        char != "\x00"
        and not is_white_space(char)
        and unicodedata.category(char) in ("Cc", "Cf")
    )


def strip_hidden(value: str) -> tuple[str, int]:
    """*value* without the hidden characters at its ends, and how many were
    left off the start. White space beside them goes too. A value with no
    hidden character at an end, one of nothing else, or one with a bidi
    control at the start is returned as it is (the caller refuses the last
    two)."""
    start, end = 0, len(value)
    while start < end and (is_hidden(value[start]) or is_white_space(value[start])):
        if value[start] in BIDI_CONTROLS:
            return value, 0
        start += 1
    while end > start and (is_hidden(value[end - 1]) or is_white_space(value[end - 1])):
        end -= 1
    if start == end or not any(is_hidden(c) for c in value[:start] + value[end:]):
        return value, 0
    return value[start:end], start


def strip_plain_format(text: str) -> tuple[str, int]:
    """*text*, the inside of a value's quote marks, without the plain format
    characters (``Cf``, no bidi control) and the white space at its ends, and
    how many were left off the start. *text* is returned as it is when it
    has none at an end, when nothing else is left, or when a bidi control or
    a control character (``Cc``) stands beyond them: it is then still
    refused (``resolver._refusal``), for the first character it names."""
    start, end = 0, len(text)
    while start < end and _is_trimmed(text[start]):
        start += 1
    while end > start and _is_trimmed(text[end - 1]):
        end -= 1
    if start == end or not any(_is_plain_format(c) for c in text[:start] + text[end:]):
        return text, 0
    if _is_unplain(text[start]) or _is_unplain(text[end - 1]):
        return text, 0
    return text[start:end], start


def _is_unplain(char: str) -> bool:
    """Whether *char* is a bidi control or a control character (``Cc``)."""
    return char in BIDI_CONTROLS or unicodedata.category(char) == "Cc"


def _is_trimmed(char: str) -> bool:
    """Whether :func:`strip_plain_format` leaves *char* off an end."""
    return is_white_space(char) or _is_plain_format(char)


def space_out_hidden(value: str) -> str:
    """*value* with each format character (``Cf``, not a bidi control) of a
    run that touches white space made a space, one code point for one, so a
    span still indexes it: ``MIT OR\\u200b ISC`` reads as ``MIT OR  ISC``.
    A run between two other characters (``M\\u200bIT``) says something, as a
    control character or a bidi control anywhere does, and is left; so is a
    value of nothing else."""
    if all(is_white_space(char) or _is_plain_format(char) for char in value):
        return value  # nothing to read: the caller refuses it
    chars = list(value)
    index, size = 0, len(chars)
    while index < size:
        if not _is_plain_format(chars[index]):
            index += 1
            continue
        end = index
        while end < size and _is_plain_format(chars[end]):
            end += 1
        if (index and is_white_space(chars[index - 1])) or (
            end < size and is_white_space(chars[end])
        ):
            chars[index:end] = " " * (end - index)
        index = end
    return "".join(chars)


def _is_plain_format(char: str) -> bool:
    """Whether *char* is a format character that is no bidi control."""
    return char not in BIDI_CONTROLS and unicodedata.category(char) == "Cf"

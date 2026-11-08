# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Control and format characters at the ends of a declared value.

``MIT\\u202e`` or ``\\ufeffMIT`` is the value ``MIT`` with a character that
shows nothing. Such a character at an *end* changes nothing that is shown:
no text stands beyond it for a bidirectional (bidi) control to reorder. So
:func:`strip_hidden` leaves it off, as white space is left off.

Not at the start, for a bidi control: ``\\u202eMIT`` shows as ``TIM``, text
that reads other than it shows. Nor inside the value, nor NUL (a sign of
binary data): ``resolve()`` refuses those (``resolver._refusal``).

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


def space_out_hidden(value: str) -> str:
    """*value* with each format character (``Cf``, not a bidi control) of a
    run that touches white space made a space, one code point for one, so a
    span still indexes it: ``MIT OR\u200b ISC`` reads as ``MIT OR  ISC``.
    A run between two other characters (``M\u200bIT``) says something, as a
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

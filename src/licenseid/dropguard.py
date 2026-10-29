# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The characters a loose reading must not drop.

A loose ID ("Apache 2.0", "Apache_2.0", "Apache-2.0,") is read by leaving
out everything that is not a letter or a digit. Most of what it leaves out is
a separator and says nothing. Some of it says something: ``Apache 2.0?`` is
the author's doubt, ``MIT*`` points to a footnote, ``MIT`` followed by U+FFFD
is a decoding error. Reading them as ``Apache-2.0`` and ``MIT`` asserts what
the author did not write. :func:`dropped` names the characters that would be
lost, so that the caller can refuse the reading.

Allowed to drop: white space, ``_``, ``.``, a dash and one comma at the end.
A dash is a character of ``normalize.RE_DASHES`` (the hyphen-minus, the
Unicode hyphens and dashes, and the minus sign U+2212, as SPDX matching
guideline 4 has it): the set ``normalize_text`` folds, so there is one
definition. Everything else that is not alphanumeric counts, and so does any
character of ``normalize.RE_QUOTES`` (some are letters, such as the modifier
letter U+02BC): a quoted value is the business of a later rule that reads
quotes as a whole. Standard library and ``licenseid.normalize`` only.
"""

from typing import Final

from licenseid.normalize import RE_DASHES, RE_QUOTES

_ALLOWED: Final = frozenset("_.")


def _is_separator(char: str) -> bool:
    """Whether dropping *char* says nothing: white space, ``_``, ``.`` or a
    dash."""
    return char.isspace() or char in _ALLOWED or RE_DASHES.match(char) is not None


def dropped(text: str) -> str:
    """The characters of *text* a loose reading would drop that are not
    separators, each once, in the order they first appear; empty if there are
    none. One comma at the end (after white space) is allowed, a second is not.
    """
    body = text.rstrip()
    body = body.removesuffix(",")
    seen: dict[str, None] = {}
    for char in body:
        if RE_QUOTES.match(char) or not (char.isalnum() or _is_separator(char)):
            seen[char] = None
    return "".join(seen)


def code_points(chars: str) -> str:
    """*chars* as code points, space separated: ``U+003F U+0021``. Safe to
    show, whatever the characters are (a lone surrogate, a mark)."""
    return " ".join(f"U+{ord(char):04X}" for char in chars)

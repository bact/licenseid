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

Allowed to drop: white space, ``-``, ``_``, ``.``, a Unicode dash (category
``Pd``: an en dash, a hyphen U+2010 are hyphens in disguise) and one comma at
the end. Everything else that is not alphanumeric counts, quotes too (a
quoted value is the business of a later rule that reads them as a whole).
Standard library only.
"""

import unicodedata
from typing import Final

_ALLOWED: Final = frozenset("-_.")


def _is_separator(char: str) -> bool:
    """Whether dropping *char* says nothing: white space, ``-``, ``_``, ``.``
    or a Unicode dash."""
    return char.isspace() or char in _ALLOWED or unicodedata.category(char) == "Pd"


def dropped(text: str) -> str:
    """The characters of *text* a loose reading would drop that are not
    separators, each once, in the order they first appear; empty if there are
    none. One comma at the end (after white space) is allowed, a second is not.
    """
    body = text.rstrip()
    body = body.removesuffix(",")
    seen: dict[str, None] = {}
    for char in body:
        if not char.isalnum() and not _is_separator(char):
            seen[char] = None
    return "".join(seen)

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

Marks of dash or dots that stand alone at either end of a value (``MIT -``,
``-- MIT``, ``MIT ...``) are dropped marks too: they say the value goes on or
is a list item. Dots touching the word (``MIT...``) are the end of a sentence
and pass.

Allowed to drop: white space, ``_``, ``.``, a dash and one comma at the end.
A dash is a character of ``normalize.RE_DASHES`` (the hyphen-minus, the
Unicode hyphens and dashes, and the minus sign U+2212, as SPDX matching
guideline 4 has it): the set ``normalize_text`` folds, so there is one
definition. Everything else that is not alphanumeric counts, and so does any
character of ``normalize.RE_QUOTES`` (some are letters, such as the modifier
letter U+02BC). Quote marks that delimit the whole value are taken off before
this guard sees it (:mod:`licenseid.quotes`); the ones it still sees are inside
the value (``Apache "2.0"``) and may qualify it.

The same guard covers words. ``normalize_text`` takes off the line-anchored
list and comment markers of the SPDX matching guidelines (5 and 6: ``REM``,
``1.``, ``x.``, ``iv.``), which are right for a licence text and wrong for a
declared value: ``REM MIT`` is not ``MIT``. :func:`dropped_words` finds them by
reading the value twice, with and without those rules, so there is no list of
markers here to keep in step. Case, ``v`` before a number and the separators
above are spelling and drop nothing. Standard library, ``licenseid.normalize``
and ``licenseid.versionkey`` only.
"""

from collections import Counter
from typing import Final

from licenseid.normalize import RE_DASHES, RE_QUOTES
from licenseid.versionkey import version_key

_ALLOWED: Final = frozenset("_.")


def _is_separator(char: str) -> bool:
    """Whether dropping *char* says nothing: white space, ``_``, ``.`` or a
    dash."""
    return char.isspace() or char in _ALLOWED or RE_DASHES.match(char) is not None


def dropped(text: str) -> str:
    """The characters of *text* a loose reading would drop that are not
    separators, each once, in the order they first appear; empty if there are
    none. One comma at the end (after white space) is allowed, a second is not.
    A dash or dot token at either end of a text of several words (``MIT -``,
    ``-- MIT``) is a dropped mark too.
    """
    body = text.rstrip()
    body = body.removesuffix(",")
    seen: dict[str, None] = {}
    for char in body:
        if RE_QUOTES.match(char) or not (char.isalnum() or _is_separator(char)):
            seen[char] = None
    for char in _dangling(body):
        seen[char] = None
    return "".join(seen)


def _dangling(text: str) -> str:
    """The marks of a first or last white-space-separated token of *text* that
    is nothing but dashes and dots, when another token stands beside it."""
    tokens = text.split()
    if len(tokens) < 2:
        return ""
    ends = (tokens[0], tokens[-1])
    return "".join(
        token
        for token in ends
        if all(char == "." or RE_DASHES.match(char) for char in token)
    )


def has_dangling_marks(text: str) -> bool:
    """Whether *text* has a dash or dot token at either end (``MIT ...``);
    the prose forms, which leave dots off the end, refuse such a value."""
    return bool(_dangling(text.rstrip().removesuffix(",")))


def dropped_words(text: str) -> str:
    """The words of *text* that a loose reading would drop, each once, in
    order, space separated and in lower case; empty if there are none. A
    word is a run of letters and digits that ``normalize_text`` keeps unless
    a line rule (a list marker ``1.``, ``iv.``, a comment marker ``REM``)
    takes it off."""
    kept = Counter(version_key(text).split())
    lost: dict[str, None] = {}
    for word in version_key(text, line_rules=False).split():
        if kept[word] > 0:
            kept[word] -= 1
        else:
            lost[word] = None
    return " ".join(lost)


def without_end_marks(text: str) -> str:
    """*text* without the marks at its end that :func:`dropped` lets pass:
    white space, dots and one comma, so that a reading of the rest drops
    nothing more than a loose ID drops. The prose forms of ``resolve`` use
    it (``MIT License.``); a ``;``, ``:`` or ``\u2026`` stays and is refused
    as ``MIT;`` is."""
    body = text.rstrip().removesuffix(",")
    end = len(body)
    while end and (body[end - 1].isspace() or body[end - 1] == "."):
        end -= 1
    return body[:end]


def code_points(chars: str) -> str:
    """*chars* as code points, space separated: ``U+003F U+0021``. Safe to
    show, whatever the characters are (a lone surrogate, a mark)."""
    return " ".join(f"U+{ord(char):04X}" for char in chars)

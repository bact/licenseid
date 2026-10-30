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

Marks at the ends are judged apart. At the start nothing is a separator: a
dash or dots (``-- MIT``, ``-MIT``, ``.GPL-3.0-only``, which is the end of
``AGPL-3.0-only``) are a list marker or a cut value. At the end one ``.`` or
``,`` passes (``MIT.``), one ``;`` or ``:`` is trimmed by the reader
(:func:`trim_end_mark`), and two or more marks, an ellipsis or a dash alone
(``MIT;;``, ``MIT...``, ``MIT -``) are dropped marks. A dash joined to the
end of a reading that no loose ID made (``MIT+-``, ``MIT License--``) is
one too (:func:`end_dashes`).

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
_END_MARKS: Final = ".,;:"
_ELLIPSIS: Final = "\u2026"


def _is_separator(char: str) -> bool:
    """Whether dropping *char* says nothing: white space, ``_``, ``.`` or a
    dash."""
    return char.isspace() or char in _ALLOWED or RE_DASHES.match(char) is not None


def dropped(text: str) -> str:
    """The characters of *text* a loose reading would drop that are not
    separators, each once, in the order they first appear; empty if there are
    none. One comma at the end (after white space) is allowed, a second is not.
    Marks at the ends are judged by :func:`lead_marks`, :func:`end_marks` and
    a dash or dots standing alone.
    """
    body = text.rstrip()
    seen: dict[str, None] = {}
    for char in body.removesuffix(","):
        if RE_QUOTES.match(char) or not (char.isalnum() or _is_separator(char)):
            seen[char] = None
    for char in lead_marks(body) + end_marks(body) + _dangling(body):
        seen[char] = None
    return "".join(seen)


def lead_marks(text: str) -> str:
    """The dots and dashes at the very start of *text* (``-MIT``,
    ``...GPL-3.0-only``): a list marker, or a cut value (``.GPL-3.0-only``
    is the end of ``AGPL-3.0-only``), never an ID spelt loosely."""
    stop = 0
    while stop < len(text) and (text[stop] == "." or RE_DASHES.match(text[stop])):
        stop += 1
    return text[:stop]


def end_marks(text: str) -> str:
    """The marks at the end of *text* when there are two or more (``MIT;;``,
    ``MIT.,``, ``MIT...``, ``MIT ; .``), white space between them left out;
    empty for none or one. One mark (``MIT.``) is judged by the rest of
    :func:`dropped`, and :func:`trim_end_mark` reads ``;`` and ``:``."""
    marks = []
    for char in reversed(text):
        if char in _END_MARKS or char == _ELLIPSIS:
            marks.append(char)
        elif not char.isspace():
            break
    return "".join(reversed(marks)) if len(marks) > 1 else ""


def end_dashes(text: str) -> str:
    """The dashes at the very end of *text*, white space after them left
    out, each once (``MIT+-`` and ``MIT License--`` give ``-``). A loose ID
    reads a dash there as a separator (``MIT-``); after a ``+``, an
    exception, a ``LicenseRef-*`` or a prose form no loose reading ran, so
    the dash is a mark that is dropped like any other."""
    body = text.rstrip()
    stop = len(body)
    while stop and RE_DASHES.match(body[stop - 1]):
        stop -= 1
    return "".join(dict.fromkeys(body[stop:]))


def trim_end_mark(text: str, marks: str = _END_MARKS) -> str | None:
    """*text* without its one *marks* mark at the end, white space around it
    left off too, or None. None when there is no such mark, when another
    mark, an ellipsis or a dash stands before it (``MIT;;``, ``MIT...``,
    ``MIT -;``), or when nothing else is left."""
    body = text.rstrip()
    if not body or body[-1] not in marks:
        return None
    rest = body[:-1].rstrip()
    if not rest or rest[-1] in _END_MARKS + _ELLIPSIS or RE_DASHES.match(rest[-1]):
        return None
    return rest


def _dangling(text: str) -> str:
    """The marks of the last white-space-separated token of *text* when it is
    nothing but dashes and dots and another token stands beside it (``MIT -``,
    ``MIT ...``); a lone dot is an end mark, not a dangling one. A first token
    of marks is a lead mark (:func:`lead_marks`)."""
    tokens = text.split()
    last = tokens[-1] if len(tokens) > 1 else ""
    return last if _only_marks(last) and last != "." else ""


def _only_marks(token: str) -> bool:
    """Whether *token* is nothing but dots and dashes."""
    return all(char == "." or RE_DASHES.match(char) for char in token)


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


def code_points(chars: str) -> str:
    """*chars* as code points, space separated: ``U+003F U+0021``. Safe to
    show, whatever the characters are (a lone surrogate, a mark)."""
    return " ".join(f"U+{ord(char):04X}" for char in chars)

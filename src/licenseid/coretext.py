# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The core text of a licence: its template without the optional parts.

A licence text of the List holds parts that a copy may leave out (the
appendix "How to apply the licence" of Apache-2.0, the whole GPL-3.0 inside
the LGPL-3.0, a title, a copyright line). A text without them is the same
licence, but its distance to the whole text is large, so a long input that
leaves them out is scored against the core as well (``licenseid.similarity``).

Standard library only.

The template format is the one of the SPDX matching guidelines, annex B.3:
<https://spdx.github.io/spdx-spec/v3.0/annexes/license-matching-guidelines-and-templates/>

* ``<<beginOptional>>`` and ``<<endOptional>>`` enclose text that may be
  omitted (B.3.4 "Optional text"). They nest.
* ``<<var;name="..";original="..";match="..">>`` marks text that may vary
  (B.3.3 "Replaceable text"): ``original`` is the wording of the List's text,
  ``match`` a regular expression of the wordings that match.

The scanner is one pass over the template with ``str.find`` and a depth
counter, never a regular expression over the whole text: the time is linear
whatever the input, and a ``<<`` that begins no mark costs one step.
"""

from typing import Final, Literal

_BEGIN: Final = "<<beginOptional>>"
_END: Final = "<<endOptional>>"
_VAR: Final = "<<var;"
# The end of a var. Its attributes are quoted but not escaped: Python-2.0.1
# has ``original="this software ("Python")"``, so a quote is no end of
# attribute; the first quote-and-``>>`` after the start is the end of the var.
_VAR_END: Final = '">>'
_ORIGINAL: Final = 'original="'
# Between ``original`` and ``match``; the last one in the var, as ``match``
# is a pattern that may hold a quote.
_ORIGINAL_END: Final = '";match="'

# What the scanner found at a ``<<``: the kind, where the next scan starts
# and the text the mark stands for.
_Token = tuple[Literal["begin", "end", "var", "text", "bad"], int, str]


def core_text(template: str) -> str | None:
    """The text of *template* with every optional part dropped and every
    variable part at its ``original`` wording, or ``None`` when the template
    is malformed (an optional part opened and never closed, closed and never
    opened, or a variable part without an ``original`` or an end).

    The order of the steps matters:

    1. An optional part is dropped whole, nested ones with it (B.3.4): a
       ``<<beginOptional>>`` inside an optional part opens a level of its own,
       and the text comes back only when the outermost one closes. A part
       that is optional only by its position (a title, a copyright line) is
       what the text of a bare copy lacks.
    2. A variable part outside every optional part is kept, as its
       ``original`` (B.3.3). Dropping it instead would cut the text (HPND, a
       licence made of its variable parts, fell to 39 words), and the
       ``original`` is what the List's text holds there. An ``original``
       that is a placeholder (MIT's ``<year> <copyright holders>``) is kept
       too: the List's whole text holds it as well, so the core and the
       text read alike there; dropped, it would make a core of a text that
       differs from it by nothing but a copyright line.
    3. Any other ``<<`` is text. The templates of the List have a ``<`` right
       before a mark (``<<<endOptional>>``, a literal angle bracket); the scan
       moves one character at a time, so the mark that starts one character
       later is still found.
    4. A var, and the place of a dropped optional part, stand apart from the
       text beside them: white space is insignificant (B.2), and a template
       may have none there. HPND has
       ``modify<<beginOptional>>,<<endOptional>>and``: without its comma,
       "modify and", not "modifyand".

    The result is not normalised: the caller does that, with the same
    function as for the whole text, so both sides of a comparison read
    alike (the guidelines' text transformations, B.2).
    """
    parts: list[str] = []
    depth = 0
    pos = 0
    while (mark := template.find("<<", pos)) >= 0:
        if depth == 0:
            parts.append(template[pos:mark])
        kind, pos, text = _token(template, mark)
        if kind == "bad" or (kind == "end" and depth == 0):
            return None
        if kind == "begin":
            depth += 1
        elif kind == "end":
            depth -= 1
        if depth == 0:  # at a var, or where an optional part closes
            # A mark is a word boundary (step 4); a "<" that is text is not.
            parts.append(text if kind == "text" else f" {text} ")
    parts.append(template[pos:])  # at depth 0, else there is no core
    return None if depth else "".join(parts)


def _token(template: str, mark: int) -> _Token:
    """What *template* has at *mark*, where a ``<<`` is."""
    if template.startswith(_BEGIN, mark):
        return "begin", mark + len(_BEGIN), ""
    if template.startswith(_END, mark):
        return "end", mark + len(_END), ""
    if template.startswith(_VAR, mark):
        end = template.find(_VAR_END, mark)
        original = _original(template[mark + len(_VAR) : end]) if end >= 0 else None
        if original is None:
            return "bad", mark, ""
        return "var", end + len(_VAR_END), original
    # Not a mark: the first ``<`` is text, and a mark may start at the next
    # character.
    return "text", mark + 1, "<"


def _original(body: str) -> str | None:
    """The ``original`` of a var whose text between ``<<var;`` and the final
    quote is *body*, or ``None`` when it has none."""
    start = body.find(_ORIGINAL)
    stop = body.rfind(_ORIGINAL_END)
    if start < 0 or stop < start + len(_ORIGINAL):
        return None
    return body[start + len(_ORIGINAL) : stop]

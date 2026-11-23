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
one too (:func:`joined_marks`).

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
above are spelling and drop nothing. Standard library, ``licenseid.exprtokens``,
``licenseid.normalize`` and ``licenseid.versionkey`` only.
"""

from collections import Counter
from typing import Final

from licenseid.exprtokens import (
    WHITE_SPACE,
    cut_inside_word,
    is_addition_ref,
    is_license_ref,
    is_white_space,
    ref_end,
)
from licenseid.normalize import QUOTE_KIND, RE_DASHES, RE_QUOTES
from licenseid.versionkey import version_key

_ALLOWED: Final = frozenset("_.")
_END_MARKS: Final = ".,;:"
_ELLIPSIS: Final = "\u2026"
# What a mark at the end may stand inside of, which stays: white space,
# closing brackets and quote marks (``"(MIT;)".``).
_AROUND: Final = ")]}"
# Where the marks at the end stop: a word, a "+" or an opening bracket.
_BEFORE_MARKS: Final = "+([{"
# What may follow the dashes that cut a tag's expression: an end mark, a "+", a
# quote mark or a closing bracket, never the start of a comment closer.
_AFTER_CUT: Final = ".,;:!?+\"')"
# The first character of a comment closer (``-->``, ``-}``, ``--]]``, ``-#}``, ``*/``).
_CLOSER_STARTS: Final = ">}]/*#"
# The closers of two characters whose first is no closer start (``?>`` of PHP,
# ``%>`` of ERB).
_CLOSER_PAIRS: Final = ("?>", "%>")
# What a mark round a whole name never is: a bracket, a "+" (the plus reader's)
# and a quote mark are read by their own steps. The corner brackets quote too
# (``licenseid.quotes.CORNER_PAIRS``, which imports this module).
_KEPT_AT_EDGE: Final = "()[]{}+「」『』"


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


def _is_edge_mark(char: str, *, trailing: bool) -> bool:
    """Whether *char* is a mark round a name: not a letter, a digit, a bracket,
    a quote mark (``'`` and the grave accent too) or a "+". At the end a dash,
    ``_`` or ``.`` is not one: it is :func:`trailing_joiners`' or the reader's
    of one end mark."""
    if char.isalnum() or char in _KEPT_AT_EDGE or char in QUOTE_KIND:
        return False
    return not trailing or char.isspace() or not _is_separator(char)


def edge_marks(text: str) -> tuple[str, str] | None:
    """*text* without the marks at both ends, and those marks (white space
    left out): ``*Apache License 2.0*`` gives ``("Apache License 2.0", "**")``,
    ``# Apache License 2.0`` gives ``#``. None where the cut is no reason to
    refuse: nothing, white space alone, or one ``.``, ``,``, ``;`` or ``:`` at
    the end with none at the start (:func:`trim_end_mark` reads it).

    At the start every mark counts, dashes and dots too (:func:`lead_marks`).
    At the end a dash, ``_``, ``.``, a "+", a bracket and a quote mark stay,
    each with a reader of its own, and so does a quote or a bracket at the
    start. One pass from each end, linear in *text*."""
    start, stop = 0, len(text)
    while start < stop and _is_edge_mark(text[start], trailing=False):
        start += 1
    while stop > start and _is_edge_mark(text[stop - 1], trailing=True):
        stop -= 1
    lead = "".join(text[:start].split())
    trail = "".join(text[stop:].split())
    if not lead and (not trail or (len(trail) == 1 and trail in _END_MARKS)):
        return None
    return text[start:stop].strip(), lead + trail


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


def joined_marks(text: str) -> str:
    """The dashes and underscores of *text*, each once, in order
    (``MIT+-`` and ``MIT License--`` give ``-``). A loose ID reads one
    joined to its end as a separator (``MIT-``, ``MIT_``); after a ``+``,
    an exception, a ``LicenseRef-*`` or a prose form no loose reading ran,
    so the mark is dropped like any other."""
    return "".join(
        dict.fromkeys(c for c in text if c == "_" or RE_DASHES.match(c) is not None)
    )


def trailing_joiners(text: str, *, least: int = 1) -> str:
    """The dashes and underscores joined to the end of *text*, each once, in
    order (``MIT-``, ``MIT_``, ``GPL-2.0-``, ``MIT--``, ``MIT-.``), or empty;
    empty too for a run of fewer than *least* (``least=2``: ``GPL-2.0-`` gives
    none, ``GPL-2.0--`` and ``GPL-2.0-_`` give their marks; the head before a
    word grant keeps one, ``GPL-2.0- or later``). One ``.`` or ``,`` after them is an
    ending and left out. They must follow
    a letter or digit: a run after a dot, a space or a mark has another
    reader (``MIT -``, :func:`_dangling`). A loose ID drops them as it drops
    any joiner, but a cut value (``MIT-`` is the start of ``MIT-0``) is no
    value written whole: a ``LicenseRef-*`` or ``AdditionRef-*`` takes them
    as its own characters and is left alone. Only the end of the text is
    read: one pass back from it."""
    body = text.rstrip(WHITE_SPACE)
    if body[-1:] in (".", ","):
        body = body[:-1]
    stop = len(body)
    while stop and (body[stop - 1] == "_" or RE_DASHES.match(body[stop - 1])):
        stop -= 1
    if len(body) - stop < least or not stop or not body[stop - 1].isalnum():
        return ""
    if ends_in_ref(body):
        return ""
    return "".join(dict.fromkeys(body[stop:]))


# What may stand glued to the end of a grant, beside one ending: a closing
# bracket or a quote mark, which ``resolve()`` reads (``or later)``, ``"``).
_GLUED_PASS: Final = frozenset(")]")


def glued_marks(text: str, end: int) -> str:
    """The marks glued to *end* of *text*, the end of a grant, that
    ``resolve()`` refuses (``GPL-2.0 or later-``, ``?``, ``>``, ``*/``, two or
    more end marks), each once, in order; empty if none: what :func:`dropped`
    names in the run, and the dashes and underscores it allows elsewhere (here
    they join the grant to what follows). One ``.``, ``,``, ``;`` or ``:``, a
    closing bracket and a quote mark pass (``or later.)``). The run is what
    touches *end* up to white space: one pass, linear."""
    stop = end
    while stop < len(text) and not text[stop].isspace():
        stop += 1
    run = text[end:stop]
    joined = (c for c in run if c == "_" or RE_DASHES.match(c))
    judged = trim_end_mark(f"x{run}") or f"x{run}"  # one ";" or ":" is an ending
    lost = (c for c in dropped(judged) if c not in _GLUED_PASS and not _quote(c))
    return "".join(dict.fromkeys((*joined, *lost)))


# What closes a grant's own bracket or a quote round the value: it ends a run
# of end marks, so one mark either side of it (``or later.).``) is two endings.
_CLOSERS: Final = ")]" + "".join(QUOTE_KIND)
# What may stand after the "or later" grant that ends a value.
_AFTER_GRANT: Final = WHITE_SPACE + _END_MARKS + _CLOSERS


def grant_end_marks(text: str, end: int | None = None) -> str:
    """The end marks a reading of *text*, a licence and the "or later" grant
    that ends it, drops at its end, each once; empty if none. One ``.``,
    ``,``, ``;`` or ``:`` is an ending (``or later.``, ``or later ;``); a run
    of them says something (``or later..``, ``or later.;``, ``or later. .``).
    A closing bracket or quote mark ends a run and is no mark itself, as in
    :func:`glued_marks` (``or later.)``, ``or later.).``).

    *end* is where the grant ends, if *text* may go on after it: only marks
    after it are judged, and prose that follows (``or later, see COPYING..``)
    is not this reader's. Without *end* the grant ends *text*'s licence, so
    the marks that end *text* are judged. Linear."""
    if end is None:
        end = len(text)
        while end and text[end - 1] in _AFTER_GRANT:
            end -= 1
    elif text[end:].strip(_AFTER_GRANT):
        return ""
    lost = ""
    run = ""
    for char in f"{text[end:]})":  # the extra closer ends the last run
        if char in _END_MARKS:
            run += char
        elif char in _CLOSERS and run:
            judged = f"x{run}"
            lost += dropped(trim_end_mark(judged) or judged)
            run = ""
    return "".join(dict.fromkeys(lost))


def glued_tag_marks(text: str, end: int) -> str:
    """:func:`glued_marks` for a tag value *text*, which knows no comment
    closers: a run that reaches one is left to the tag reader, as
    :func:`cut_by_joiners` leaves it. The closer may follow end marks and
    dashes (``or later*/``, ``.*/``, ``.-->``, ``#}``, ``}``) or be ``?>`` or
    ``%>`` (a bare ``?`` or ``%`` is a mark). A closing bracket before it
    passes (``(or later)*/``, ``(or later)?`` is a mark). End marks alone
    (``...``, ``.,``) end the run too: ``resolve()`` reads them."""
    stop = end
    while stop < len(text) and text[stop] in _END_MARKS + ")]":
        stop += 1
    marks = stop
    while stop < len(text) and (text[stop] == "_" or RE_DASHES.match(text[stop])):
        stop += 1
    after = text[stop : stop + 2]
    if after[:1] in tuple(_CLOSER_STARTS) or after in _CLOSER_PAIRS:
        return ""
    if marks == stop and (stop == len(text) or is_white_space(text[stop])):
        return ""
    return glued_marks(text, end)


def _quote(char: str) -> bool:
    """Whether *char* is a quote mark ``resolve()`` takes off a value."""
    return RE_QUOTES.match(char) is not None


def cut_by_joiners(text: str, end: int) -> bool:
    """Whether the expression of a tag value *text* that ends at *end* is cut
    by dashes or underscores: a run of them touches it (``MIT-``, ``MIT_``,
    ``GPL-2.0-``, ``MIT- OR ISC``) and the value ends there, or white space or
    a character of :data:`_AFTER_CUT` follows the run. The same value as
    an argument is refused (:func:`trailing_joiners`). Another character
    after the run may start a comment closer (``MIT-->``, ``MIT-*/``) and is
    left to the tag reader, which knows no closers: the run is not judged.
    Where white space separates the dash from the ID (``MIT - some text``)
    the dash is the author's. A ``LicenseRef-*`` keeps its own dashes: the
    reader takes them into its token (:func:`licenseid.exprtokens.ref_end`)."""
    stop = end
    while stop < len(text) and (text[stop] == "_" or RE_DASHES.match(text[stop])):
        stop += 1
    if stop == end or not end:
        return False
    return stop == len(text) or is_white_space(text[stop]) or text[stop] in _AFTER_CUT


def cut_reference(text: str, end: int) -> bool:
    """Whether the expression of a tag value *text* that ends at *end* has a
    last operand that is a ``LicenseRef-*`` (or ``AdditionRef-*``) with
    dashes or underscores directly before a comment closer
    (``MIT OR LicenseRef-a-->``, ``-}``, ``--]]``, ``-#}``, ``-*/``). The
    reference may own those dashes or the closer may: a tag reader that
    knows no closers cannot tell, and either reading is another reference
    than the author's, so the value is refused, as the same value is as an
    argument. A lone reference (``LicenseRef-a-->``) is refused too. A run apart
    by white space (``LicenseRef-a- -->``) is the author's."""
    body = text[:end]
    word = _last_word(body)
    if not (is_license_ref(word) or is_addition_ref(word)):
        return False
    stop = end
    while stop < len(text) and (text[stop] == "_" or RE_DASHES.match(text[stop])):
        stop += 1
    run = len(word) - len(word.rstrip("-")) + stop - end
    return bool(run) and stop < len(text) and text[stop] in _CLOSER_STARTS


def cut_off(text: str, end: int) -> bool:
    """Whether the expression of a tag value *text* that ends at *end* is cut:
    inside a word (``LicenseRef-café``, :func:`licenseid.exprtokens.cut_inside_word`),
    by dashes or underscores (:func:`cut_by_joiners`) or by a closer beside a
    reference's dashes (:func:`cut_reference`)."""
    return (
        cut_inside_word(text, end)
        or cut_by_joiners(text, end)
        or cut_reference(text, end)
    )


def ends_in_ref(text: str) -> bool:
    """Whether the last word of *text* is a ``LicenseRef-*`` or an
    ``AdditionRef-*``, whose characters include ``.``, ``-`` and ``_``
    (``LicenseRef-a.``, ``AdditionRef-x-``): those are no marks there.
    Words are split at :data:`licenseid.exprtokens.WHITE_SPACE`: a
    reader before ``resolve()``'s gate calls this, and an information separator
    (U+001C) is no white space to it."""
    word = _last_word(text.rstrip(WHITE_SPACE))
    return is_license_ref(word) or is_addition_ref(word)


def _last_word(text: str) -> str:
    """The run of characters of *text* after its last white space."""
    start = len(text)
    while start and not is_white_space(text[start - 1]):
        start -= 1
    return text[start:]


def ends_in_mark(text: str) -> bool:
    """Whether *text* ends in an end mark or an ellipsis, white space and
    closing brackets after it left out (``MIT;``, ``(MIT.)``, ``[MIT,]``); a
    dot that ends a ``LicenseRef-*`` is a character of the ID, not a mark.
    The question :func:`trim_end_mark` answers for one mark, asked for any."""
    stop = len(text)
    while stop and (is_white_space(text[stop - 1]) or text[stop - 1] in ")]}"):
        stop -= 1
    body = text[:stop]
    if not body or body[-1] not in _END_MARKS + _ELLIPSIS:
        return False
    return not (body[-1] == "." and ends_in_ref(body))


def trim_end_mark(text: str, marks: str = _END_MARKS) -> str | None:
    """*text* without its one *marks* mark at the end, white space around it
    left off too, or None. None when there is no such mark, when another
    mark, an ellipsis or a dash stands before it (``MIT;;``, ``MIT...``,
    ``MIT -;``), or when nothing else is left. A ``.``, ``-`` or ``_`` that
    ends a ``LicenseRef-*`` or ``AdditionRef-*`` is a character of the ID
    (``LicenseRef-a.;`` is ``LicenseRef-a.``). White space is
    :data:`licenseid.exprtokens.WHITE_SPACE`: ``resolve()`` calls this before
    its gate, which must still see a U+001C before the mark."""
    body = text.rstrip(WHITE_SPACE)
    if not body or body[-1] not in marks:
        return None
    rest = body[:-1].rstrip(WHITE_SPACE)
    if not rest:
        return None
    if rest[-1] in _END_MARKS + _ELLIPSIS or RE_DASHES.match(rest[-1]):
        return rest if ends_in_ref(rest) else None  # ``LicenseRef-a.;``
    return rest


def marks_at_end(text: str) -> tuple[str, str] | None:
    """*text* without the marks at its end, and those marks in the order
    they stand, or None for none. The marks may stand inside the closing
    brackets and quote marks of the value, which stay (``"(MIT;)".`` gives
    ``"(MIT)"`` and ``;.``); they stop at a letter, a digit, a ``+`` or an
    opening bracket. A ``.`` or ``-`` that ends a ``LicenseRef-*`` or an
    ``AdditionRef-*`` is a character of the ID, not a mark
    (``"LicenseRef-a.;".`` gives ``"LicenseRef-a."``). One pass back from
    the end, linear in *text*: each word is read for a reference once."""
    kept: list[str] = []
    marks: list[str] = []
    stop = len(text)
    word = (stop + 1, stop)  # the word being read, and where its ID may end
    while stop:
        char = text[stop - 1]
        if char.isalnum() or char in _BEFORE_MARKS:
            break
        if char in ".-":
            if stop <= word[0]:  # a new word: where its reference ends
                word = _ref_word(text, stop)
            if stop <= word[1]:
                break
        if char.isspace() or char in _AROUND or char in QUOTE_KIND:
            kept.append(char)
        else:
            marks.append(char)
        stop -= 1
    if not marks:
        return None
    return text[:stop] + "".join(reversed(kept)), "".join(reversed(marks))


def _ref_word(text: str, stop: int) -> tuple[int, int]:
    """Where the word of *text* that holds code point ``stop - 1`` starts,
    and up to where a ``text[:end]`` ends in a reference that the word holds
    after the brackets and quote marks that open it (``(LicenseRef-a.-;``):
    a reference takes ``.`` and ``-`` at its end. The second is below the
    first when the word holds none."""
    start = stop
    while start and not text[start - 1].isspace():
        start -= 1
    core = start
    while core < stop and (text[core] in "([{" or text[core] in QUOTE_KIND):
        core += 1
    return start, ref_end(text, core)


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


def without_name_tail(value: str) -> str:
    """*value* without its comment closer or full stop, for the name lookup.

    No license name ends in anything but a word character or ")", and a
    "+" is part of the expression, not punctuation. A backward scan, not
    the regex "[^\\w)+]+$": that retries a long run of spaces or dashes
    from every start and is quadratic (6 s at 40,000 characters).
    """
    end = len(value)
    while end and not (value[end - 1].isalnum() or value[end - 1] in "_)+"):
        end -= 1
    return value[:end]

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whose grant an "or later" phrase is: the one reader of its subject.

``classify.OR_LATER_PHRASE`` finds a phrase; this module reads what stands
right before it. A grant qualifies the licence it names: ``GPL-2.0 or
later`` grants GPL-2.0 later versions, ``Requires Python 3.8 or later``
grants nothing of a licence. The subject is a version number and the word
before it (a licence's name, ``version``, ``v``), or ``the License``; a
number alone, or after a word that names no thing (``in 3 or later``), is
no subject. "N only" (``version 2 only``) has the same subject.

A :class:`Grant` keeps the version and the family (the letters of the
licence: ``gpl``, ``lgpl``, or a tool's name such as ``python``) it names;
:func:`grants_licence` asks whether it is a given licence's. A tool's grant
is kept, so a caller sees it, and grants no licence of the List.

Standard library and ``licenseid.classify`` only: no database. Every pass is
one scan of the phrases, each read in a bounded stretch before it
(:data:`SUBJECT_REACH`), so a long line costs time in its phrases, not
their square.
"""

import bisect
import re
from collections.abc import Callable, Sequence
from typing import Final, NamedTuple

from licenseid.classify import (
    OR_LATER_PHRASE,
    RE_OR_LATER_SHORTHAND,
    is_negated,
    same_version,
)

#: How many characters before a phrase are read for its subject, and how many
#: words of them: "version 2 of the GNU General Public License as published
#: by the Free Software Foundation, or (at your option) any later version".
SUBJECT_REACH: Final = 120
_MAX_TOKENS: Final = 24

#: A licence ID or a tool as a function of a licence ID: whether the input
#: grants it ("GPL-2.0-or-later" to True).
GrantSignal = Callable[[str], bool]


class Grant(NamedTuple):
    """A grant read in a text."""

    start: int  # where its subject starts
    end: int  # where the phrase ends
    version: str | None  # the number it qualifies ("2", "2.1"); None: "the License"
    family: str | None  # the letters of the licence it names ("lgpl"), else None


class Signals(NamedTuple):
    """What an input says of the grants of its licences, for
    ``licenseid.variants``: asked per licence, read when first asked."""

    later: GrantSignal  # grants later versions of the licence
    only: GrantSignal = lambda _license_id: False  # states "only" of it
    leave: Callable[[], bool] = lambda: False  # leave an -or-later answer alone


def constant(flag: bool) -> GrantSignal:
    """A signal that gives *flag* for every licence (a pure licence text grants
    nothing: its "How to Apply" appendix holds the phrase)."""
    return lambda _license_id: flag


#: The signal of an input that grants nothing.
NO_GRANT: Final[GrantSignal] = constant(False)


def lazy_signal(found: Callable[[], Sequence[Grant]]) -> GrantSignal:
    """The signal of the grants *found* reads, read at the first question and
    once: most inputs are never asked. A text repeats few kinds of grant
    ("GPLv2+" a hundred thousand times): each kind is asked once."""
    kinds: list[set[tuple[str | None, str | None]]] = []
    answers: dict[str, bool] = {}

    def signal(license_id: str) -> bool:
        if not kinds:
            kinds.append({(g.version, g.family) for g in found()})
        if license_id not in answers:
            answers[license_id] = any(
                grants_licence(Grant(0, 0, version, family), license_id)
                for version, family in kinds[0]
            )
        return answers[license_id]

    return signal


# A later-version phrase with a word more than OR_LATER_PHRASE reads ("or any
# version later"), or one it reads that stands without a subject: it grants
# "something" that :func:`grants` cannot give a licence.
_LOOSE_PHRASE: Final = re.compile(
    r"\bany\s+(?:later|newer)\s+version\b|\bany\s+version\s+(?:later|newer)\b"
    r"|\bor\s+(?:later|newer)\s+version\b",
    re.IGNORECASE | re.ASCII,
)


def has_unowned_phrase(text: str) -> bool:
    """Whether *text* holds a later-version phrase (``any later version``, ``or
    any version later``) that no subject of :func:`grants` owns: the licence's
    own grant may be one the subject rule cannot read. A phrase that starts
    inside a grant of a tool (``Python 3.8 or any later version``) is that tool's."""
    spans = sorted((g.start, g.end) for g in grants(text))
    starts = [start for start, _ in spans]
    reach: list[int] = []  # the furthest end of the spans up to each one
    for _, end in spans:
        reach.append(max(end, reach[-1]) if reach else end)
    for match in _LOOSE_PHRASE.finditer(text):
        before = bisect.bisect_right(starts, match.start()) - 1
        owned = before >= 0 and match.start() < reach[before]
        if not owned and not is_negated(
            text[max(0, match.start() - 5) : match.start()]
        ):
            return True
    return False


# A token: an escaped line break or tab (JSON writes a notice so), a number, a
# run of ASCII letters, or one other character.
_TOKEN: Final = re.compile(r"\\[nrt]|[0-9]+(?:\.[0-9]+)*|[A-Za-z]+|\S")
# What may stand between words of a subject: marks of a wrapped notice, a comma,
# a bracket, a dash. A full stop, "+" or "!" is a barrier: the sentence or the
# word (``g++``) ends there.
# What a line of a wrapped notice starts with: a comment leader of autoconf,
# Texinfo, man pages, Fortran, batch files and mail quotes.
_LEADER: Final = re.compile(
    r"^[ \t]*(?:dnl|rem|@c|\.\\\"|c|//!|[#%!>;*/-]+)(?=[ \t])",
    re.IGNORECASE | re.MULTILINE,
)
_GAP: Final = frozenset([*",;()[]*/#-_:\"'", "\\n", "\\r", "\\t"])
_MARKS: Final = frozenset({"v", "ver", "version"})
_LICENCE_WORDS: Final = frozenset({"license", "licence"})
# Words that name no licence and no tool: before a number they are no subject,
# before "version" they leave the family open ("either version 2").
_STOP: Final = frozenset(
    [
        "the",
        "this",
        "that",
        "any",
        "of",
        "under",
        "and",
        "or",
        "at",
        "a",
        "an",
        "to",
        "in",
        "with",
        "by",
        "as",
        "either",
        "same",
        "your",
        "option",
        "terms",
        "published",
        "gnu",
    ]
)
_FAMILIES: Final = frozenset({"gpl", "lgpl", "agpl", "gfdl", "fdl"})
# The last words of a GNU licence's name, where a name is cut short ("gnu public
# v2.0 or later"): they stand for the name that ends in "License".
_FRAGMENTS: Final = frozenset(
    {"public", "general", "documentation", "lesser", "library", "affero"}
)
# The words of "or (at your option) any later version" before "any", where the
# phrase starts there (the "or" was not read: ``or\\n(at ...``).
_PREAMBLE: Final = frozenset({"or", "and", "at", "your", "option", "discretion"})
_NAME_WORDS: Final = 4
# How far back a WITH may stand from the end of its exception's name.
_EXCEPTION_WORDS: Final = 8
_ALIASES: Final = {"fdl": "gfdl"}
_MODIFIERS: Final = {"lesser": "lgpl", "library": "lgpl", "affero": "agpl"}

_Token = tuple[int, str]

# "N only", the number named so that its end is known.
_ONLY_AFTER_VERSION: Final = re.compile(
    r"(?P<number>\d{1,6}(?:\.\d{1,6}){0,3})\)?\s+only\b", re.IGNORECASE | re.ASCII
)


def grants(text: str) -> list[Grant]:
    """Every "or later" grant of *text* with a subject: a version number and
    the licence it names, or ``the License``. A phrase after a number alone, a
    full stop or nothing is none."""
    found: list[Grant] = []
    for match in OR_LATER_PHRASE.finditer(text):
        # A phrase that starts at a digit starts at the last digit of its number.
        at = match.start() if text[match.start()] in "oOaA" else match.start() + 1
        grant = _subject(_tokens(text, at), match.end())
        if grant is not None:
            found.append(grant)
    found.extend(
        Grant(m.start(), m.end(), m.group("version"), m.group("family").lower())
        for m in RE_OR_LATER_SHORTHAND.finditer(text)
    )
    return found


def onlys(text: str) -> list[Grant]:
    """Every "N only" of *text* (``GPL-2.0 only``, ``version 2 only``) with the
    subject of its number; a number alone is none."""
    found: list[Grant] = []
    for match in _ONLY_AFTER_VERSION.finditer(text):
        tokens = _tokens(text, match.end("number"))
        if tokens and _is_number(tokens, len(tokens) - 1):
            grant = _numbered(tokens, len(tokens) - 1, match.end())
            if grant is not None:
                found.append(grant)
    return found


_ID: Final = re.compile(r"([A-Za-z]+)[-_ ]?v?(\d+(?:\.\d+)*)")


def grants_licence(grant: Grant, license_id: str) -> bool:
    """Whether *grant* is for *license_id*: it names no family, or the ID's
    letters (``gpl`` for ``GPL-2.0-only``), and no version, or the ID's own
    (``2`` is ``2.0``, and names the 2.x series: ``2.1``). An exception
    (``WITH ...``) is no part of it."""
    head = re.split(r"\s+WITH\s+", license_id, maxsplit=1, flags=re.IGNORECASE)[0]
    parts = _ID.match(head)
    letters, own = (parts.group(1).lower(), parts.group(2)) if parts else ("", None)
    if grant.family is not None and grant.family != letters:
        return False
    if grant.version is None:
        return True
    if own is None:
        return False
    # "version 2" is any 2.x; "version 2.1" is that one.
    series = ".".join(own.split(".")[: len(grant.version.split("."))])
    return same_version(grant.version, series)


def _tokens(text: str, end: int) -> list[_Token]:
    """The last tokens of the stretch of *text* before *end*, with their offsets,
    the comment leaders of its lines (``dnl``, ``%``, ``@c``) left out."""
    begin = max(0, end - SUBJECT_REACH)
    leaders = [m.span() for m in _LEADER.finditer(text, begin, end)]
    found = [
        (m.start(), m.group())
        for m in _TOKEN.finditer(text, begin, end)
        if not any(a <= m.start() < b for a, b in leaders)
    ]
    return found[-_MAX_TOKENS:]


def _skip(tokens: list[_Token], i: int) -> int:
    """The index of the last token at or before *i* that is no gap."""
    while i >= 0 and tokens[i][1] in _GAP:
        i -= 1
    return i


def _is_word(tokens: list[_Token], i: int) -> bool:
    return i >= 0 and tokens[i][1].isalpha()


def _is_number(tokens: list[_Token], i: int) -> bool:
    return i >= 0 and tokens[i][1][0] in "0123456789"


def _family_word(word: str, tokens: list[_Token], i: int) -> str:
    """The family a word names at *i*: ``GPL`` after "Lesser" or "Library" is
    ``lgpl``, after "Affero" ``agpl``; ``FDL`` is ``gfdl``."""
    if word == "gpl":
        before = _skip(tokens, i - 1)
        if _is_word(tokens, before):
            return _MODIFIERS.get(tokens[before][1].lower(), "gpl")
    return _ALIASES.get(word, word)


def _name_words(tokens: list[_Token], i: int) -> tuple[list[str], int]:
    """The words of a licence's name that end at the token *i*, nearest first
    ("GNU" left out), and the index before them."""
    words: list[str] = []
    while (
        _is_word(tokens, i)
        and len(words) < _NAME_WORDS
        and tokens[i][1].lower() not in _STOP - {"gnu"}
    ):
        words.append(tokens[i][1].lower())
        i = _skip(tokens, i - 1)
    return [w for w in words if w != "gnu"], i


def _name_family(words: list[str]) -> str | None:
    """The family of a licence named by *words* (nearest first): "General
    Public" is ``gpl`` (``lgpl`` with "Lesser" or "Library", ``agpl`` with
    "Affero"), "Documentation" ``gfdl``, "<Name> Public" or any other word that
    word, "the" or "GNU" none."""
    modifier = next((_MODIFIERS[w] for w in words if w in _MODIFIERS), None)
    if "documentation" in words:
        return "gfdl"
    if modifier or "general" in words:
        return modifier or "gpl"
    if "public" in words:
        after = words.index("public") + 1
        return words[after] if after < len(words) else None
    return words[0] if words else None


def _licence_name(tokens: list[_Token], i: int) -> tuple[str | None, int]:
    """The family named by the words before the ``License`` at *i*, and the
    index before them."""
    words, before = _name_words(tokens, _skip(tokens, i - 1))
    return _name_family(words), before


def _name_before(tokens: list[_Token], i: int) -> str | None:
    """The family of the word at *i* that names what a version belongs to: a
    name that stops short of "License" ("gnu public v2.0") too."""
    word = tokens[i][1].lower()
    if word in _LICENCE_WORDS:
        return _licence_name(tokens, i)[0]
    if word in _FRAGMENTS:
        return _name_family(_name_words(tokens, i)[0])
    if word in _STOP:
        return None
    return _family_word(word, tokens, i)


def _owner(tokens: list[_Token], j: int) -> tuple[str | None, bool]:
    """Whose version the number right after the token *j* is: its family (None:
    any licence's) and whether it has an owner at all. A number is a licence
    or tool's with a name before it (``GPL-2.0``, ``Python 3``), or a mark
    (``version 2``, ``v2``), which leaves the family to the word before it."""
    j = _skip(tokens, j)
    if j > 0 and tokens[j][1] == "." and tokens[j - 1][1].lower() in ("ver", "v"):
        j = _skip(tokens, j - 1)  # "ver. 2"
    if not _is_word(tokens, j):
        return None, False
    word = tokens[j][1].lower()
    if word in _STOP:
        return None, False
    if word in _MARKS:
        before = _past_foundation(tokens, _skip(tokens, j - 1))
        if not _is_word(tokens, before):
            return None, True
        return _name_before(tokens, before), True
    if len(word) > 1 and word.endswith("v") and word[:-1] in _FAMILIES:
        return _family_word(word[:-1], tokens, j), True  # GPLv2
    return _name_before(tokens, j), True


def _numbered(tokens: list[_Token], i: int, end: int) -> Grant | None:
    """The grant of the number at *i*, if it has an owner."""
    first = i
    while first and _is_number(tokens, first - 1):  # "v2 0": a version spelt apart
        first -= 1
    before = _skip(tokens, first - 1)
    if before >= 0 and tokens[before][1].lower() == "exception":
        return _of_excepted(tokens, before, end)
    family, owned = _owner(tokens, first - 1)
    if not owned:
        return None
    version = ".".join(tokens[k][1] for k in range(first, i + 1))
    return Grant(tokens[first][0], end, version, family)


def _of_excepted(tokens: list[_Token], i: int, end: int) -> Grant | None:
    """The grant after an exception ("GPL-2.0 WITH Classpath-exception-2.0 or
    later") is the licence's before its "WITH"."""
    for k in range(i, max(i - _EXCEPTION_WORDS, -1), -1):
        if tokens[k][1].lower() == "with":
            before = _skip(tokens, k - 1)
            return (
                _numbered(tokens, before, end) if _is_number(tokens, before) else None
            )
    return None


def _past_foundation(tokens: list[_Token], i: int) -> int:
    """*i* before "as published by the Free Software Foundation" if it ends there."""
    if (
        i >= 2
        and tokens[i][1].lower() == "foundation"
        and tokens[i - 1][1].lower() == "software"
        and tokens[i - 2][1].lower() == "free"
    ):
        i = _skip(tokens, i - 3)
        while i >= 0 and tokens[i][1].lower() in ("the", "by", "published", "as"):
            i = _skip(tokens, i - 1)
    return i


def _subject(tokens: list[_Token], end: int) -> Grant | None:
    """The grant of a phrase that follows *tokens* and ends at *end*."""
    i = _skip(tokens, len(tokens) - 1)
    while i >= 0 and tokens[i][1].lower() in _PREAMBLE:  # "or (at your option)"
        i = _skip(tokens, i - 1)
    if i < 0:
        return None
    if _is_number(tokens, i):
        return _numbered(tokens, i, end)
    i = _past_foundation(tokens, i)
    word = tokens[i][1].lower() if _is_word(tokens, i) else ""
    if word in _LICENCE_WORDS:
        family, before = _licence_name(tokens, i)
    elif word in _FAMILIES:
        family, before = _family_word(word, tokens, i), i - 1
    else:
        return None
    return _of_number(tokens, (i, before), end, family)


def _of_number(
    tokens: list[_Token], licence: tuple[int, int], end: int, family: str | None
) -> Grant:
    """The grant of the licence named at *licence* (its last token and the one
    before its name): a number before it ("version 2 of the GPL") is its
    version; else it names none."""
    k = _skip(tokens, licence[1])
    while k >= 0 and tokens[k][1].lower() in ("the", "this"):
        k = _skip(tokens, k - 1)
    if k >= 0 and tokens[k][1].lower() == "of":
        k = _skip(tokens, k - 1)
        if _is_number(tokens, k):
            owner, _ = _owner(tokens, k - 1)
            return Grant(tokens[k][0], end, tokens[k][1], family or owner)
    return Grant(tokens[licence[0]][0], end, None, family)

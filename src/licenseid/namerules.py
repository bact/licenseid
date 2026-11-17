# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules that doubt one name hit of the name tier (item 47).

``namehits`` weighs tied names against each other; these rules read what the
rest of the input says beside one hit's name. Each judges the words that
touch the name, not the whole input: a dash in ``Copyright 2015- the
authors`` or a ``with GCC`` in a sentence about a build says nothing about
the licence that the name states.

Standard library, ``types``, ``normalize`` and the readers of a version
(``versionkey``), a grant (``classify``, ``plusoperator``), a joiner
(``dropguard``) and a licence ID (``plusoperator``, ``listlookup``) only.
"""

import itertools
import re
from collections.abc import Callable, Collection, Iterable
from typing import Final, NamedTuple

from licenseid.classify import OR_LATER_PHRASE
from licenseid.dropguard import trailing_joiners
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text
from licenseid.plusoperator import PLUS_OPERATOR, grant_stem
from licenseid.types import LicenseNameId
from licenseid.versionkey import sibling_keys, version_key

#: Words that name no licence in particular: not counted as what an input
#: holds of a name, or what it holds more.
GENERIC: Final = frozenset({"license", "licence", "see", "file"})

#: The longest input whose version is read: its key costs a second
#: ``normalize_text``, and no name is that long.
_MAX_KEY_TEXT: Final = 500
#: The marks that separate the words of a list of IDs (``MIT, ISC``).
_WORD: Final = re.compile(r"[^\s,;/()\[\]]+")
#: The marks that join two IDs of a list, and those that bracket one.
_LIST_MARKS: Final = frozenset(",;/")
_ANY_MARKS: Final = frozenset(",;/()[]")
#: The words that join two IDs of a list (``MIT and ISC``), and those that
#: may stand between an ID and the name after it (``MIT, the Unlicense``).
_CONNECTORS: Final = frozenset({"and", "or", "&"})
_DETERMINERS: Final = frozenset({"a", "an", "the", "this"})
_EXCEPTION_WORDS: Final = frozenset({"exception", "exceptions"})
#: Words that lie in the name of an exception without naming it ("with or
#: without modification" ends in a window as "with or"), or in a name
#: without naming a licence ("The IPA Group").
_FUNCTION_WORDS: Final = frozenset(
    {"a", "an", "and", "any", "in", "is", "of", "or", "that", "the", "this", "to"}
)
#: The words after a "with" in which "exception" is the licence's
#: (``with the Universal FOSS exception``), and how far before it the name
#: of the licence may end (``Apache License 2.0 or later with ...``).
_EXCEPTION_REACH: Final = 5
#: The most words that tell one exception from the rest (the List's longest).
_MOST_TOLD: Final = 8
_NAME_REACH: Final = 3
#: The number a grant follows (``2`` of ``v2 or later``).
_NUMBER_BEFORE: Final = re.compile(r"(\d+(?:\.\d+)*)[\s,()\[\]*/#;-]*\Z")


def core(name: Iterable[str]) -> frozenset[str]:
    """The words of *name* that say which licence it is."""
    words = frozenset(name)
    return (words - GENERIC) or words


def cut_version(raw: str, rows: list[LicenseNameId], license_id: str) -> bool:
    """Whether *raw* writes the version of the licence *license_id* cut
    short: its number is the start of the licence's (``Apache License 1``
    against ``Apache License 1.1``; ``Apache License 2`` is ``2.0``: the
    key folds ``.0``). Both numbers are read as the ID key reads them
    (:func:`licenseid.versionkey.version_key`, so ``4.3TAHOE`` has its
    ``3``), and the cut is :func:`licenseid.versionkey.sibling_keys`: the
    licence's number is the input's with numbers after it, not all
    zeros. Not where *raw* states the version in full as well, nor where a
    grant ("or later", ``+``) stands right after the cut number:
    ``GNU Lesser General Public License v2 or later`` is LGPL-2.1-or-later,
    as a cut ID with a grant is, and ``Requires Java 8 or later`` grants
    nothing of ``Apache License 1``."""
    if len(raw) > _MAX_KEY_TEXT:
        return False
    name = next((r["name"] for r in rows if r["license_id"] == license_id), None)
    if name is None:
        return False
    stated = _number_runs(version_key(raw))
    listed = _number_runs(version_key(name))
    granted = _granted_numbers(raw)
    return any(
        _is_cut(run, whole, stated)
        for run in stated
        if run not in granted
        for whole in listed
    )


def _number_runs(key: str) -> list[list[str]]:
    """The runs of numbers in a version key, in order."""
    runs: list[list[str]] = []
    run: list[str] = []
    for token in key.split():
        if token.isascii() and token.isdigit():
            run.append(token)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    return runs


def _granted_numbers(raw: str) -> list[list[str]]:
    """The numbers (as runs of digits) that a grant stands right after in
    *raw*: the ``2`` of ``v2 or later`` and of ``v2+``."""
    numbers: list[str] = []
    for phrase in OR_LATER_PHRASE.finditer(raw):
        # The phrase after a number starts with its last digit.
        end = phrase.start() + (1 if phrase.group()[:1].isdigit() else 0)
        numbers.append(raw[:end])
    numbers.extend(plus.group("id") for plus in PLUS_OPERATOR.finditer(raw))
    found = (_NUMBER_BEFORE.search(text) for text in numbers)
    return [match.group(1).split(".") for match in found if match]


def _is_cut(run: list[str], whole: list[str], stated: list[list[str]]) -> bool:
    """Whether *run* is *whole* cut short (not all zeros left), and *whole*
    is not among the *stated* runs."""
    if whole in stated or len(run) >= len(whole):
        return False
    key, other = "v " + " ".join(run), "v " + " ".join(whole)
    extra = whole[len(run) :]
    return bool(sibling_keys([other], key)) and any(part.strip("0") for part in extra)


def glued_dash(raw: str, name: Collection[str]) -> bool:
    """Whether a word of *raw* that touches the name (it is, or stands
    beside, a word of *name*: generic words aside) ends in a dash or an
    underscore (``MIT-``, ``-or-``): the author's mark is dropped by
    ``normalize_text``, and a cut word (``MIT-`` starts ``MIT-0``) is no
    value written whole. A dash elsewhere (``Copyright 2015- present``,
    ``pre- and post-``) is about something else. The reader of the dash is
    :func:`licenseid.dropguard.trailing_joiners`."""
    named = core(name)
    parts = raw.split()
    return any(
        trailing_joiners(word)
        and any(
            named & set(normalize_text(w).split()) for w in parts[max(0, i - 1) : i + 2]
        )
        for i, word in enumerate(parts)
    )


def fragment_of_longer(
    query: frozenset[str],
    name: frozenset[str],
    listed: Iterable[frozenset[str]],
) -> bool:
    """Whether the hit is a shorter name the input holds, and the rest of
    the input's words (generic words aside) lie in a longer name of the
    List: ``MIT Future License`` is the start of another licence's name, not
    MIT with a word more. An input that is the hit's name and generic words
    only is not a fragment."""
    extra = query - core(name) - GENERIC
    if not extra or not core(name) <= query:
        return False
    evidence = query - GENERIC
    return any(evidence <= other and other != name for other in listed)


def names_an_exception(
    words: list[str],
    name: frozenset[str],
    exception_words: Callable[[], Collection[frozenset[str]]],
) -> bool:
    """Whether the words after a "with" that follows the licence's name name
    an exception: the word "exception" a few words on (``Apache License 2.0
    with the LLVM exception``; not ``with no exceptions``), or the words that
    tell an exception of the List of several words from the rest (its name
    and ID without "exception", numbers and common words) right after the
    "with" (``GPL-2.0 with Linux syscall note``). One word is not enough:
    ``built with GCC``, ``compatible with Swift`` and ``works with Linux``
    are no exceptions. A "with" of the name's own is skipped (``HPND sell
    variant with MIT disclaimer``), and "with" alone is no doubt ("in
    compliance with the License", "with or without modification")."""
    starts = [i for i, word in enumerate(words) if word == "with"]
    if "with" in name:
        starts = starts[1:]
    named = core(name) - _FUNCTION_WORDS
    for start in starts:
        if not named.intersection(words[max(0, start - _NAME_REACH) : start]):
            continue
        if _says_exception(words[start + 1 : start + 1 + _EXCEPTION_REACH]):
            return True
        told = list(
            itertools.islice(
                (
                    w
                    for w in itertools.islice(words, start + 1, None)
                    if _tells_exception(w)
                ),
                _MOST_TOLD,
            )
        )
        if told and any(
            len(core_words) > 1 and set(told[: len(core_words)]) == core_words
            for core_words in map(_distinctive, exception_words())
        ):
            return True
    return False


def _says_exception(after: list[str]) -> bool:
    """Whether "exception" stands in *after*, not as "no exception"."""
    return any(
        word in _EXCEPTION_WORDS and (i == 0 or after[i - 1] != "no")
        for i, word in enumerate(after)
    )


def _tells_exception(word: str) -> bool:
    """Whether *word* can tell one exception from another."""
    return not (
        word in _FUNCTION_WORDS or word in GENERIC or word.isdigit() or word == "with"
    )


def _distinctive(listed: frozenset[str]) -> frozenset[str]:
    """The words of an exception's name or ID that tell it from the rest."""
    return frozenset(
        word
        for word in listed
        if word not in _EXCEPTION_WORDS and _tells_exception(word)
    )


class _Token(NamedTuple):
    """A word of the input without the marks round it, the text between it and
    the word before, and whether a ")" follows it right away."""

    text: str
    gap: str
    closed: bool


def _tokens(raw: str) -> list[_Token]:
    """The words of *raw* (``MIT, ISC`` has two) with the gap before each."""
    tokens: list[_Token] = []
    end = 0
    for match in _WORD.finditer(raw):
        text = match.group().strip(".:\"'")
        if text:
            tokens.append(
                _Token(text, raw[end : match.start()], raw[match.end() :][:1] == ")")
            )
        end = match.end()
    return tokens


def names_another_id(
    raw: str, rows: list[LicenseNameId], license_id: str, name: frozenset[str]
) -> bool:
    """Whether *raw* writes the ID of another licence whole, in words that
    the hit's name does not have, and as a licence beside the name: joined to
    it by a comma, a semicolon, a slash, "and", "or" or "&" (``BSD-3-Clause,
    Apache License 2.0``, ``MIT, ISC``, ``ISC License and Apache-2.0``), an
    ID with a digit or a dash also in brackets. Not an ID of the name's
    sentence that is none of these (``MIT License. Depends on python-ldap``,
    ``MIT License, copyright (c) 2020 The IPA Group``), and not an ID that
    is an ordinary word (``Intel``, ``Fair``, ``Unlicense``, ``curl``)."""
    ids = {fold_case(row["license_id"]): row["license_id"] for row in rows}
    mine = fold_case(grant_stem(license_id))
    tokens = _tokens(raw)
    for i, token in enumerate(tokens):
        found = ids.get(fold_case(token.text))
        if (
            found is not None
            and fold_case(grant_stem(found)) != mine
            and not frozenset(normalize_text(token.text).split()) <= name
            and _written_as_id(found, tokens, i, name)
        ):
            return True
    return False


def _written_as_id(
    license_id: str, tokens: list[_Token], index: int, name: frozenset[str]
) -> bool:
    """Whether the token at *index* writes *license_id* as a licence beside
    the *name*: an ID with a digit or a dash, or an acronym."""
    if _has_id_shape(license_id):
        return _beside_name(tokens, index, name, _ANY_MARKS)
    if not _is_acronym(license_id, tokens[index].text):
        return False
    # An acronym alone in brackets is a licence too: ``MIT License (ISC)``.
    marks = _LIST_MARKS | {"("} if tokens[index].closed else _LIST_MARKS
    return _beside_name(tokens, index, name, marks)


def _has_id_shape(license_id: str) -> bool:
    """Whether *license_id* has a digit or a dash: no ordinary word."""
    return any(char.isdigit() or char == "-" for char in license_id)


def _is_acronym(license_id: str, written: str) -> bool:
    """Whether *written* is the ID *license_id*, upper-case letters, as it
    is."""
    return written == license_id and len(license_id) > 1 and license_id.isupper()


def _beside_name(
    tokens: list[_Token], index: int, name: frozenset[str], marks: Collection[str]
) -> bool:
    """Whether the word before or after ``tokens[index]`` is one of the words
    of *name*, joined to it: a mark of *marks* in the gap, or an "and", "or"
    or "&" looked through (and a "the" before the word after)."""
    named = name - _FUNCTION_WORDS
    for step in (-1, 1):
        joined, at = False, index
        while True:
            nxt = at + step
            if not 0 <= nxt < len(tokens):
                break
            gap = tokens[at].gap if step < 0 else tokens[nxt].gap
            joined = joined or any(mark in gap for mark in marks)
            word = tokens[nxt].text.lower()
            if word in _CONNECTORS or (step > 0 and word in _DETERMINERS):
                joined = joined or word in _CONNECTORS
                at = nxt
                continue
            if joined and named & set(normalize_text(word).split()):
                return True
            break
    return False

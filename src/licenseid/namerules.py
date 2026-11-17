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
(``versionkey``), a grant (``grantsubject``, the one reader of whose grant a
phrase is; ``classify.same_version``), a joiner (``dropguard``) and a licence
ID (``plusoperator``, ``listlookup``) only.
"""

import itertools
import re
from collections.abc import Callable, Collection, Iterable
from typing import Final, NamedTuple

from licenseid.classify import same_version
from licenseid.dropguard import trailing_joiners
from licenseid.grantsubject import MODIFIERS, Grant, grants, grants_licence
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text
from licenseid.plusoperator import grant_stem
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
#: The IDs that carry a grant: only these have a version that "or later"
#: leaves open, as a cut number does.
_CARRIES_GRANT: Final = ("-or-later", "+")
#: A family reader's grant of the GPL, for asking whether an ID is its own.
_GPL: Final = Grant(0, 0, None, "gpl")


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
    zeros. Not where *raw* writes the licence's number in full as well, at
    the place the name has it (``Apache License 1.1`` and ``Requires Java
    1``; a number that follows other words, ``Requires Java 1.1``, is not
    the licence's), nor for a number that a grant of the licence qualifies,
    where the hit carries the grant: ``GNU Lesser General Public License v2
    or later`` is the one LGPL-2.1-or-later of the List, while ``Requires
    Java 1 or later`` grants nothing of ``Apache License 1``, and ``Apache
    License 1 or later`` names no row (Apache has no ``-or-later`` ID). A
    grant exempts one written number (:func:`_without_grants`)."""
    if len(raw) > _MAX_KEY_TEXT:
        return False
    name = next((r["name"] for r in rows if r["license_id"] == license_id), None)
    if name is None:
        return False
    stated = _runs_before(version_key(raw))
    listed = _runs_before(version_key(name))
    return any(
        _is_cut(run, whole, _runs_after(stated, words))
        for run in _without_grants([run for run, _ in stated], raw, license_id)
        for whole, words in listed
    )


def _runs_before(key: str) -> list[tuple[list[str], list[str]]]:
    """The runs of numbers in a version key, in order, each with the words
    before it (since the run before)."""
    runs: list[tuple[list[str], list[str]]] = []
    words: list[str] = []
    run: list[str] = []
    for token in key.split():
        if token.isascii() and token.isdigit():
            run.append(token)
        else:
            if run:
                runs.append((run, words))
                run, words = [], []
            words.append(token)
    if run:
        runs.append((run, words))
    return runs


def _runs_after(
    stated: list[tuple[list[str], list[str]]], listed_words: list[str]
) -> list[list[str]]:
    """The runs of *stated* that follow the word that a run of the name
    follows (the last of *listed_words*, the words before it in the name),
    within :data:`_NAME_REACH` words: ``license`` of ``Apache License 1.1``,
    and ``EGENIX.COM PUBLIC LICENSE AGREEMENT Version 1.1.0``. A name's run
    with no word before it (``3D Slicer License``) is any run."""
    word = listed_words[-1] if listed_words else None
    return [
        run for run, words in stated if word is None or word in words[-_NAME_REACH:]
    ]


def _without_grants(
    runs: list[list[str]], raw: str, license_id: str
) -> list[list[str]]:
    """The *runs* of numbers that no grant of the licence qualifies: each
    grant of *license_id* in *raw* (``v2`` of ``GNU Lesser General Public
    License v2 or later``; not the ``1`` of ``Requires Java 1 or later``)
    takes out one written run, where the hit carries a grant. An ID with
    none (``Apache-1.1``) leaves them all: ``Apache License 1 or later``
    names another licence than the hit."""
    left = list(runs)
    if not license_id.endswith(_CARRIES_GRANT):
        return left
    for grant in grants(raw):
        if grant.version and grants_licence(grant, license_id):
            _drop_first(left, grant.version)
    return left


def _drop_first(runs: list[list[str]], version: str) -> None:
    """Remove from *runs* the first run that is *version* (one written number
    per grant)."""
    for at, run in enumerate(runs):
        if same_version(".".join(run), version):
            del runs[at]
            return


def _is_cut(run: list[str], whole: list[str], written: list[list[str]]) -> bool:
    """Whether *run* is *whole* cut short (not all zeros left), and *whole*
    is not among the runs *written* right after the name."""
    if whole in written or len(run) >= len(whole):
        return False
    key, other = "v " + " ".join(run), "v " + " ".join(whole)
    extra = whole[len(run) :]
    return bool(sibling_keys([other], key)) and any(part.strip("0") for part in extra)


def names_other_gnu_licence(words: list[str], license_id: str) -> bool:
    """Whether a GPL hit stands for an input whose ``General Public`` is the
    LGPL's or the AGPL's: ``Lesser``, ``Library`` or ``Affero``
    (:data:`licenseid.grantsubject.MODIFIERS`) stands right before it, a
    ``GNU`` between aside, and no ``General Public`` is the plain GPL's. The
    name of the GPL holds those words, so token set scoring gives it 100,
    the modifier being a word more. No grant is read: ``GNU Lesser General
    Public License v2.0 only`` names the LGPL as much as ``... v2.0 or
    later``. An input that writes both (``GNU General Public License v3.0.
    Not the GNU Lesser General Public License``) names the GPL too. The ID's
    family is read by :func:`licenseid.grantsubject.grants_licence`."""
    if not grants_licence(_GPL, license_id):
        return False
    named = [
        _before(words, at) in MODIFIERS
        for at in range(len(words) - 1)
        if words[at : at + 2] == ["general", "public"]
    ]
    return bool(named) and all(named)


def _before(words: list[str], at: int) -> str:
    """The word before the one at *at* ("" at the start), a ``gnu`` skipped."""
    before = words[:at][-2:]
    if before[-1:] == ["gnu"]:
        before = before[:-1]
    return before[-1] if before else ""


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

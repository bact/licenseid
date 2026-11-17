# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Which name hits of the name tier stand (item 47).

Token set scoring (``shorttext``) reads the words of an input as a set, so
it scores a name 100 when the input holds every word of the name, whatever
else the input says. That is right for ``Licensed under the MIT License``
and wrong when the extra words name something else: another licence
(``MIT or Apache License 2.0``), an exception (``Apache License 2.0 with
LLVM exception``), a longer name the input is the start of (``MIT Future
License``) or a version cut short (``Apache License 1`` is no ``Apache-1.1``).
The SPDX matching guidelines make a different version, exception or licence
a different licence, so a name hit that one of the rules below doubts is
dropped, and the input gets no name answer.

Limits, measured and kept open (roadmap item 47): only names that tie at the
top score are weighed against each other, so a grant-less GPL name next to
``MIT License`` (``GNU General Public License v2.0 or MIT License``) still
answers MIT.

The precision principle of the project: a doubtful answer is no answer.
:func:`settle` returns the hits that stand and, when it dropped a hit that
would have answered (score above 1), says so: the caller then gives no text
answer either (``detector._short_text_refused``).

A word is no evidence for or against a name when it says nothing about which
licence is meant: :data:`GENERIC` ("license", "see", "file": ``MIT No
Attribution (see LICENSE)``). Standard library, ``types`` and the
readers of a version (``versionkey``), a grant (``classify``), a joiner
(``dropguard``), a licence ID (``plusoperator``, ``listlookup``) and
``resolvefirst``'s word count only.
"""

import re
from collections.abc import Callable, Collection
from typing import Final, NamedTuple

from licenseid.classify import OR_LATER_PHRASE
from licenseid.dropguard import trailing_joiners
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text
from licenseid.plusoperator import grant_stem, strip_plus_operator
from licenseid.resolvefirst import MIN_TEXT_WORDS
from licenseid.types import LicenseNameId, RawMatch
from licenseid.versionkey import sibling_keys, version_key

#: Words that name no licence in particular: not counted as what an input
#: holds of a name, or what it holds more.
GENERIC: Final = frozenset({"license", "licence", "see", "file"})

#: The longest input whose version is read: its key costs a second
#: ``normalize_text``, and no name is that long.
_MAX_KEY_TEXT: Final = 500
#: The marks that separate the words of a list of IDs (``MIT, ISC``).
_ID_SEPARATORS: Final = re.compile(r"[\s,;/()\[\]]+")
_EXCEPTION_WORDS: Final = frozenset({"exception", "exceptions"})
#: Words that lie in the name of an exception without naming it ("with or
#: without modification" ends in a window as "with or").
_FUNCTION_WORDS: Final = frozenset(
    {"a", "an", "and", "any", "in", "is", "of", "or", "that", "the", "this", "to"}
)


class NameHits(NamedTuple):
    """The name hits that stand, and whether a rule dropped a hit that would
    have answered (score above 1): then no later tier may answer either."""

    found: list[RawMatch]
    refused: bool


class _Input(NamedTuple):
    """What the rules read of one input: the raw text, its normalised
    *words*, the List's rows, and the words of each name by ID."""

    raw: str
    words: list[str]
    rows: list[LicenseNameId]
    names: dict[str, frozenset[str]]


def refusal_answer(word_count: int) -> list[RawMatch] | None:
    """What a refused name hit leaves of Tier 0, for an input of
    *word_count* normalised words: no answer at all from
    :data:`~licenseid.resolvefirst.MIN_TEXT_WORDS` words on (no text answer
    round a doubted name either), else None, so ``too_short`` still says why
    the input is no licence value."""
    return [] if word_count >= MIN_TEXT_WORDS else None


def settle(
    ranked: list[RawMatch],
    rows: list[LicenseNameId],
    words: list[str],
    raw: str,
    exception_words: Callable[[], Collection[frozenset[str]]],
) -> NameHits:
    """The hits of *ranked* (sorted, by name and ID, for the input *words*
    that normalised *raw*) that stand. Only a top hit found by name that
    is not exact is judged: an exact name is the input. *exception_words*
    reads the words of the List's exceptions, when asked."""
    top = ranked[0] if ranked else None
    if top is None or top["exact"] or top["method"] != "name":
        return NameHits(ranked, False)
    names = {row["license_id"]: frozenset(row["norm_name"].split()) for row in rows}
    found = _settle_ties(ranked, names, frozenset(words))
    if found is not None:
        first = names.get(found[0]["license_id"])
        given = _Input(raw, words, rows, names)
        if first is not None and _doubted(found[0], first, given, exception_words):
            found = None
    if found is None:
        return NameHits([], top["score"] > 1.0)
    return NameHits(found, False)


def _doubted(
    hit: RawMatch,
    name: frozenset[str],
    given: _Input,
    exception_words: Callable[[], Collection[frozenset[str]]],
) -> bool:
    """Whether a rule doubts *hit*, whose name has the words *name*."""
    return (
        cut_version(given.raw, given.rows, hit["license_id"])
        or glued_dash(given.raw)
        or fragment_of_longer(frozenset(given.words), name, given.names.values())
        or names_an_exception(given.words, name, exception_words)
        or names_another_id(given.raw, given.rows, hit["license_id"], name)
    )


def _core(name: frozenset[str]) -> frozenset[str]:
    """The words of *name* that say which licence it is."""
    return (name - GENERIC) or name


def _settle_ties(
    ranked: list[RawMatch], names: dict[str, frozenset[str]], query: frozenset[str]
) -> list[RawMatch] | None:
    """*ranked* with the hits of the most specific licence only, where the
    top score is tied by the names of several licences (the twins -only and
    -or-later of one are one licence): the input holds each name whole, as
    words (``Licensed under the Apple Public Source License 1.2`` holds
    APSL-1.1's and APSL-1.2's names), and the names nest (generic words
    aside), the longest holding the others: its licence is the one named,
    and the others tied with it are dropped. None where the tie is no
    answer: two licences not nested (``UPL 1.0 or Apache License 2.0``).
    A name that the input only lies in (token set scores it 100 too) is
    left to :func:`fragment_of_longer`; names that all hold the input in
    part (a deprecated name of its own, held by the names that replaced
    it) are left as ``shorttext._partial_names`` kept them."""
    top = ranked[0]["score"]
    held: dict[str, frozenset[str]] = {}
    partial: set[str] = set()
    for hit in ranked:
        if hit["score"] != top or hit["method"] != "name":
            continue
        name = names.get(hit["license_id"])
        if name is None:
            return ranked  # a row that is gone: nothing to weigh
        stem = grant_stem(hit["license_id"])
        if name <= query:
            held[stem] = max(held.get(stem, frozenset()), name, key=len)
        else:
            partial.add(stem)
    if len(held) + len(partial - held.keys()) < 2:
        return ranked
    if not held:
        return ranked  # names that only hold the input: _partial_names kept them
    ordered = sorted(held.items(), key=lambda item: -len(_core(item[1])))
    best, best_name = ordered[0]
    if not all(_core(name) < _core(best_name) for _, name in ordered[1:]):
        return None  # not nested: two licences are named
    # The names tied with the winner are not the answer either: with the
    # winner excluded, no tied hit is left to answer.
    return [
        hit
        for hit in ranked
        if hit["score"] != top
        or hit["method"] != "name"
        or grant_stem(hit["license_id"]) == best
    ]


def cut_version(raw: str, rows: list[LicenseNameId], license_id: str) -> bool:
    """Whether *raw* writes the version of the licence *license_id* cut
    short: its number is the start of the licence's (``Apache License 1``
    against ``Apache License 1.1``; ``Apache License 2`` is ``2.0``: the
    key folds ``.0``). Both numbers are read as the ID key reads them
    (:func:`licenseid.versionkey.version_key`, so ``4.3TAHOE`` has its
    ``3``), and the cut is :func:`licenseid.versionkey.sibling_keys`: the
    licence's number is the input's with numbers after it, not all
    zeros. Not where *raw* states the version in full as well, nor where it
    reads a grant ("or later", ``+``): ``GNU Lesser General Public License
    v2 or later`` is LGPL-2.1-or-later, as a cut ID with a grant is."""
    if len(raw) > _MAX_KEY_TEXT:
        return False
    name = next((r["name"] for r in rows if r["license_id"] == license_id), None)
    if name is None or OR_LATER_PHRASE.search(raw) or strip_plus_operator(raw) != raw:
        return False
    stated = _number_runs(version_key(raw))
    listed = _number_runs(version_key(name))
    return any(_is_cut(run, whole, stated) for run in stated for whole in listed)


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


def _is_cut(run: list[str], whole: list[str], stated: list[list[str]]) -> bool:
    """Whether *run* is *whole* cut short (not all zeros left), and *whole*
    is not among the *stated* runs."""
    if whole in stated or len(run) >= len(whole):
        return False
    key, other = "v " + " ".join(run), "v " + " ".join(whole)
    extra = whole[len(run) :]
    return bool(sibling_keys([other], key)) and any(part.strip("0") for part in extra)


def glued_dash(raw: str) -> bool:
    """Whether a word of *raw* ends in a dash or an underscore (``MIT-``,
    ``-or-``): the author's mark is dropped by ``normalize_text``, and a
    cut word (``MIT-`` starts ``MIT-0``) is no value written whole. The
    reader is :func:`licenseid.dropguard.trailing_joiners`."""
    return any(trailing_joiners(word) for word in raw.split())


def fragment_of_longer(
    query: frozenset[str],
    name: frozenset[str],
    listed: Collection[frozenset[str]],
) -> bool:
    """Whether the hit is a shorter name the input holds, and the rest of
    the input's words (generic words aside) lie in a longer name of the
    List: ``MIT Future License`` is the start of another licence's name, not
    MIT with a word more. An input that is the hit's name and generic words
    only is not a fragment."""
    extra = query - _core(name) - GENERIC
    if not extra or not _core(name) <= query:
        return False
    evidence = query - GENERIC
    return any(evidence <= other and other != name for other in listed)


def names_an_exception(
    words: list[str],
    name: frozenset[str],
    exception_words: Callable[[], Collection[frozenset[str]]],
) -> bool:
    """Whether the words after a "with" of the input name an exception: the
    word "exception", or the words that tell one exception of the List from
    the rest (its name and ID without "exception", numbers and common
    words) right after the "with" (``Apache License 2.0 with LLVM
    exception``, ``... with LLVM``). One word of an exception's name is not
    enough: ``works with Linux`` is no ``Linux-syscall-note``. A "with" of
    the name's own is skipped (``HPND sell variant with MIT disclaimer``),
    and "with" alone is no doubt ("in compliance with the License",
    "with or without modification")."""
    starts = [i for i, word in enumerate(words) if word == "with"]
    if "with" in name:
        starts = starts[1:]
    for start in starts:
        after = words[start + 1 :]
        if _EXCEPTION_WORDS.intersection(after):
            return True
        told = [word for word in after if _tells_exception(word)]
        if told and any(
            set(told[: len(core)]) == core
            for core in map(_distinctive, exception_words())
            if core
        ):
            return True
    return False


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


def names_another_id(
    raw: str, rows: list[LicenseNameId], license_id: str, name: frozenset[str]
) -> bool:
    """Whether *raw* writes the ID of another licence whole, in words that
    the hit's name does not have: an ID with a digit or a dash
    (``BSD-3-Clause, Apache License 2.0``), or an upper-case one of
    letters, written as it is (``MIT, ISC``). Not an ID that is an ordinary
    word (``Intel``, ``Fair``, ``Unlicense``, ``curl``)."""
    ids = {fold_case(row["license_id"]): row["license_id"] for row in rows}
    mine = fold_case(grant_stem(license_id))
    for token in _ID_SEPARATORS.split(raw):
        token = token.strip(".:\"'")
        found = ids.get(fold_case(token))
        if (
            found is not None
            and _is_id_not_word(found, token)
            and fold_case(grant_stem(found)) != mine
            and not frozenset(normalize_text(token).split()) <= name
        ):
            return True
    return False


def _is_id_not_word(license_id: str, written: str) -> bool:
    """Whether *written*, the ID *license_id* in any case, names the ID and
    not an ordinary word: the ID has a digit or a dash, or is upper-case
    letters and is written so."""
    if any(char.isdigit() or char == "-" for char in license_id):
        return True
    return written == license_id and len(license_id) > 1 and license_id.isupper()

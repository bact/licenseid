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
a different licence, so a name hit that one of the rules doubts is dropped,
and the input gets no name answer. This module weighs the names that tie at
the top score (:func:`settle`); ``namerules`` has the rules that read what
stands beside one name.

Limits, measured and kept open (roadmap item 47): only names that tie at the
top score are weighed against each other, and a lower-scoring licence named
whole is another name only with its ``v`` and its grant left out
(:func:`_names_another`), so ``MIT License or BSD 3-Clause`` is still open.

The precision principle of the project: a doubtful answer is no answer.
:func:`settle` returns the hits that stand and, when it dropped a hit that
would have answered (score above 1), says so: the caller then gives no text
answer either (``detector._short_text_refused``).

Standard library, ``types``, ``namerules``, ``plusoperator`` (the grant stem
of an ID) and ``resolvefirst``'s word count only.
"""

import itertools
import re
from collections.abc import Callable, Collection, Sequence
from typing import Final, NamedTuple

from licenseid.namerules import (
    GENERIC,
    cut_version,
    fragment_of_longer,
    glued_dash,
    names_an_exception,
    names_another_id,
    names_other_gnu_licence,
)
from licenseid.plusoperator import grant_stem
from licenseid.resolvefirst import MIN_TEXT_WORDS
from licenseid.types import LicenseNameId, RawMatch

__all__ = ["GENERIC", "NameHits", "refusal_answer", "settle"]

#: A version written as a letter and a number (``v1`` of ``v1.0``).
_V_NUMBER: Final = re.compile(r"v(\d+)\Z")

#: The words of a grant that end a name (``or later``, ``only``): another
#: licence's grant may stand elsewhere in the input.
_GRANT_WORDS: Final = frozenset({"or", "later", "only"})

#: The generic word a name holds (``Zlib License``; ``licence`` is read as
#: ``license``): ``see`` and ``file`` are none, so they stand between a name and
#: a word that follows it.
_NAME_WORDS: Final = frozenset({"license"})

#: The words that join two names of a list (a comma is no word).
_JOINERS: Final = frozenset({"or", "and"})

#: The words that point at a name (``or see Zlib``, ``Zlib (see file)``): they
#: stand beside a one-word name that a joining word joins, and are no part of it.
_REFERENCE_WORDS: Final = frozenset({"see", "file"})


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
    names: dict[str, list[str]]


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
    names = {row["license_id"]: row["norm_name"].split() for row in rows}
    found = _settle_ties(ranked, names, words)
    if found is not None:
        first = names.get(found[0]["license_id"])
        given = _Input(raw, words, rows, names)
        if first is not None and (
            _doubted(found[0], first, given, exception_words)
            or _names_another(found[0], ranked, names, words)
        ):
            found = None
    if found is None:
        return NameHits([], top["score"] > 1.0)
    return NameHits(found, False)


def _doubted(
    hit: RawMatch,
    name: list[str],
    given: _Input,
    exception_words: Callable[[], Collection[frozenset[str]]],
) -> bool:
    """Whether a rule doubts *hit*, whose name has the words *name*."""
    held = frozenset(name)
    return (
        cut_version(given.raw, given.rows, hit["license_id"])
        or glued_dash(given.raw, held)
        or fragment_of_longer(
            frozenset(given.words), held, map(frozenset, given.names.values())
        )
        or names_an_exception(given.words, held, exception_words)
        or names_another_id(given.raw, given.rows, hit["license_id"], held)
        or names_other_gnu_licence(given.words, hit["license_id"])
    )


def _plain(words: Sequence[str]) -> list[str]:
    """*words* with a version ``v1`` read as the number 1 (``Universal
    Permissive License v1.0``, written ``UPL 1.0``)."""
    return [m.group(1) if (m := _V_NUMBER.match(w)) else w for w in words]


def _names_another(
    found: RawMatch,
    ranked: list[RawMatch],
    names: dict[str, list[str]],
    words: list[str],
) -> bool:
    """Whether the input writes the name of another licence whole as well,
    one that scores below the hit only for its ``v`` of a version or its
    grant (``Universal Permissive License 1.0 or Apache License 2.0``,
    ``GNU General Public License version 2.0, requires Python 3.8``): two
    licences are named, whichever the names nest in. A name that holds, or
    lies in, the hit's is the hit's own."""
    best = names[found["license_id"]]
    mine = grant_stem(found["license_id"])
    spoken = _plain(words)
    for hit in ranked:
        name = names.get(hit["license_id"])
        if hit["score"] >= ranked[0]["score"] or name is None:
            continue
        said, own = _without_grant(_plain(name)), tuple(_plain(best))
        if (
            grant_stem(hit["license_id"]) != mine
            and _runs_in(said, spoken)
            and not (_runs_in(said, own) or _runs_in(own, said))
        ):
            return True
    return False


def _without_grant(name: Sequence[str]) -> tuple[str, ...]:
    """*name* without the grant at its end (``or later``, ``only``): one
    licence's grant is no part of the other's."""
    end = len(name)
    while end > 1 and name[end - 1] in _GRANT_WORDS:
        end -= 1
    return tuple(name[:end])


def _said(name: Sequence[str]) -> tuple[str, ...]:
    """The words of *name* that say which licence it is, in order."""
    return tuple(word for word in name if word not in GENERIC) or tuple(name)


def _written_whole(name: Sequence[str], words: list[str], spoken: list[str]) -> bool:
    """Whether the input writes *name* whole: the words of it that say which
    licence it is, in order and close (*spoken*, the input's words without
    generic ones; ``Open Software Licensev. 2.1``). Where one word says it
    (``ICU License``), the generic word must stand beside it in *words*:
    ``uses ICU for the license terms`` writes no such name."""
    said = _said(name)
    if len(said) > 1:
        return _runs_in(said, spoken)
    return _runs_in(tuple(name), words)


def _places(part: Sequence[str], whole: Sequence[str]) -> dict[int, int]:
    """Where the words *part* stand in *whole* in this order and close
    together: ``{start: words spanned}``. An ordinary word is at most one
    word after the last (``SIL Open Font License 1.1`` stands in ``SIL Open
    Font License, Version 1.1``; ``Open Software License`` does not stand in
    ``Software ... Open ... License``), the first number of a version at most
    two words after it (``License (CDDL) Version 1.0``), the next number
    right after; a generic word at most three words after it (``Motosoto
    Open Source License``)."""
    first = part[0] if part else None
    found: dict[int, int] = {}
    for start in (i for i, word in enumerate(whole) if word == first):
        at = start
        for last, word in itertools.pairwise(part):
            if word.isdigit():
                reach = 0 if last.isdigit() else 2
            else:
                reach = 3 if word in GENERIC else 1
            ahead = whole[at + 1 : at + 2 + reach]
            if word not in ahead:
                break
            at += ahead.index(word) + 1
        else:
            found[start] = at - start
    return found


def _runs_in(part: Sequence[str], whole: Sequence[str]) -> bool:
    """Whether the words *part* stand in *whole* (:func:`_places`)."""
    return bool(_places(part, whole))


def _tightest(held: dict[str, tuple[str, ...]], spoken: list[str]) -> str | None:
    """The licence whose name the input writes in the fewest words, where
    the names tell by their numbers only and stand from the same word of the
    input (``Open Software License version 2.1 1) Grant`` writes 2.1 in
    fewer words than 1.1, the 1 of its list). None where they differ in
    other words, tie, or stand apart (``Apache License, Version 2.0; before,
    Apache License 1.1`` names two versions)."""
    titles = {
        tuple(word for word in said if not word.isdigit()) for said in held.values()
    }
    places = {stem: _places(said, spoken) for stem, said in held.items()}
    shared = set.intersection(*(set(found) for found in places.values()))
    if len(titles) != 1 or not shared:
        return None
    start = min(shared)
    spans = sorted((found[start], stem) for stem, found in places.items())
    return spans[0][1] if spans[0][0] < spans[1][0] else None


def _nested_by_words(part: Sequence[str], whole: Sequence[str]) -> bool:
    """Whether the words of *part* are among those of *whole*, which has a
    word that is no number more: ``1.1`` is the words 1 and 1, so a name
    with another number is no name that holds it."""
    extra = set(whole) - set(part)
    return set(part) < set(whole) and any(not word.isdigit() for word in extra)


def _settle_ties(
    ranked: list[RawMatch], names: dict[str, list[str]], words: list[str]
) -> list[RawMatch] | None:
    """*ranked* with the hits of the most specific licence only, where the
    top score is tied by the names of several licences (the twins -only and
    -or-later of one are one licence). The input holds each name as words
    (``Licensed under the Apple Public Source License 1.2`` holds APSL-1.1's
    and APSL-1.2's names: token set reads ``1.1`` as the word 1). A name the
    input writes whole, its words in order and close, is the one named; a
    name made of words from here and there is not (``This library is free
    software under the GNU General Public License v2.0 only`` holds the
    Library GPL's words too). Of the names written whole the longest licence
    wins where they nest, the others tied with it are dropped; None where
    the tie is no answer: two licences not nested (``Apache License 2.0 or
    Zlib``), or another tied name that also stands apart from the winner's
    (:func:`_stands_apart`). Where no name is written whole, names nest by
    their words, a longer name that adds more than a number. A name that the
    input only lies in (token set scores it 100 too) is left to
    ``fragment_of_longer``; names that all hold the input in part (a
    deprecated name of its own, held by the names that replaced it) are left
    as ``shorttext._partial_names`` kept them."""
    top = ranked[0]["score"]
    query = frozenset(words)
    spoken = [word for word in words if word not in GENERIC]
    whole: dict[str, tuple[str, ...]] = {}
    scattered: dict[str, tuple[str, ...]] = {}
    partial: set[str] = set()
    for hit in ranked:
        if hit["score"] != top or hit["method"] != "name":
            continue
        name = names.get(hit["license_id"])
        if name is None:
            return ranked  # a row that is gone: nothing to weigh
        stem = grant_stem(hit["license_id"])
        if not query.issuperset(name):
            partial.add(stem)
            continue
        said = _said(name)
        side = whole if _written_whole(name, words, spoken) else scattered
        if len(said) >= len(side.get(stem, ())):
            side[stem] = said
    if len(whole.keys() | scattered.keys() | partial) < 2:
        return ranked
    if not (whole or scattered):
        return ranked  # names that only hold the input: _partial_names kept them
    # Names written whole beat names put together from scattered words.
    held, nested = (whole, _runs_in) if whole else (scattered, _nested_by_words)
    best = _most_specific(held, nested, spoken)
    if best is None or (whole and _stands_apart(best, whole, scattered, words)):
        return None  # not nested, or nested but written apart: two licences
    # The names tied with the winner are not the answer either: with the
    # winner excluded, no tied hit is left to answer.
    return [
        hit
        for hit in ranked
        if hit["score"] != top
        or hit["method"] != "name"
        or grant_stem(hit["license_id"]) == best
    ]


def _most_specific(
    held: dict[str, tuple[str, ...]],
    nested: Callable[[Sequence[str], Sequence[str]], bool],
    spoken: list[str],
) -> str | None:
    """The licence of the longest of the names *held* where the rest nest in
    it, else (names of one title that differ by a number) the one written
    in the fewest words, else None."""
    ordered = sorted(held.items(), key=lambda item: -len(item[1]))
    best, best_name = ordered[0]
    if all(
        len(name) < len(best_name) and nested(name, best_name)
        for _, name in ordered[1:]
    ):
        return best
    return _tightest(held, spoken)


def _stands_apart(
    best: str,
    whole: dict[str, tuple[str, ...]],
    scattered: dict[str, tuple[str, ...]],
    words: list[str],
) -> bool:
    """Whether another tied name stands in *words* apart from the places of
    the winner *best*'s name: CC-BY-4.0's name nests in CC-BY-NC-4.0's, but
    ``... 4.0 International or ... Non Commercial 4.0 International`` names
    both. A grant at the end of a name is left out, so that one licence's
    ``or later`` is no part of the other's (``GNU Lesser General Public
    License v2.1 or later, GNU General Public License v2.0``). A name of one
    word counts only where it is listed beside the winner's (``Apache License
    2.0 or Zlib``): elsewhere a word such as ``Ntp`` or ``JSON`` says no name
    (``Apache License 2.0 (JSON module)``). Only ``license`` is left out of
    *words*: ``see`` and ``file`` stand between the name and the word
    (``Apache License 2.0 (see zlib)``)."""
    spoken = [word for word in words if word not in _NAME_WORDS]
    spans = _places(whole[best], spoken)
    for stem, said in (scattered | whole).items():
        if stem == best:
            continue
        part = list(_without_grant(said))
        apart = [
            at
            for at in _places(part, spoken)
            if not any(start <= at <= start + n for start, n in spans.items())
        ]
        if len(part) == 1:
            apart = [at for at in apart if _listed_beside(at, spans, spoken)]
        if apart:
            return True
    return False


def _listed_beside(at: int, spans: dict[int, int], spoken: list[str]) -> bool:
    """Whether the word at *at* of *spoken* is an item of a list with one of
    the *spans* (``{start: words spanned}``): right before or after it, or
    one joining word away, with the end of the input or a joining word on
    its other side (``Apache License 2.0 or Zlib``, not ``... 2.0 (JSON
    module)``). Where a joining word joins it, ``see`` and ``file`` stand
    beside it (``... 2.0 or see Zlib``, ``... or Zlib (see file)``)."""
    for start, n in spans.items():
        for edge, step in ((start + n, 1), (start, -1)):
            if _reached(edge, step, at, spoken) and _list_ends(at, step, spoken):
                return True
    return False


def _reached(edge: int, step: int, at: int, spoken: list[str]) -> bool:
    """Whether the word at *at* is the next one after *edge* in direction
    *step*, or the next after a joining word, which a reference may follow
    (``or see Zlib``) or precede (``2.0 (see file) or Zlib``): a reference
    with no joining word beside it joins nothing (``2.0 (see Zlib)``)."""
    near = _past_references(edge + step, step, spoken)
    if 0 <= near < len(spoken) and spoken[near] in _JOINERS:
        return _past_references(near + step, step, spoken) == at
    return edge + step == at


def _list_ends(at: int, step: int, spoken: list[str]) -> bool:
    """Whether the end of the input or a joining word follows the word at
    *at* in direction *step*, but for a reference (``Zlib (see file)``)."""
    far = _past_references(at + step, step, spoken)
    return not 0 <= far < len(spoken) or spoken[far] in _JOINERS


def _past_references(pos: int, step: int, spoken: list[str]) -> int:
    """*pos*, moved in direction *step* past the reference words."""
    while 0 <= pos < len(spoken) and spoken[pos] in _REFERENCE_WORDS:
        pos += step
    return pos

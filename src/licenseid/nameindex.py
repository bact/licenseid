# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What Tier 0 reads from the names of the List, worked out once.

``licenseid.shorttext`` compares each short input with every row of
``names_and_ids()``. Its choice lists, the word set of each name, the names
in use, the licences whose name lacks their grant and the IDs folded to
upper case depend on the rows alone, so :class:`NameIndex` holds them for as
long as the rows stand (``licenseid.dbcache.TableCache.name_index`` drops it
with them). Everything in it is immutable, so threads share one.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import NamedTuple

from licenseid.plusoperator import grant_stem
from licenseid.types import LicenseNameId

__all__ = ["NameIndex", "build_name_index"]

# The words that end a List name with its grant, normalised.
_GRANT_WORDS = (" only", " or later")


class NameIndex(NamedTuple):
    """The names of the List in the order of *rows*, which are the rows of
    ``names_and_ids()`` itself: position *i* of every field is row *i*."""

    rows: list[LicenseNameId]
    ids: tuple[str, ...]  # norm_license_id of each row
    names: tuple[str, ...]  # norm_name of each row
    words: tuple[frozenset[str], ...]  # the words of each name
    live_names: frozenset[str]  # the names of the rows in use
    upper_ids: Mapping[str, tuple[int, ...]]  # positions by ID, ASCII upper case
    left_out: Mapping[frozenset[str], frozenset[str]]  # see _grant_left_out


def build_name_index(rows: list[LicenseNameId]) -> NameIndex:
    """The :class:`NameIndex` of *rows*."""
    upper: dict[str, list[int]] = {}
    for position, row in enumerate(rows):
        upper.setdefault(row["norm_license_id"].upper(), []).append(position)
    return NameIndex(
        rows,
        tuple(row["norm_license_id"] for row in rows),
        tuple(row["norm_name"] for row in rows),
        tuple(frozenset(row["norm_name"].split()) for row in rows),
        frozenset(row["norm_name"] for row in rows if not row["is_deprecated"]),
        MappingProxyType({key: tuple(found) for key, found in upper.items()}),
        MappingProxyType(_grant_left_out(rows)),
    )


def _grant_left_out(rows: list[LicenseNameId]) -> dict[frozenset[str], frozenset[str]]:
    """The licences (plusoperator.grant_stem) that have both an -only and an
    -or-later row in use whose name is a set of words and its grant, by that
    set: "GNU General Public License v2.0" is GPL-2.0-only's name without
    "only", and GPL-2.0-or-later's without "or later". The caller needs every
    other word to be there ("GNU Affero General Public License" states no
    version), and both grants, or the guess could not be the one decided."""
    grants: dict[frozenset[str], dict[str, set[str]]] = {}
    for row in rows:
        name = row["norm_name"]
        stem = grant_stem(row["license_id"])
        if row["is_deprecated"] or stem == row["license_id"]:
            continue
        for grant in _GRANT_WORDS:
            if name.endswith(grant):
                for spelling in _spellings(name[: -len(grant)]):
                    grants.setdefault(spelling, {}).setdefault(stem, set()).add(grant)
    return {
        spelling: frozenset(
            stem for stem, found in stems.items() if len(found) == len(_GRANT_WORDS)
        )
        for spelling, stems in grants.items()
    }


def _spellings(name: str) -> list[frozenset[str]]:
    """The word sets that state *name* (a List name without its grant): its
    words, and without a last "0" after "vN", where "GNU General Public
    License v3" is "v3.0" (the rule PR #168 set for "v2.0")."""
    words = name.split()
    spelled = [frozenset(words)]
    if len(words) > 1 and words[-1] == "0" and _is_v_number(words[-2]):
        spelled.append(frozenset(words[:-1]))
    return spelled


def _is_v_number(word: str) -> bool:
    """Whether *word* is "v" and digits (``v3``)."""
    return word.startswith("v") and word[1:].isdigit()

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The other names a licence is known by, read as that licence.

Some declared values name a BSD licence by a name that is neither its ID nor
its List name: ``New BSD``, ``Simplified BSD``, ``3-clause BSD``, ``BSD-3``.
Each word of such a name comes from the List or the Open Source Initiative
(OSI):

- the List names the licences ``BSD 3-Clause "New" or "Revised" License``
  and ``BSD 2-Clause "Simplified" License``: ``New``, ``Revised`` and
  ``Simplified`` are its own words;
- the OSI says BSD-3-Clause "has also been called" the ``New BSD License``
  or ``Modified BSD License``, and BSD-2-Clause the ``Simplified BSD
  License``; it titles them ``The 3-Clause BSD License`` and ``The 2-Clause
  BSD License`` (https://opensource.org/license/bsd-3-clause,
  https://opensource.org/license/bsd-2-clause, read 2026-11-06);
- ``BSD-3`` and ``BSD3`` are the ID with ``Clause`` left out: the number of
  a BSD ID counts its clauses; ``Two-clause BSD`` spells the OSI's number
  out, as a project in the sample does.

``Modified`` is the OSI's word only: no List name has it. The List's ``BSD
3-Clause Modification`` and ``BSD Mark Modifications License`` are other
licences, which ``Modified BSD`` does not name. An ``alias_name`` step cites
the SPDX List for the ID it reads, not for the alias, which the List does
not record.

The names are data, decided once here, as the titles are
(:mod:`licenseid.resolvetitle`): a name is read only if this table holds it,
never by a looser match. Each is one the PyPI sample declares
(``tools/pypi_licence_sample``), with a final ``License`` or ``licence``
read by the prose rule P1 (:mod:`licenseid.resolveprose`), so ``New BSD
License`` is ``New BSD``. ``tests/test_resolver_alias.py`` checks each
against the List.

Not here, on purpose: a name that states no clause count (``BSD``, ``BSD
License``, ``BSD-style``), which the trove table reads as no licence;
``FreeBSD``, which the OSI uses for BSD-2-Clause but the List for
``FreeBSD-DOC`` and the deprecated ``BSD-2-Clause-FreeBSD``; and any
spelling no project declares (``BSD 2``, ``BSD 4``).

Case does not matter, in ASCII only; white space does, as in a List name.
"""

from typing import Final

from licenseid.listlookup import ListLookup
from licenseid.resolveleaf import Found
from licenseid.resolvetable import read_by_table

_KIND: Final = "alias_name"

#: The names, folded (:func:`licenseid.listlookup.fold_case`), and the ID
#: each names.
ALIASES: Final[dict[str, str]] = {
    "2-clause bsd": "BSD-2-Clause",  # OSI
    "3-clause bsd": "BSD-3-Clause",  # OSI
    "bsd 3": "BSD-3-Clause",  # the ID, "Clause" left out
    "bsd-3": "BSD-3-Clause",
    "bsd3": "BSD-3-Clause",
    "modified bsd": "BSD-3-Clause",  # OSI
    "new bsd": "BSD-3-Clause",  # the List and the OSI
    "revised bsd": "BSD-3-Clause",  # the List
    "simplified bsd": "BSD-2-Clause",  # the List and the OSI
    "two-clause bsd": "BSD-2-Clause",  # the sample: the OSI's, spelt out
}


def read_alias(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a value no leaf, compound, trove or title reader reads,
    as another name of a licence into *found*: an ``alias_name`` step to the
    ID of the table, then the steps of that ID read alone. False if *text*
    is no name of the table or the list lacks its ID."""
    return read_by_table(db, text, ALIASES, _KIND, found)

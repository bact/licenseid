# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The title a licence's own text gives itself, read as that licence.

Some declared values are neither an ID nor a List name but the heading of
the licence text: ``CC0 1.0 Universal`` (the List names it ``Creative
Commons Zero v1.0 Universal``), ``Mulan PSL v2`` (the short name the Mulan
text defines for itself) and the title line of the GNU GPL version 3. Each
is as certain as a List name: the licence's own text writes it.

The titles are data, decided once here, as the trove names are
(:mod:`licenseid.trovenames`): a title is read only if this table holds it,
never by a looser match. Each entry is one the PyPI sample declares
(``tools/pypi_licence_sample``); ``tests/test_resolver_title.py`` checks that
the text of each of its IDs writes the title. A title that writes a version
but no grant (the GPL title line) is the bare deprecated ID, read as the
author's own ID would be (decision P49 of the 0.7.0 review): ``GPL-3.0``,
``assumed_only``, with both candidates.

A title that writes no version is not here (decision P47: the List today is
not what the value says), with one exception: ``CC0``, the name the CC0 text
gives itself apart from its version, is ``CC0-1.0``, the only CC0 (the
maintainer, 2026-11-05). The UPL trove name is the other exception, in
:mod:`licenseid.trovenames`.

Case does not matter, as for a List name; white space does.
"""

from typing import Final

from licenseid.listlookup import ListLookup
from licenseid.resolveleaf import Found, read_leaf
from licenseid.resolvertypes import step
from licenseid.resolvetrove import copy_reading

_KIND: Final = "text_title"

#: The titles, folded (``str.casefold``), and the ID each names.
TITLES: Final[dict[str, str]] = {
    "cc0": "CC0-1.0",  # no version: an exception to P47
    "cc0 1.0 universal": "CC0-1.0",
    "gnu general public license version 3, 29 june 2007": "GPL-3.0",
    "mulan psl v2": "MulanPSL-2.0",
}


def read_title(db: ListLookup, text: str, found: Found) -> bool:
    """Read *text*, a value no leaf, compound or trove reader reads, as the
    title of a licence text into *found*: a ``text_title`` step to the ID of
    the table, then the steps of that ID read alone. False if *text* is no
    title of the table or the list lacks its ID."""
    license_id = TITLES.get(text.casefold())
    if license_id is None:
        return False
    reading = Found()
    if not read_leaf(db, license_id, reading):
        return False  # the list read lacks the ID
    found.steps = [step(_KIND, True, text, license_id), *reading.steps]
    copy_reading(found, reading)
    return True

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag whose expression is cut by a dash or ``_`` gets no answer (item 54).

``SPDX-License-Identifier: MIT-`` was read as ``MIT``, ``EXACT=true``,
because the tag reader ends the expression at the first token no operator
bridges. A dash or ``_`` that touches the end of the expression and is followed
by the end of the value, white space, a ``.``, a ``,`` or a ``+`` is a cut
value, as the same value is as an argument. A dash followed by anything else
may start a comment closer (``MIT-->``) and is left to the reader as before.
The rows were pinned on ``main`` first (``# BUG: (item 54)``) and flipped.
A ``license`` field and ``license_id`` are read by ``resolve()`` first and
were refused already (``tests/test_cut_versions.py``).
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.dropguard import cut_by_joiners

TAG = "SPDX-License-Identifier: "

#: Lines refused now; each was read (``MIT-`` as ``MIT``, ``EXACT=true``,
#: ``METHOD=tag``). # BUG: (item 54) in the git history of this table.
REFUSED = [
    TAG + "MIT-",
    TAG + "GPL-2.0-",
    TAG + "Apache-2.0-",
    TAG + "MIT_",
    TAG + "MIT--",
    TAG + "MIT-.",
    TAG + "MIT- text",
    TAG + "MIT-\t",
    TAG + "MIT- OR ISC",
    TAG + "MIT OR ISC-",
    TAG + "(MIT)-",
    TAG + "(MIT OR ISC)-",
    TAG + "MIT+-",
    TAG + "MIT-+",
    TAG + "MIT\u2013",
    TAG + "GPL-2.0-only-",
    TAG + "GPL-2.0 or later-",
    TAG + "BSD-3-Clause-",
    TAG + "MIT-0-",
    TAG + "LicenseRef-a_",
    TAG + '"MIT-"',
    TAG + "'MIT-'",
    TAG + "MIT-;",
    TAG + "MIT-)",
    TAG + "MIT-?",
    TAG + "MIT WITH Classpath-exception-2.0-",
    "/* " + TAG + "MIT- */",
    "# " + TAG + "MIT-",
    "// " + TAG + "MIT-",
    "-- " + TAG + "MIT-",
    "# " + TAG + "MIT- \n",
    TAG + "MIT-\r\n",
]

#: ``line: expression`` answered before and after: a comment closer, a spaced
#: dash, an ending, a reference, no tag at all.
STAYS: dict[str, str] = {
    TAG + "MIT": "MIT",
    TAG + "MIT.": "MIT",
    TAG + "MIT -": "MIT",
    TAG + "MIT - some text": "MIT",
    TAG + "MIT -- text": "MIT",
    TAG + "MIT -text": "MIT",
    TAG + "MIT-->": "MIT",
    TAG + "MIT--> ": "MIT",
    TAG + "MIT -->": "MIT",
    TAG + "MIT*/": "MIT",
    TAG + "MIT-0": "MIT-0",
    # a reference takes the dashes at its end, as ``resolve()`` reads it
    TAG + "LicenseRef-a-": "LicenseRef-a-",
    TAG + "LicenseRef-a.-": "LicenseRef-a.-",
    TAG + "DocumentRef-x:LicenseRef-a-": "DocumentRef-x:LicenseRef-a-",
    # a grant follows: its own reader, as for an argument
    TAG + "GPL-2.0_ or later": "GPL-2.0-or-later",
    TAG + "GPL-2.0- or later": "GPL-2.0-or-later",
    TAG + "MIT_ or later": "MIT+",
    TAG + "GPL-2.0-only": "GPL-2.0-only",
    "<!-- " + TAG + "MIT-->": "MIT",
    "<!-- " + TAG + "MIT -->": "MIT",
    "/* " + TAG + "MIT */": "MIT",
    "-- " + TAG + "MIT": "MIT",
    "// " + TAG + "MIT -": "MIT",
    "# " + TAG + "MIT\n# next line": "MIT",
    "{# " + TAG + "MIT #}": "MIT",
    # A dash glued to what follows may start a comment closer (``MIT-->``):
    # the tag reader knows no closers, so these keep their reading
    TAG + "MIT-*/": "MIT",
    TAG + "MIT-/": "MIT",
    TAG + "MIT-}": "MIT",  # Haskell
    TAG + "MIT--]]": "MIT",  # Lua
    "{# " + TAG + "MIT-#}": "MIT",
}


def _found(db: LicenseDatabase, text: str) -> list[tuple[str, str]]:
    found = LicenseDetector(db.location).detect(text=text)
    return [(d["expression"], d["method"]) for d in found]


@pytest.mark.parametrize("line", REFUSED, ids=lambda v: repr(v[-24:]))
def test_a_cut_tag_gets_no_answer(corpus_db: LicenseDatabase, line: str) -> None:
    assert _found(corpus_db, line) == []


@pytest.mark.parametrize("line", sorted(STAYS), ids=lambda v: repr(v[-24:]))
def test_an_uncut_tag_is_read(corpus_db: LicenseDatabase, line: str) -> None:
    assert _found(corpus_db, line)[:1] == [(STAYS[line], "tag")]


def test_a_cut_tag_does_not_hide_the_next_tag(corpus_db: LicenseDatabase) -> None:
    both = TAG + "MIT-\n" + TAG + "ISC"
    assert _found(corpus_db, both) == [("ISC", "tag")]


@pytest.mark.parametrize(
    ("text", "end", "expected"),
    [
        ("MIT-", 3, True),
        ("MIT_", 3, True),
        ("MIT--", 3, True),
        ("MIT\u2013", 3, True),
        ("MIT- OR ISC", 3, True),
        ("MIT-.", 3, True),
        ("MIT-,", 3, True),
        ("MIT-+", 3, True),
        ("MIT-->", 3, False),  # a comment closer may start here
        ("MIT-*/", 3, False),
        ("MIT -", 3, False),  # white space: the dash is the author's
        ("MIT", 3, False),
        ("MIT.", 3, False),
        ("MIT-0", 3, False),
        ("-", 0, False),
        ("", 0, False),
    ],
)
def test_cut_by_joiners(text: str, end: int, expected: bool) -> None:
    assert cut_by_joiners(text, end) is expected

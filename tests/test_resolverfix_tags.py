# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Two readings of an ``SPDX-License-Identifier`` tag (task ``resolverfix``,
item 8): an "or later" grant after an ID that states its qualifier already,
and an ID cut at a character the SPDX idstring has not (``LicenseRef-café``).

Every entry point's answer (API, ``is_spdx``, CLI ``detect`` and
``is-spdx``): no licence for (a), as the maintainer decided on 2026-11-02,
and for (b), the narrowest rule that never answers a cut ID."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from spdx_tag_helpers import Answers, answers, tag_db


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_resolverfix_tags")


def named(expression: str) -> Answers:
    """Every entry point answers *expression*, an SPDX expression."""
    return Answers(expression, True, expression, True)


def reference(expression: str) -> Answers:
    """Every entry point answers *expression*, which holds a ``LicenseRef-*``:
    not on the List, so not SPDX for ``is-spdx`` (``is_spdx`` says no)."""
    return Answers(expression, False, expression, False)


#: No entry point answers.
NOTHING = Answers(None, None, None, False)

#: (a) An "or later" grant after ``-only`` or ``-or-later``: a qualifier
#: stated twice, which ``match()`` refuses. Each was read before: as the ID
#: alone, or as the OR of the ID and a licence ``later``.
TWICE = [
    "GPL-2.0-only or (at your option) any later version",
    "GPL-2.0-or-later or any later version",
    "GPL-2.0-only or later",
    "GPL-2.0-or-later or later",
    "gpl-2.0-ONLY or later",
    "(GPL-2.0-only) or later",
    "GPL-2.0-only WITH Classpath-exception-2.0 or later",
    "MIT OR GPL-2.0-only or later",
    "GPL-2.0-only or, at your option, any later version",
]

#: (b) An ID cut at a character outside the idstring grammar (ASCII
#: letters, digits, ``.`` and ``-``). Each answered the ID as cut before.
CUT = [
    "LicenseRef-caf\u00e9",
    "MIT OR LicenseRef-caf\u00e9",
    "LicenseRef-caf\u00e9-x OR MIT",
    "LicenseRef-a-\u00e4",
    "LicenseRef-cafe\u0301",  # a combining mark
    "MIT\u00e9",
    "MIT.\u00e9",
    "LicenseRef-\u00e4",  # no answer before either
    "MIT WITH Classpath-exception-2.0\u00e9",
    "MIT\u0661",  # a digit of another script
]

#: Tag answers that stay as they are.
STAYS: dict[str, Answers] = {
    "GPL-2.0 or later": named("GPL-2.0-or-later"),
    "GPL-2.0-only": named("GPL-2.0-only"),
    "GPL-2.0-or-later": named("GPL-2.0-or-later"),
    "GPL-2.0-only OR MIT": named("GPL-2.0-only OR MIT"),
    "GPL-2.0-only OR LGPL-2.1 or later": named("GPL-2.0-only OR LGPL-2.1-or-later"),
    "GPL-2.0-only OR GPL-2.0 or later": named("GPL-2.0-only OR GPL-2.0-or-later"),
    "GPL-2.0-only, see COPYING for any later version": named("GPL-2.0-only"),
    # A word after a space, or a mark that is no letter, ends the expression,
    # as prose and code after a tag do (``MIT, with additions``).
    "LicenseRef-a b": reference("LicenseRef-a"),
    "LicenseRef-caf \u00e9": reference("LicenseRef-caf"),
    "MIT\u20ac": named("MIT"),
    "MIT_": named("MIT"),
    "MIT*": named("MIT"),
    "(MIT)\u00e9": named("MIT"),
    "MIT+\u00e9": named("MIT+"),
    "Apache-2.0: see NOTICE": named("Apache-2.0"),
}


@pytest.mark.parametrize("tag", TWICE + CUT, ids=ascii)
def test_tag_names_nothing(db: str, tag: str, tmp_path: Path) -> None:
    assert answers(db, tag, tmp_path) == NOTHING


@pytest.mark.parametrize("tag", list(STAYS), ids=ascii)
def test_tag(db: str, tag: str, tmp_path: Path) -> None:
    assert answers(db, tag, tmp_path) == STAYS[tag]

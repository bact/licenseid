# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``resolve()`` does with a character the loose reading drops (task T6).

A loose ID ("Apache 2.0", "Apache_2.0") is read by dropping the characters
that are neither letters nor digits. Some of those carry the author's doubt
("Apache 2.0?") or a decoding error (U+FFFD): reading past them asserts what
the author did not write. These cases pin the answers of 0.6.0 for every
class of dropped character, so the change that refuses them shows exactly
what it moved.
"""

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: Characters the loose reading may drop silently: white space, "-", "_",
#: ".", a Unicode dash (Pd) and one trailing ",".
KEPT = [
    ("Apache 2.0", "Apache-2.0", "separator"),
    ("Apache_2.0", "Apache-2.0", "separator"),
    ("Apache  2.0", "Apache-2.0", "separator"),
    ("Apache–2.0", "Apache-2.0", "separator"),  # en dash
    ("Apache—2.0", "Apache-2.0", "separator"),  # em dash
    ("Apache‐2.0", "Apache-2.0", "separator"),  # hyphen U+2010
    ("Apache 2.0.", "Apache-2.0", "separator"),
    ("MIT..", "MIT", "separator"),
    ("MIT,", "MIT", "separator"),
    ("Apache 2.0,", "Apache-2.0", "separator"),
]

#: Not read through the loose path: a listed name keeps its "!", a grant
#: reads its own tail.
UNTOUCHED = [
    ("Yahoo! Public License v1.0", "YPL-1.0", "listed_name"),
    ("MIT License", "MIT", "listed_name"),
    ("GPLv2 or later.", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later!", "GPL-2.0-or-later", "version_spelling"),
    ("GPL-3.0 (or later)", "GPL-3.0-or-later", "stated_qualifier"),
]

#: Characters that are dropped today and carry no separator. One per class:
#: punctuation, symbols, quotes (straight and curly), a second comma, the
#: replacement character.
DROPPED = [
    ("Apache 2.0?", "Apache-2.0"),
    ("Apache 2.0!", "Apache-2.0"),
    ("Apache2?", "Apache-2.0"),
    ("MIT?", "MIT"),
    ("mit?", "MIT"),
    ("MIT*", "MIT"),
    ("#MIT", "MIT"),
    ('MIT"', "MIT"),
    ('"MIT"', "MIT"),
    ("'MIT'", "MIT"),
    ("`MIT`", "MIT"),
    ("“MIT”", "MIT"),
    ("MIT,,", "MIT"),
    ("MIT;", "MIT"),
    ("MIT:", "MIT"),
    ("MIT/", "MIT"),
    ("MIT\\", "MIT"),
    ("MIT|", "MIT"),
    ("MIT~", "MIT"),
    ("MIT@", "MIT"),
    ("MIT$", "MIT"),
    ("MIT%", "MIT"),
    ("MIT^", "MIT"),
    ("MIT&", "MIT"),
    ("MIT=", "MIT"),
    ("MIT<", "MIT"),
    ("MIT>", "MIT"),
    ("MIT™", "MIT"),  # trade mark sign
    ("MIT★", "MIT"),  # black star
    ("MIT·", "MIT"),  # middle dot
    ("MIT�", "MIT"),
    ("BSD 3-Clause!", "BSD-3-Clause"),
]


def _ids(rows: list[tuple[str, ...]]) -> list[str]:
    return [ascii(row[0])[:36] for row in rows]


@pytest.mark.parametrize(("value", "expression", "category"), KEPT, ids=_ids(KEPT))
def test_an_allowed_dropped_character_is_read(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    """White space, "-", "_", ".", a dash and a trailing comma are dropped."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)


@pytest.mark.parametrize(
    ("value", "expression", "category"), UNTOUCHED, ids=_ids(UNTOUCHED)
)
def test_a_name_and_a_grant_are_not_read_by_dropping(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    """A listed name and the tail of a grant never reach the loose reading's
    dropped characters."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)


# BUG: T6 (dropguard) refuses these; 0.6.0 reads the licence past the dropped
# character, and so its category is `separator`, `version_spelling` or a
# deprecation one, with the licence as the expression.
@pytest.mark.parametrize(("value", "wrong"), DROPPED, ids=_ids(DROPPED))
def test_bug_a_dropped_character_is_read_as_a_licence(
    corpus_db: LicenseDatabase, value: str, wrong: str
) -> None:
    """Pins today's wrong answer; T6 flips it."""
    got = resolve(value, corpus_db)
    assert got["expression"] == wrong
    assert got["category"] in ("separator", "version_spelling")

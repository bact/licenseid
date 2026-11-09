# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the BSD alias reader (``licenseid.resolvealias``: another
name a BSD licence is known by) moved in the parity corpus and the PyPI
sample, grouped by where the name comes from.

The answers are in ``fixtures/resolver_aliases_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`ALIASES_CHANGES` into ``EXPECTED_CHANGES`` last.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_aliases_changes.tsv"

_WAS = "it was `unresolved`, `not found`"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "list": (
        "a word the List's own name of the licence quotes (`BSD 3-Clause"
        ' "New" or "Revised" License`, `BSD 2-Clause "Simplified" License`)'
        f" names it (`alias_name`, `resolver_rule`); {_WAS}"
    ),
    "osi": (
        "the OSI's other name of the licence (`Modified BSD License`, `3-clause"
        f" BSD License`) names it (`alias_name`, `resolver_rule`); {_WAS}"
    ),
    "id": (
        "the ID with `Clause` left out, its number the clause count, names it"
        f" (`alias_name`, `resolver_rule`); {_WAS}"
    ),
}

#: ``{value: (answer, reason)}``, every value the alias reader moves.
ALIASES_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

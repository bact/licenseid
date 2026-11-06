# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the title reader (``licenseid.resolvetitle``: the title a
licence's own text gives itself) and the UPL trove name moved in the parity
corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_titles_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`TITLES_CHANGES` into ``EXPECTED_CHANGES`` last.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_titles_changes.tsv"

_WAS = "it was `unresolved`, `not found`"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "title": (
        "the title the licence's own text gives itself is read as that"
        f" licence (`text_title`, `resolver_rule`); {_WAS}"
    ),
    "bare": (
        "the GPL v3 title line writes a version and no grant: the bare"
        " deprecated ID, `assumed_only` with both candidates, never narrowed"
        f" (P49), after a `text_title` step; {_WAS}"
    ),
    "upl": (
        "the UPL trove name writes no version, but UPL-1.0 is the only UPL:"
        " read as it (`trove_name`), an exception to P47 the maintainer made"
        f" on 2026-11-05; {_WAS}"
    ),
}

#: ``{value: (answer, reason)}``, every value the title reader moves.
TITLES_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

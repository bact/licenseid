# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task T8 (the prose forms of one ID, rules P1 to P3) moved in
the parity corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_t8_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`T8_CHANGES` into ``EXPECTED_CHANGES``.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_t8_changes.tsv"

_WAS = "T9 answered `unresolved`"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "word": (
        "T8 (P1): a final `license` or `licence` after a value that reads"
        " alone is dropped (`prose_form`, `resolver_rule`); the rest keeps"
        f" its own steps; {_WAS}"
    ),
    "version": (
        "T8 (P2): `<name> License[,] (Version|v) N` is read as `<name> N`,"
        " through the loose key, to the one ID with that number"
        f" (`prose_form`); {_WAS}"
    ),
    "article": (
        f"T8 (P3): a leading `The` with P1 or a listed name (`prose_form`); {_WAS}"
    ),
    "trailing": (
        "T8 (P3, P58): the head is a prose form and the parenthesis is the"
        " same expression, so the parenthesis is dropped (`trailing_name`,"
        f" then `prose_form`); {_WAS}"
    ),
}

#: ``{value: (answer, reason)}``, every value T8 moves.
T8_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

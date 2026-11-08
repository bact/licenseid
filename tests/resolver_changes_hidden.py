# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the hidden-character rule (``licenseid.hiddenchars``) moved in
the parity corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_hidden_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`HIDDEN_CHANGES` into ``EXPECTED_CHANGES`` last.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_hidden_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "hidden": (
        "a control or format character at an end of the value is left off"
        " (`trim`, detail `invisible characters`, `separator`,"
        " `resolver_rule`); it was refused (`control or format character`)"
    ),
}

#: ``{value: (answer, reason)}``, every value the rule moves.
HIDDEN_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

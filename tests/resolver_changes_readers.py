# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the readers ``detect()`` and ``resolve()`` share (0.7.0
review) moved in the parity corpus and the PyPI sample, grouped
by the rule.

The answers are in ``fixtures/resolver_readers_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`READERS_CHANGES` into ``EXPECTED_CHANGES`` last.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_readers_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "spaced-plus": (
        'a "+" after a space is no operator'
        ' (plusoperator.PLUS_OPERATOR) and may say "and": malformed,'
        " `plus after a space`; it was read as the operator with a"
        " `whitespace` step. No PyPI sample value has one"
    ),
}

#: ``{value: (answer, reason)}``, every value the shared readers move.
READERS_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

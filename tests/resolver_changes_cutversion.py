# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers a cut ID moved in the parity corpus and the PyPI sample (roadmap
item 54: a bare major the List has another minor of, a dash joined to the end).

The answers are in ``fixtures/resolver_cutversion_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`CUTVERSION_CHANGES` into ``EXPECTED_CHANGES``.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_cutversion_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "cut": (
        "`LGPLv2` writes only the major: the List has `LGPL-2.0` and"
        " `LGPL-2.1`, so it names none and is refused with the IDs it may mean"
        " (`version ambiguous`); it was `LGPL-2.0`, `assumed_only`. `LGPLv2+`"
        " stays: a grant covers every later minor"
    ),
}

#: ``{value: (answer, reason)}``, every value the item moves.
CUTVERSION_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

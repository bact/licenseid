# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the pre-freeze contract batch moved in the parity corpus and
the PyPI sample: item P5, a reason for every refusal. Each value gains a
``reason`` and nothing else: no expression, category, step or trust moved.

The answers are in ``fixtures/resolver_contract_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`CONTRACT_CHANGES` into ``EXPECTED_CHANGES`` last, so a value an
earlier task moved (``BSD-3-Clause and Public-Domain``, T7) is listed here
with its answer now.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_contract_changes.tsv"

_WAS = "the refusal had no reason"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "not_found": (
        "P5: a value no reader reads says so, `not found: <value>`, once every"
        f" reader has declined it (resolvereason.no_reading); {_WAS}"
    ),
    "exception": (
        "P5: `X WITH Y` whose licence reads and whose exception is not on the"
        f" List says `exception not found: Y`; {_WAS}"
    ),
    "qualifier": (
        "P5: a qualifier stated twice (`GPL-2.0-only+`) is malformed with the"
        " reason `qualifier stated twice: <leaf>`, which an operand now gives"
        " the compound, as any operand's own reason does (P29); it said"
        " `operand not resolved: GPL-2.0-only+`"
    ),
}

#: ``{value: (answer, reason)}``, every value the batch moves.
CONTRACT_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

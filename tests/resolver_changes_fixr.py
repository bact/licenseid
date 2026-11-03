# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task ``fixr`` (the reasons and readings of ``match()`` found
in the 0.7.0 review) moved in the parity corpus and the PyPI sample,
grouped by the rule.

The answers are in ``fixtures/resolver_fixr_changes.tsv``; :data:`REASONS`
says why each group moved. ``resolver_corpus`` merges :data:`FIXR_CHANGES`
into ``EXPECTED_CHANGES`` last: each value here was listed by an earlier
task, with the answer it gave then.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_fixr_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "with-words": (
        "fixr item 2: `exception not found` names one word after WITH;"
        " several words after it (`LLVM exception`, or a listed exception"
        " and more: `Classpath-exception-2.0 or something`) are no exception"
        " ID, so the value is `not found`"
    ),
}

#: ``{value: (answer, reason)}``, every value the task moves.
FIXR_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task ``resolverfix`` (edge values of ``match()`` found in the
0.7.0 review) moved in the parity corpus and the PyPI sample, grouped by
the rule.

The answers are in ``fixtures/resolver_resolverfix_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`RESOLVERFIX_CHANGES` into ``EXPECTED_CHANGES`` after
``CONTRACT_CHANGES``: each value here was listed by an earlier task, with
the answer it gave then.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_resolverfix_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "surrogate": (
        "resolverfix item 6: the result's `input` holds U+FFFD for each"
        " surrogate code point, so that `json_line` (RFC 8785) can write it;"
        " the value is refused as before (`lone surrogate`)"
    ),
    "semicolon": (
        "resolverfix item 2: a reason keeps the `;` of the input"
        " (`errors.reason_detail`); it was made `,`, as on a diagnostic line,"
        " where a `;` would start the ACTION"
    ),
    "ending": (
        "resolverfix review item 6: one end mark after a value no reader read"
        " with it (brackets, a trove name or path, a listed name) is an"
        " ending, read without it as a `separator` step, as after an ID"
    ),
}

#: ``{value: (answer, reason)}``, every value the task moves.
RESOLVERFIX_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

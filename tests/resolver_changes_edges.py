# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the edge values of ``resolve()`` found in the 0.7.0 review
moved in the parity corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_edges_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`EDGES_CHANGES` into ``EXPECTED_CHANGES`` after
``REFUSALS_CHANGES``: each value here was listed by an earlier change,
with the answer it gave then.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_edges_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "surrogate": (
        "the result's `input` holds U+FFFD for each"
        " surrogate code point, so that `json_line` (RFC 8785) can write it;"
        " the value is refused as before (`lone surrogate`)"
    ),
    "semicolon": (
        "a reason keeps the `;` of the input"
        " (`errors.reason_detail`); it was made `,`, as on a diagnostic line,"
        " where a `;` would start the ACTION"
    ),
    "ending": (
        "one end mark after a value no reader read"
        " with it (brackets, a trove name or path, a listed name) is an"
        " ending, read without it as a `separator` step, as after an ID"
    ),
}

#: ``{value: (answer, reason)}``, every value the edge values move.
EDGES_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

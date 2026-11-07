# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the versioned-name rule (``licenseid.resolveprose``: a name
with a version and no word ``License``, a version in brackets, and the names
of ``VERSIONED_NAMES``) moved in the parity corpus and the PyPI sample.

The answers are in ``fixtures/resolver_versioned_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`VERSIONED_CHANGES` into ``EXPECTED_CHANGES``.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_versioned_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "versioned": (
        "a name with a version is one rule (P2): `Apache Version 2.0` as"
        " `Apache 2`, a version in brackets as `, Version N`, and"
        " `Apache Software License` with a version as `Apache N`; each"
        " reduction must read as a listed ID (`prose_form`,"
        " `resolver_rule`); it was `unresolved`, `not found`"
    ),
}

#: ``{value: (answer, reason)}``, every value the rule moves.
VERSIONED_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

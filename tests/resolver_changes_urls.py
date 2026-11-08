# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers the licence URL reader (``licenseid.resolveurl``) moved in the
parity corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_urls_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`URLS_CHANGES` into ``EXPECTED_CHANGES`` last.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_urls_changes.tsv"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "urls": (
        "a licence URL is read as its licence (`license_url`, `resolver_rule`):"
        " the URL is one the List gives the licence, or an alias the survey"
        " accepted (`mit-license.php`); it was `unresolved`, `not found`"
    ),
}

#: ``{value: (answer, reason)}``, every value the URL reader moves.
URLS_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The answers task T9 (trove names and paths, an agreeing trailing name)
moved in the parity corpus and the PyPI sample, grouped by the rule.

The answers are in ``fixtures/resolver_t9_changes.tsv``;
:data:`REASONS` says why each group moved. ``resolver_corpus`` merges
:data:`T9_CHANGES` into ``EXPECTED_CHANGES``.
"""

from pathlib import Path

from changes_file import load_changes

from tools.pypi_licence_sample.answer import Answer

CHANGES_FILE = Path(__file__).parent / "fixtures" / "resolver_t9_changes.tsv"

_WAS = "0.6.0 answered `unresolved`"

#: Why each group of the changes file moved.
REASONS: dict[str, str] = {
    "stated": (
        "T9 (T2): a name of the trove table that states one licence is read"
        f" as that ID (`trove_name`, `resolver_rule`); {_WAS}"
    ),
    "assumed": (
        "T9 (T2, Q23): a trove name that writes a version but not `-only` or"
        " `-or-later` is the bare deprecated ID, `assumed_only` with both"
        f" candidates, never narrowed; {_WAS}"
    ),
    "path": (
        "T9 (T1): a `License :: ...` classifier in its real form is read as"
        " its name is read alone, plus a `trove_path` step (`lexical`);"
        f" {_WAS}"
    ),
    "trailing": (
        "T9 (T3, P63): the head and the parenthesis are one expression (read"
        " before the trove table), so the"
        " parenthesis is dropped (`trailing_name`, `lexical`) and the answer"
        f" is the head's; {_WAS}"
    ),
}

#: ``{value: (answer, reason)}``, every value T9 moves.
T9_CHANGES: dict[str, tuple[Answer, str]] = load_changes(CHANGES_FILE, REASONS)

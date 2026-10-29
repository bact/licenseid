# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Read a file of answers a task moved (``fixtures/resolver_t*_changes.tsv``):
one row a value, with the group whose reason says why it moved."""

from pathlib import Path

from tools.pypi_licence_sample.answer import (
    ANSWER_COLUMNS,
    Answer,
    answer_from_row,
    unescape_field,
)


def load_changes(path: Path, reasons: dict[str, str]) -> dict[str, tuple[Answer, str]]:
    """The rows of *path* as ``{value: (answer, reason)}``, each with the
    reason of its group in *reasons*. Comment lines start with ``#``; the
    first other line is the header."""
    changes: dict[str, tuple[Answer, str]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [line.split("\t") for line in lines if not line.startswith("#")]
    for value, group, *fields in rows[1:]:
        row = dict(zip(ANSWER_COLUMNS, fields, strict=True))
        changes[unescape_field(value)] = (answer_from_row(row), reasons[group])
    return changes

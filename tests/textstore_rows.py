# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The stored form of a corpus read back with no database: the checks
``update`` writes beside the rows (:func:`checks_of`) and the corpus a lookup
reads from them (:func:`read_back`), as ``licenseid.textentries`` composes
``textstore.read_head`` and ``textstore.read_entry``."""

from collections.abc import Iterable, Mapping

from licenseid.textcorpus import TextCorpus, TextRow, core_of_row, group_rows
from licenseid.textstore import (
    ENTRY_KINDS,
    HEAD,
    HEAD_KINDS,
    RawEntry,
    entry_check,
    head_digest,
    read_entry,
    read_head,
)

#: The ``last_update_datetime`` the rows are written with.
UPDATED = "2026-11-27T00:00:00+00:00"
Stored = Iterable[tuple[object, object, object]]


def _bodies(stored: Stored) -> dict[tuple[object, object], object]:
    return {(kind, owner): body for kind, owner, body in stored}


def _raw(
    name: str,
    row: TextRow,
    bodies: Mapping[tuple[object, object], object],
    check: object,
) -> RawEntry:
    return RawEntry(
        name,
        row.text,
        core_of_row(row),
        {kind: bodies[(kind, name)] for kind in ENTRY_KINDS if (kind, name) in bodies},
        check,
    )


def checks_of(
    rows: Iterable[TextRow], stored: Stored, updated: str = UPDATED
) -> dict[str, str]:
    """The checks of the head and of each entry of *stored*, the codes of
    *rows*, written with *updated*."""
    bodies = _bodies(stored)
    head = head_digest(
        updated,
        {
            kind: str(bodies[(kind, HEAD)])
            for kind in HEAD_KINDS
            if (kind, HEAD) in bodies
        },
    )
    first, _ = group_rows(rows)
    checks = {HEAD: head}
    for name, row in first.items():
        check = entry_check(head, _raw(name, row, bodies, None))
        if check is not None:
            checks[name] = check
    return checks


def read_back(
    rows: Iterable[TextRow],
    stored: Stored,
    checks: Mapping[str, object],
    updated: object = UPDATED,
) -> TextCorpus | None:
    """The corpus a lookup reads from *stored* under *checks* for the rows
    *rows* (every entry), or None when the head or an entry fails."""
    bodies = _bodies(stored)
    head = read_head(
        updated,
        {kind: bodies[(kind, HEAD)] for kind in HEAD_KINDS if (kind, HEAD) in bodies},
        checks.get(HEAD),
    )
    if head is None:
        return None
    first, representatives = group_rows(rows)
    entries = []
    for name in sorted(first):
        entry = read_entry(head, _raw(name, first[name], bodies, checks.get(name)))
        if entry is None:
            return None
        entries.append(entry)
    return TextCorpus(head.vocabulary, tuple(entries), representatives)

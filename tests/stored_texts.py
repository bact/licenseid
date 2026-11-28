# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Helpers for the tests of the coded List texts read per candidate
(``licenseid.textentries``): the corpus of every text as the store gives it,
the corpus a lookup builds when no stored codes are used, and a count of the
builds and of the entries read."""

from collections.abc import Collection, Sequence
from typing import Any

import pytest

from licenseid import textentries
from licenseid.database import LicenseDatabase, snapshot, text_source
from licenseid.textcorpus import TextCorpus, TextRow
from licenseid.textstore import RawEntry


def all_texts(db: LicenseDatabase, ids: Collection[str] | None = None) -> TextCorpus:
    """The corpus of the texts of *ids* (default: every text of *db*), read
    as a call reads its candidates', in one transaction."""
    with snapshot(db):
        if ids is None:
            ids = list(db._tables.index_rows())  # pylint: disable=protected-access
        return text_source(db).corpus(ids)


def no_stored_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every lookup find the head of the stored codes failing its check:
    the corpus is then built in memory, without regions."""
    monkeypatch.setattr(textentries, "read_head", lambda *_: None)


class Counts:
    """The builds of a corpus in memory, and the names of the entries read,
    while a test runs."""

    def __init__(self) -> None:
        self.builds = 0
        self.read: list[str] = []


def counting(monkeypatch: pytest.MonkeyPatch) -> Counts:
    """Count the builds of a corpus in memory and the entries read."""
    seen = Counts()
    real_build = TextCorpus.build  # bound to the class: taken before the patch
    real_read = textentries.read_raw_entries

    def build(rows: Sequence[TextRow]) -> TextCorpus:
        seen.builds += 1
        return real_build(rows)

    def read(conn: Any, names: Sequence[str], *rest: Any) -> list[RawEntry]:
        seen.read.extend(names)
        return real_read(conn, names, *rest)

    monkeypatch.setattr(TextCorpus, "build", staticmethod(build))
    monkeypatch.setattr(textentries, "read_raw_entries", read)
    return seen

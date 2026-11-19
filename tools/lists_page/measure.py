# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the page measures instead of typing it: the PyPI projects that each
row of a table reads, the answer of ``resolve()`` to an example and the IDs
the List gives a URL page to.

Each runs on the corpus the tests use (the SPDX 3.29.0 List of
``tests/fixtures/license-list/`` and the sample of
``tests/fixtures/pypi_values_2026-10.tsv``), so the numbers are the same on
every machine and never read the real cache."""

import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import NamedTuple

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.listlookup import fold_case
from licenseid.resolvefirst import is_exact
from licenseid.resolveurl import page_index_key
from licenseid.trovenames import TROVE_NAMES, strip_trove_path

# isort: off
# tests/ is on sys.path only at run time (tools.golden.paths): pylint cannot
# resolve conftest and resolver_corpus.
# pylint: disable=wrong-import-order,unused-import,ungrouped-imports,import-error
from tools.golden import paths  # noqa: F401  # first: puts tests/ on sys.path

from conftest import make_memory_db_path
from resolver_corpus import corpus_db_path, read_comments, sample_files, sample_rows
from tools.pypi_licence_sample.answer import unescape_field

# isort: on

#: The step kind of each table the sample is counted for by step; the trove
#: table is counted by value (:func:`_trove_name`).
TABLES = {"alias": "alias_name", "title": "text_title", "trove": "trove_name"}
_SAMPLED = re.compile(r"(\d+) projects")


class Answer(NamedTuple):
    """What ``resolve()`` says of a value: the expression, the category,
    whether ``detect()`` calls it exact and the detail of its first step."""

    expression: str | None
    category: str
    exact: bool
    detail: str | None = None


@contextmanager
def corpus() -> Iterator[LicenseDatabase]:
    """An in-memory database of the whole List fixture."""
    for db_path in corpus_db_path("lists", make_memory_db_path):
        yield LicenseDatabase(db_path, create=False)


def answer_of(db: LicenseDatabase, value: str) -> Answer:
    """The answer of ``resolve()`` to *value*."""
    resolution = resolve(value, db)
    expression = resolution["expression"]
    steps = resolution["steps"]
    return Answer(
        expression,
        resolution["category"],
        expression is not None
        and is_exact(resolution)
        and _detected_exact(db, value, expression),
        steps[0]["detail"] if steps else None,
    )


def _detected_exact(db: LicenseDatabase, value: str, expression: str) -> bool:
    """Whether ``detect()`` gives *expression* for *value* and calls it
    exact: its one later rule makes a variant licenseid chose inexact (an
    encoded "+": ``licenses.nuget.org/GPL-2.0%2B``)."""
    results = LicenseDetector(db_path=str(db.db_path)).detect(text=value)
    return bool(results) and (
        results[0]["expression"] == expression and results[0]["exact"]
    )


def sample_size() -> tuple[int, int]:
    """The projects of the PyPI sample, and those of them with one short
    value, which the tables count."""
    header = " ".join(read_comments(sample_files()[0]))
    found = _SAMPLED.search(header)
    if found is None:
        raise ValueError("the sample header gives no number of projects")
    return int(found.group(1)), sum(int(row["projects"]) for row in sample_rows())


def _trove_name(value: str) -> str | None:
    """The classifier name *value* is, whole or alone, whatever reads it."""
    return strip_trove_path(value) or (value if value in TROVE_NAMES else None)


def list_owners(db: LicenseDatabase, key: str) -> tuple[str, ...]:
    """The IDs the List gives the page *key* to (a ``url_key``), the licences
    then the exceptions, each in List order; empty for a page the List lacks."""
    return tuple(
        owner["id"] for owner in db.get_ids_by_url(page_index_key).get(key, ())
    )


def project_counts(db: LicenseDatabase) -> dict[str, Counter[str]]:
    """The projects of the sample that each row of the tables reads, by
    table (:data:`TABLES`) and key: the folded name of an alias or a title,
    the classifier name of a trove name, read or not (a value that is the
    classifier or its name alone). A row nobody declares is absent."""
    counts: dict[str, Counter[str]] = {name: Counter() for name in TABLES}
    kinds = {kind: name for name, kind in TABLES.items() if name != "trove"}
    for row in sample_rows():
        value = unescape_field(row["value"])
        name = _trove_name(value)
        if name is not None:
            counts["trove"][name] += int(row["projects"])
        for step in resolve(value, db)["steps"]:
            table = kinds.get(step["kind"])
            if table is not None and step["applied"]:
                key = fold_case(" ".join(step["from"].split()))
                counts[table][key] += int(row["projects"])
    return counts

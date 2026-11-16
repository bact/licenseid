# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the page measures instead of typing it: the PyPI projects that each
row of a table reads, and the answer of ``resolve()`` to an example.

Both run on the corpus the tests use (the SPDX 3.29.0 List of
``tests/fixtures/license-list/`` and the sample of
``tests/fixtures/pypi_values_2026-10.tsv``), so the numbers are the same on
every machine and never read the real cache."""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import NamedTuple

from licenseid import LicenseDatabase, resolve
from licenseid.listlookup import fold_case
from licenseid.resolvefirst import is_exact

# isort: off
# pylint: disable=wrong-import-order,unused-import,ungrouped-imports
from tools.golden import paths  # noqa: F401  # first: puts tests/ on sys.path

from conftest import make_memory_db_path
from resolver_corpus import corpus_db_path, sample_rows
from tools.pypi_licence_sample.answer import unescape_field

# isort: on

#: The step kind of each table the sample is counted for.
TABLES = {"alias": "alias_name", "title": "text_title", "trove": "trove_name"}


class Answer(NamedTuple):
    """What ``resolve()`` says of a value: the expression, the category and
    whether ``detect()`` calls it exact."""

    expression: str | None
    category: str
    exact: bool


@contextmanager
def corpus() -> Iterator[LicenseDatabase]:
    """An in-memory database of the whole List fixture."""
    for db_path in corpus_db_path("lists", make_memory_db_path):
        yield LicenseDatabase(db_path, create=False)


def answer_of(db: LicenseDatabase, value: str) -> Answer:
    """The answer of ``resolve()`` to *value*."""
    resolution = resolve(value, db)
    return Answer(
        resolution["expression"],
        resolution["category"],
        resolution["expression"] is not None and is_exact(resolution),
    )


def project_counts(db: LicenseDatabase) -> dict[str, Counter[str]]:
    """The projects of the sample that each row of the tables reads, by
    table (:data:`TABLES`) and key: the folded name of an alias or a title,
    the classifier name of a trove name. A row nobody declares is absent."""
    counts: dict[str, Counter[str]] = {name: Counter() for name in TABLES}
    kinds = {kind: name for name, kind in TABLES.items()}
    for row in sample_rows():
        value = unescape_field(row["value"])
        steps = resolve(value, db)["steps"]
        for step in steps:
            table = kinds.get(step["kind"])
            if table is None or not step["applied"]:
                continue
            key = (
                step["from"]
                if table == "trove"
                else fold_case(" ".join(step["from"].split()))
            )
            counts[table][key] += int(row["projects"])
    return counts

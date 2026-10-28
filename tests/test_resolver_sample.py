# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The frozen PyPI sample and the guard over both fixtures (0.7.0 plan, T0).

``tests/fixtures/pypi_values_2026-10*.tsv`` holds the distinct short licence
values of the most downloaded PyPI projects and the answers of
``resolve()`` 0.6.0 on SPDX 3.29.0. Every rule pull request of 0.7.0 must
show that the set of values whose answer changed is exactly the set it
announces (``resolver_corpus.EXPECTED_CHANGES``).
"""

import hashlib
import re

from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import (
    NONE,
    Answer,
    changed_answers,
    changes_report,
    escape,
    parity_rows,
    pinned,
    read_rows,
    sample_files,
    sample_rows,
    unescape,
)

from licenseid import LicenseDatabase

SAMPLE = sample_rows()


def _rows(*values: str) -> list[dict[str, str]]:
    """Copies of the parity rows of single, stable ids (a later rule does not
    move them), to be edited by a test."""
    by_value = {unescape(row["value"]): row for row in parity_rows()}
    return [dict(by_value[value]) for value in values]


def test_the_changed_set_is_the_expected_set(corpus_db: LicenseDatabase) -> None:
    """The guard. Over the parity corpus and the PyPI sample, the values whose
    answer (expression, category, candidates) differs from the pinned 0.6.0
    one are exactly the keys of ``EXPECTED_CHANGES``. A later rule pull
    request adds each value it changes, with its reason, and no other."""
    changed = changed_answers(corpus_db)
    assert not changes_report(changed), "\n" + changes_report(changed)


def test_the_guard_names_a_value_whose_pin_was_edited(
    corpus_db: LicenseDatabase,
) -> None:
    """Mutation check (a): a pinned row edited in a copy is reported with the
    old and the new answer."""
    rows = _rows("MIT", "ISC")
    rows[0]["expression_0_6_0"] = "Apache-2.0"
    changed = changed_answers(corpus_db, rows)
    assert list(changed) == ["MIT"]  # ISC is untouched
    report = changes_report(changed)
    assert "'MIT'" in report
    assert "expression='Apache-2.0'" in report
    assert "expression='MIT'" in report


def test_the_guard_names_a_value_that_should_have_changed(
    corpus_db: LicenseDatabase,
) -> None:
    """A value in ``EXPECTED_CHANGES`` whose answer did not move is reported."""
    rows = _rows("0BSD", "MIT")
    changed = changed_answers(corpus_db, rows)
    report = changes_report(changed, {"0BSD": "a later rule reads it"})
    assert report.startswith("in EXPECTED_CHANGES, answer unchanged: '0BSD'")
    assert changes_report(changed, {}) == ""


def test_the_guard_accepts_a_declared_change(corpus_db: LicenseDatabase) -> None:
    """A moved answer that ``EXPECTED_CHANGES`` lists is not a failure."""
    rows = _rows("0BSD", "MIT")
    rows[0]["category_0_6_0"] = "unresolved"
    value = unescape(rows[0]["value"])
    changed = changed_answers(corpus_db, rows)
    assert changes_report(changed, {value: "test"}) == ""
    assert "changed, not in EXPECTED_CHANGES" in changes_report(changed, {})


def test_the_sample_files_are_small_and_named() -> None:
    """Each file is under the 800-line limit and named as the glob expects."""
    files = sample_files()
    assert files, "no pypi_values_2026-10*.tsv"
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 800, path.name
        assert re.fullmatch(r"pypi_values_2026-10(-\d+)?\.tsv", path.name), path.name


def test_the_sample_rows_are_distinct_and_escaped() -> None:
    """One row per value, written in the documented escape."""
    values = [row["value"] for row in SAMPLE]
    assert len(values) == len(set(values))
    assert len(SAMPLE) >= 100
    for row in SAMPLE:
        assert escape(unescape(row["value"])) == row["value"]
        assert int(row["projects"]) >= 1
        assert int(row["downloads"]) >= 0
        assert row["field"] in {"License", "License-Expression", "Classifier"}


def test_a_sample_row_without_an_expression_pins_none() -> None:
    """``-`` is ``None``: no row has the text ``-`` as its expression."""
    for row in SAMPLE:
        answer = pinned(row)
        assert isinstance(answer, Answer)
        assert (answer.expression is None) == (row["expression_0_6_0"] == NONE)


def _header_numbers() -> tuple[int, int]:
    """``(distinct values, values kept)`` that the files' headers record."""
    numbers = {
        tuple(re.findall(r"\d+", line)[:2])
        for path in sample_files()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("# distinct values:")
    }
    assert len(numbers) == 1, "the headers disagree"
    total, kept = next(iter(numbers))
    return int(total), int(kept)


def test_the_sample_header_records_the_full_set() -> None:
    """Each file says how many distinct values the sample had and the SHA-256
    of the sorted ``(value, expression, category)`` lines of all of them. When
    every value is kept the rows must hash to exactly that; when only the
    values that are not ``exact`` are kept, the files hold no ``exact`` one."""
    total, kept = _header_numbers()
    assert kept == len(SAMPLE)
    if kept < total:
        assert all(row["category_0_6_0"] != "exact" for row in SAMPLE)
        return
    digest = hashlib.sha256()
    for row in sorted(SAMPLE, key=lambda r: r["value"]):
        line = f"{row['value']}\t{row['expression_0_6_0']}\t{row['category_0_6_0']}\n"
        digest.update(line.encode())
    text = sample_files()[0].read_text(encoding="utf-8")
    assert f"(value, expression, category): {digest.hexdigest()}" in text


def test_every_sample_file_reads_the_same_columns() -> None:
    """The files are shards of one table."""
    columns = [tuple(read_rows(path)[0]) for path in sample_files()]
    assert len(set(columns)) == 1


def test_the_sample_and_the_parity_corpus_agree_on_shared_values() -> None:
    """A value in both fixtures is pinned to the same answer."""
    parity = {unescape(r["value"]): pinned(r) for r in parity_rows()}
    for row in SAMPLE:
        value = unescape(row["value"])
        if value in parity:
            assert pinned(row) == parity[value], value

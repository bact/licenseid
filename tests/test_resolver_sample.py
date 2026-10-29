# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The frozen PyPI sample and the guard over both fixtures (0.7.0 plan, T0).

``tests/fixtures/pypi_values_2026-10*.tsv`` holds the distinct short licence
values of the most downloaded PyPI projects and the answers of
``match()`` 0.6.0 on SPDX 3.29.0. Every rule pull request of 0.7.0 must
show that the set of values whose answer changed is exactly the set it
announces (``resolver_corpus.EXPECTED_CHANGES``).
"""

import ast
import hashlib
import re

import pytest
import resolver_corpus
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import (
    EXCEPTION_LIST,
    EXPECTED_CHANGES,
    LICENSE_LIST,
    UNRESOLVED,
    changed_answers,
    changes_report,
    corpus_rows,
    list_meta,
    parity_rows,
    pinned,
    read_comments,
    read_rows,
    sample_files,
    sample_rows,
)

from licenseid import LicenseDatabase, match
from tools.pypi_licence_sample.answer import (
    ANSWER_COLUMNS,
    NONE_FIELD,
    Answer,
    answer_of,
    escape_field,
    unescape_field,
)

SAMPLE = sample_rows()


def _parity_rows_for(*values: str) -> list[dict[str, str]]:
    """Copies of the parity rows of single, stable ids (a later rule does not
    move them), to be edited by a test."""
    by_value = {unescape_field(row["value"]): row for row in parity_rows()}
    return [dict(by_value[value]) for value in values]


def test_the_changed_set_is_the_expected_set(corpus_db: LicenseDatabase) -> None:
    """The guard. Over the parity corpus and the PyPI sample, a value whose
    answer differs from the pinned 0.6.0 one is listed in ``EXPECTED_CHANGES``
    and gives the listed answer; every other value gives its pinned answer.
    A later rule pull request adds each value it changes, with the new answer
    and the reason, and no other."""
    changed = changed_answers(corpus_db)
    assert not changes_report(changed), "\n" + changes_report(changed)


def test_the_guard_names_a_value_whose_pin_was_edited(
    corpus_db: LicenseDatabase,
) -> None:
    """Mutation check (a): a pinned row edited in a copy is reported with the
    old and the new answer."""
    rows = _parity_rows_for("MIT", "ISC")
    rows[0]["expression_0_6_0"] = "Apache-2.0"
    changed = changed_answers(corpus_db, rows)
    assert list(changed) == ["MIT"]  # ISC is untouched
    report = changes_report(changed, {})  # no listed value: only the diff
    assert "'MIT'" in report
    assert "expression: 'Apache-2.0' -> 'MIT'" in report
    assert "category" not in report  # only the field that differs is named


def test_the_guard_names_a_value_that_should_have_changed(
    corpus_db: LicenseDatabase,
) -> None:
    """A value in ``EXPECTED_CHANGES`` whose answer did not move is reported."""
    changed = changed_answers(corpus_db, _parity_rows_for("0BSD", "MIT"))
    listed = {"0BSD": (pinned(_parity_rows_for("0BSD")[0]), "a later rule reads it")}
    report = changes_report(changed, listed)
    assert report.startswith("in EXPECTED_CHANGES, answer unchanged: '0BSD'")
    assert changes_report(changed, {}) == ""


def _declared(
    corpus_db: LicenseDatabase, field: str, new: str
) -> tuple[dict[str, tuple[Answer, Answer]], Answer]:
    """Pin ``MIT`` with *field* set to *new* in a copy of its row; return the
    changed set and the answer ``MIT`` really gives."""
    rows = _parity_rows_for("MIT")
    rows[0][field] = new
    return changed_answers(corpus_db, rows), answer_of("MIT", match("MIT", corpus_db))


def test_the_guard_accepts_a_declared_change(corpus_db: LicenseDatabase) -> None:
    """A moved answer that ``EXPECTED_CHANGES`` lists, with the answer it now
    gives, is not a failure."""
    changed, now = _declared(corpus_db, "category_0_6_0", "unresolved")
    assert changes_report(changed, {"MIT": (now, "test")}) == ""
    assert "changed, not in EXPECTED_CHANGES" in changes_report(changed, {})


def test_the_guard_refuses_a_listed_value_with_a_wrong_answer(
    corpus_db: LicenseDatabase,
) -> None:
    """Listing a value is not a licence to give any answer: the answer is
    compared too."""
    changed, now = _declared(corpus_db, "category_0_6_0", "unresolved")
    wrong = now._replace(expression="ISC")
    report = changes_report(changed, {"MIT": (wrong, "test")})
    assert "in EXPECTED_CHANGES, wrong answer: 'MIT'" in report
    assert "expression: 'ISC' -> 'MIT'" in report


def test_a_reported_key_can_be_pasted_back() -> None:
    """The report prints the value as a Python literal, once escaped: a tab,
    a backslash and a lone surrogate come back as the value."""
    value = "a\tb\\c\udcff"
    changed = {value: (UNRESOLVED, UNRESOLVED._replace(trust="x"))}
    key = changes_report(changed, {}).split(": ")[1]
    assert ast.literal_eval(key) == value


def test_the_expected_answers_are_whole_answers() -> None:
    """Every entry of ``EXPECTED_CHANGES`` is an ``Answer`` and a reason."""
    for answer, reason in EXPECTED_CHANGES.values():
        assert isinstance(answer, Answer)
        assert reason


@pytest.mark.parametrize(
    ("field", "new"),
    [
        ("steps_0_6_0", "trim"),
        ("steps_0_6_0", "trim!"),
        ("step_targets_0_6_0", "MIT"),
        ("expansions_0_6_0", "plus_to_or_later"),
        ("expansion_targets_0_6_0", "MIT"),
        ("trust_0_6_0", "none"),
        ("input_same_0_6_0", "no"),
        ("reason_0_6_0", "lone surrogate"),
    ],
)
def test_a_change_of_steps_only_is_seen_and_declarable(
    corpus_db: LicenseDatabase, field: str, new: str
) -> None:
    """The guard compares step kinds and whether they applied, the targets of
    steps and expansions, expansion kinds, trust, the reason and whether
    ``input`` is the value, not only the expression and the category."""
    changed, now = _declared(corpus_db, field, new)
    assert list(changed) == ["MIT"], field
    assert changes_report(changed, {"MIT": (now, "steps only")}) == ""
    assert changes_report(changed, {}) != ""


def test_the_guard_reads_the_parity_corpus_and_the_sample() -> None:
    """The default rows of the guard are both fixtures, and the sample holds
    values the parity corpus does not (so dropping it is seen below)."""
    assert corpus_rows() == [*parity_rows(), *SAMPLE]
    parity = {row["value"] for row in parity_rows()}
    assert {row["value"] for row in SAMPLE} - parity


def test_the_guard_names_a_sample_only_value_whose_pin_was_edited(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation check on the guard itself: a pin edited in a row that only the
    PyPI sample holds is reported by the default call. A guard that read the
    parity corpus alone would not see it."""
    parity = {row["value"] for row in parity_rows()}
    row = dict(next(r for r in SAMPLE if r["value"] not in parity))
    row["trust_0_6_0"] = "edited"
    monkeypatch.setattr(resolver_corpus, "sample_rows", lambda: [row])
    changed = changed_answers(corpus_db)
    assert unescape_field(row["value"]) in changed


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
        assert escape_field(unescape_field(row["value"])) == row["value"]
        assert int(row["projects"]) >= 1
        assert int(row["downloads"]) >= 0
        assert row["field"] in {"License", "License-Expression", "Classifier"}


def test_a_sample_row_without_an_expression_pins_none() -> None:
    """``-`` is ``None``: no row has the text ``-`` as its expression."""
    for row in SAMPLE:
        assert (pinned(row).expression is None) == (
            row["expression_0_6_0"] == NONE_FIELD
        )


def _header_numbers() -> tuple[int, int]:
    """``(distinct values, values kept)`` that the files' headers record."""
    numbers = {
        tuple(re.findall(r"\d+", line)[:2])
        for path in sample_files()
        for line in read_comments(path)
        if line.startswith("# distinct values:")
    }
    assert len(numbers) == 1, "the headers disagree"
    total, kept = next(iter(numbers))
    return int(total), int(kept)


def test_the_sample_header_records_the_full_set() -> None:
    """Each file says how many distinct values the sample had and the SHA-256
    of the sorted ``(value, every answer column)`` lines of all of them. When
    every value is kept the rows must hash to exactly that; when only the
    values that are not ``exact`` are kept, the files hold no ``exact`` one."""
    total, kept = _header_numbers()
    assert kept == len(SAMPLE)
    if kept < total:
        assert all(row["category_0_6_0"] != "exact" for row in SAMPLE)
        return
    digest = hashlib.sha256()
    for row in sorted(SAMPLE, key=lambda r: r["value"]):
        fields = [row["value"], *(row[c] for c in ANSWER_COLUMNS)]
        digest.update(("\t".join(fields) + "\n").encode())
    text = "\n".join(read_comments(sample_files()[0]))
    assert f"answer column) lines: {digest.hexdigest()}" in text


def test_every_sample_file_reads_the_same_columns() -> None:
    """The files are shards of one table."""
    columns = [tuple(read_rows(path)[0]) for path in sample_files()]
    assert len(set(columns)) == 1


def test_the_sample_and_the_parity_corpus_agree_on_shared_values() -> None:
    """A value in both fixtures is pinned to the same answer."""
    parity = {unescape_field(r["value"]): pinned(r) for r in parity_rows()}
    for row in SAMPLE:
        value = unescape_field(row["value"])
        if value in parity:
            assert pinned(row) == parity[value], value


def test_the_list_version_is_one_in_every_fixture(
    corpus_db: LicenseDatabase,
) -> None:
    """Both List snapshots and the sample header name the same release, and the
    corpus database records it."""
    version, released = list_meta(LICENSE_LIST)
    assert list_meta(EXCEPTION_LIST) == (version, released)
    header = read_comments(sample_files()[0])[0]
    assert f"SPDX {version}." in header
    assert corpus_db.get_metadata()["license_list_version"] == version
    assert corpus_db.get_metadata()["release_date"] == released

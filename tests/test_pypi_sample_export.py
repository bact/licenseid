# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``tools.pypi_licence_sample``: ``distinct_values`` and ``export``, on a
sample of a dozen synthetic projects (``fixtures/pypi_sample_small.jsonl``).
No network: the sample is read from a file and answered from the corpus
database."""

import hashlib
import json
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import FIXTURES, read_comments, read_rows

from licenseid import LicenseDatabase
from tools.pypi_licence_sample import __main__ as sample_tool
from tools.pypi_licence_sample.answer import escape_field

SAMPLE = FIXTURES / "pypi_sample_small.jsonl"
PROJECTS = [json.loads(line) for line in SAMPLE.read_text("utf-8").splitlines()]
#: The distinct values of the sample, sorted by escaped value, with the
#: answer's category.
VALUES = {
    "Apache 2.0": "separator",
    "Apache\t2.0 \\ é": "unresolved",
    "ISC": "exact",
    "MIT": "exact",
    "mit": "lexical",
    "BSD License": "unresolved",
}


@pytest.fixture(autouse=True)
def corpus(monkeypatch: pytest.MonkeyPatch, corpus_db: LicenseDatabase) -> None:
    """Answer from the corpus database, whatever path ``--db`` names."""
    monkeypatch.setattr(sample_tool, "_open_database", lambda path: corpus_db)


def _rows(files: list[Path]) -> list[dict[str, str]]:
    return [row for path in files for row in read_rows(path)]


def test_distinct_values_are_counted_sorted_and_without_several_classifiers() -> None:
    """One row per value; a project of two classifiers, an error, licence text
    and ``UNKNOWN`` give none; ``field`` is the source most projects used."""
    got = sample_tool.distinct_values(PROJECTS)
    assert [row[0] for row in got] == sorted(VALUES, key=escape_field)
    by_value = {row[0]: row for row in got}
    assert by_value["MIT"] == ("MIT", "License-Expression", 3, 1001)
    assert by_value["ISC"][1:] == ("License", 1, 40)
    assert by_value["BSD License"][1:] == ("Classifier", 1, 5)
    assert "MIT License AND BSD License" not in by_value
    assert all("\n" not in value and value != "UNKNOWN" for value, *_ in got)


def test_export_writes_one_file_with_escaped_values_and_the_header(
    tmp_path: Path,
) -> None:
    """The answer columns, the escape and the hash of the full set."""
    path = sample_tool.export(SAMPLE, tmp_path / "out", Path("db"))[0]
    assert path.name == "out.tsv"
    rows = {row["value"]: row for row in read_rows(path)}
    assert set(rows) == {escape_field(v) for v in VALUES}
    escaped = rows["Apache\\t2.0 \\\\ \\xe9"]
    assert escaped["category_0_6_0"] == "unresolved"
    assert escaped["expression_0_6_0"] == "-"
    assert rows["mit"]["steps_0_6_0"] == "id_case"
    assert rows["mit"]["trust_0_6_0"] == "identity"
    assert rows["mit"]["input_same_0_6_0"] == "yes"
    assert rows["MIT"]["projects"] == "3"
    header = read_comments(path)
    assert any("distinct values: 6; kept in these files: 6" in c for c in header)
    digest = hashlib.sha256()
    for value in sorted(VALUES, key=escape_field):
        row = rows[escape_field(value)]
        line = [row["value"], *(row[c] for c in list(row)[4:7])]
        digest.update(("\t".join(line) + "\n").encode())
    assert f"candidates): {digest.hexdigest()}" in "\n".join(header)


def test_export_splits_into_files_that_share_one_header_hash(tmp_path: Path) -> None:
    """Two rows a file when ``max_lines`` leaves room for two: three files."""
    files = sample_tool.export(
        SAMPLE, tmp_path / "split", Path("db"), max_lines=sample_tool.HEADER_LINES + 2
    )
    assert [f.name for f in files] == ["split-1.tsv", "split-2.tsv", "split-3.tsv"]
    assert len(_rows(files)) == len(VALUES)
    hashes = {next(c for c in read_comments(f) if "sha256" in c) for f in files}
    assert len(hashes) == 1
    assert [read_comments(f)[-1] for f in files] == [
        f"# file {n} of 3" for n in (1, 2, 3)
    ]


def test_export_keeps_only_values_that_are_not_exact_when_they_do_not_fit(
    tmp_path: Path,
) -> None:
    """Capacity 2 files of 2 rows: 4 non-exact values are kept, the hash still
    covers all 6, and the header says so."""
    full = sample_tool.export(SAMPLE, tmp_path / "all", Path("db"))
    cut = sample_tool.export(
        SAMPLE,
        tmp_path / "cut",
        Path("db"),
        max_files=2,
        max_lines=sample_tool.HEADER_LINES + 2,
    )
    rows = _rows(cut)
    assert len(cut) == 2
    assert {row["category_0_6_0"] for row in rows} == {
        "separator",
        "unresolved",
        "lexical",
    }
    assert len(rows) == 4
    header = read_comments(cut[0])
    assert any("distinct values: 6; kept in these files: 4" in c for c in header)
    hash_line = next(c for c in header if "sha256" in c)
    assert hash_line in read_comments(full[0])


@pytest.mark.parametrize(
    ("max_files", "max_lines"),
    [(0, 790), (-1, 790), (1, 5), (1, 10), (1, 12)],
    ids=["zero-files", "negative-files", "no-room", "header-only", "too-many-left"],
)
def test_export_refuses_what_would_write_more_files_than_allowed(
    tmp_path: Path, max_files: int, max_lines: int
) -> None:
    """Never a silent overrun: 4 non-exact rows do not fit one file of 2."""
    (tmp_path / "out").mkdir()
    with pytest.raises(ValueError, match="max_files|not exact"):
        sample_tool.export(
            SAMPLE,
            tmp_path / "out" / "x",
            Path("db"),
            max_files=max_files,
            max_lines=max_lines,
        )
    assert not list((tmp_path / "out").iterdir())


def test_the_command_line_refuses_max_files_zero_with_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--max-files 0`` exits 2 through argparse and writes nothing."""
    (tmp_path / "out").mkdir()
    with pytest.raises(SystemExit) as stop:
        sample_tool.main(
            ["export", str(SAMPLE), "--out", str(tmp_path / "out" / "x")]
            + ["--max-files", "0"]
        )
    assert stop.value.code == 2
    assert "export: need max_files >= 1" in capsys.readouterr().err
    assert not list((tmp_path / "out").iterdir())

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The headers set of the speed gate: forms, archive, classes, verdict, gate."""

import io
import json
import sqlite3
import tarfile
from pathlib import Path
from typing import Any

import pytest
from speedgate_helpers import case, result

from benchmarks.speedgate import (
    buildinputs,
    cli,
    headerclasses,
    headergate,
    sets_headers,
)
from benchmarks.speedgate.gates import FAIL, NA, PASS
from benchmarks.speedgate.report import compare_folders
from benchmarks.speedgate.results import kind_of

# pylint: disable=missing-function-docstring


def _archive(path: Path, details: dict[str, dict[str, Any]]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in details.items():
            raw = json.dumps(data).encode()
            info = tarfile.TarInfo(f"list-9/json/details/{name}.json")
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
        other = tarfile.TarInfo("list-9/text/NOPE.txt")
        other.size = 0
        tar.addfile(other, io.BytesIO(b""))
    return path


def _detail(licence: str, header: str, deprecated: bool = False) -> dict[str, Any]:
    return {
        "licenseId": licence,
        "standardLicenseHeader": header,
        "isDeprecatedLicenseId": deprecated,
    }


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('"Plain line one\nline two"', "Plain line one\nline two"),
        ("*Starred header*", "Starred header"),
        ("<one instruction>\nKept line", "Kept line"),
        ("one line to give the name\nKept", "Kept"),
        ("Copyright (C) 2026 Someone\nKept", "Kept"),
        ("Portions Copyright [name of owner]\nKept", "Kept"),
        ("# Copyright 2026 YOUR NAME. Rights follow\nKept", "Rights follow\nKept"),
        ("Copyright 2026 A. All Rights Reserved.\nKept", "Kept"),
        (
            "Use [Software Name] and <name> and ____ now",
            "Use Example and Example and Example now",
        ),
        (
            "See [1] and <https://example.test/x>",
            "See [1] and <https://example.test/x>",
        ),
        ("No placeholder at all", "No placeholder at all"),
        ("", ""),
    ],
)
def test_each_cut_rule(header: str, expected: str) -> None:
    assert sets_headers.cut(header) == expected


def test_only_headers_of_licences_in_use_are_read_from_the_archive(
    tmp_path: Path,
) -> None:
    tarball = _archive(
        tmp_path / "list.tar.gz",
        {
            "B": _detail("B", "Header B"),
            "A": _detail("A", "Header A"),
            "Old": _detail("Old", "Header Old", deprecated=True),
            "None": _detail("None", "  "),
        },
    )
    assert sets_headers.read_headers(tarball) == [("A", "Header A"), ("B", "Header B")]
    cases = sets_headers.header_cases(tarball)
    assert [c["key"] for c in cases] == [
        "hdr:given:A",
        "hdr:cut:A",
        "hdr:given:B",
        "hdr:cut:B",
    ]
    assert cases[0]["want"] == "A" and cases[1]["kind"] == "hdr:cut"


def test_a_missing_archive_skips_the_set_with_a_printed_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    given: list[Path | None] = []

    def fake_build(*args: Any) -> dict[str, Any]:
        given.append(args[4])
        return {"counts": {}}

    monkeypatch.setattr(buildinputs, "build_inputs", fake_build)
    monkeypatch.setattr(buildinputs, "write_inputs", lambda *a: Path("x"))
    tarball = tmp_path / "gone.tar.gz"
    argv = ["inputs", str(tmp_path), "--side", str(tmp_path), "--tarball", str(tarball)]
    cli.main(argv)
    assert given == [None] and "headers: skipped" in capsys.readouterr().out
    _archive(tarball, {})
    cli.main(argv)
    assert given == [None, tarball]


def test_the_kind_of_a_header_key_is_its_form() -> None:
    assert kind_of("hdr:cut:MIT") == "hdr:cut"


def _database(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE licenses (license_id TEXT, is_deprecated BOOLEAN,"
        " superseded_by TEXT, same_text TEXT)"
    )
    con.executemany(
        "INSERT INTO licenses VALUES (?, ?, ?, ?)",
        [
            ("GPL-2.0-only", 0, None, "GPL-2.0-only GPL-2.0-or-later"),
            ("GPL-2.0-or-later", 0, None, "GPL-2.0-only GPL-2.0-or-later"),
            ("GPL-2.0", 1, None, None),
            ("GPL-2.0+", 1, None, None),
            ("Old-1", 1, "New-1", None),
            ("New-1", 0, None, None),
            ("Solo", 0, None, None),
            ("Gone-1", 1, None, None),
        ],
    )
    con.commit()
    con.close()


def test_a_class_is_a_same_text_group_with_its_deprecated_ids(
    tmp_path: Path,
) -> None:
    db = tmp_path / "licenses.db"
    _database(db)
    found = headerclasses.classes(db)
    twins = found["GPL-2.0-only"]
    assert found["GPL-2.0-or-later"] == twins
    assert found["GPL-2.0"] == twins and found["GPL-2.0+"] == twins
    assert found["Old-1"] == found["New-1"] == "New-1"
    assert found["Solo"] == "Solo" and found["Gone-1"] == "Gone-1"


def _hdr(answer: str | None, score: float = 1.0) -> dict[str, Any]:
    return case(1.0, answer, score)


def test_a_verdict_is_right_for_the_class_wrong_for_another_and_none_below_the_bar(
    tmp_path: Path,
) -> None:
    db = tmp_path / "licenses.db"
    _database(db)
    found = result(
        {
            "hdr:given:GPL-2.0-only": _hdr("GPL-2.0-or-later"),
            "hdr:given:Old-1": _hdr("New-1"),
            "hdr:given:Solo": _hdr("New-1"),
            "hdr:cut:Solo": _hdr("Solo", 0.84),
            "hdr:cut:New-1": _hdr("Solo OR New-1"),
            "hdr:cut:Gone-1": _hdr(None),
        }
    )
    headerclasses.attach(found, db)
    assert found["classes"]["New-1"] == "New-1"
    got = headergate.verdicts(found)
    assert got["hdr:given:GPL-2.0-only"] == ("right", "GPL-2.0-or-later")
    assert got["hdr:given:Old-1"][0] == "right"
    assert got["hdr:given:Solo"] == ("wrong", "New-1")
    assert got["hdr:cut:Solo"] == ("none", "")
    assert got["hdr:cut:New-1"][0] == "wrong"
    assert got["hdr:cut:Gone-1"][0] == "none"


def _run(right: int, wrong: int, none: int, form: str = "given") -> dict[str, Any]:
    cases = {}
    for n in range(right + wrong + none):
        answer = "A" if n < right else "B" if n < right + wrong else None
        cases[f"hdr:{form}:L{n}"] = _hdr(answer)
    return result(cases, classes={f"L{n}": "A" for n in range(right)})


def _both(given: dict[str, Any], cut: dict[str, Any]) -> dict[str, Any]:
    return result(
        {**given["cases"], **cut["cases"]},
        classes={**given["classes"], **cut["classes"]},
    )


def test_the_gate_passes_with_no_fewer_right_and_no_more_wrong() -> None:
    base = {"headers": _both(_run(5, 2, 1), _run(4, 2, 2, "cut"))}
    better = {"headers": _both(_run(6, 1, 1), _run(4, 2, 2, "cut"))}
    gate = headergate.gate(base, better)
    assert gate.status == PASS and "5 / 2 / 1 to 6 / 1 / 1" in gate.detail


def test_the_gate_fails_on_fewer_right_in_a_form() -> None:
    base = {"headers": _both(_run(5, 2, 1), _run(4, 2, 2, "cut"))}
    cand = {"headers": _both(_run(5, 2, 1), _run(3, 2, 3, "cut"))}
    assert headergate.gate(base, cand).status == FAIL


def test_the_gate_fails_on_more_wrong_in_a_form() -> None:
    base = {"headers": _both(_run(5, 2, 1), _run(4, 2, 2, "cut"))}
    cand = {"headers": _both(_run(5, 3, 0), _run(4, 2, 2, "cut"))}
    assert headergate.gate(base, cand).status == FAIL


def test_a_base_without_the_set_is_not_applicable_but_shows_the_candidate() -> None:
    cand = {"headers": _both(_run(5, 2, 1), _run(4, 2, 2, "cut"))}
    gate = headergate.gate({}, cand)
    assert gate.status == NA and "as given 5 / 2 / 1, cut 4 / 2 / 2" in gate.detail
    assert headergate.gate(cand, {}).status == NA
    assert headergate.section({}, cand) == ["headers: not in both runs"]


def test_a_header_whose_verdict_moved_is_listed_with_both_answers() -> None:
    base = {"headers": _run(2, 0, 0)}
    cand = {"headers": _run(1, 0, 1)}
    cand["headers"]["classes"] = {"L0": "A"}
    lines = headergate.section(base, cand)
    assert lines[0] == "headers: 1 verdicts moved"
    assert lines[1] == "  L1 (as given): right [A] -> none [-]"


def test_the_report_has_the_headers_gate_and_section(tmp_path: Path) -> None:
    for name, run in (("base", _run(2, 0, 0)), ("cand", _run(1, 0, 1))):
        (tmp_path / name).mkdir()
        (tmp_path / name / "headers.json").write_text(json.dumps(run))
    text, failed = compare_folders(tmp_path / "base", tmp_path / "cand", None, None)
    assert failed is True
    assert "== Headers" in text and "FAIL         Headers:" in text

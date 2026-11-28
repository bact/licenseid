# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``SAME_TEXT`` (JSON ``same_text``): the other List IDs whose text is
identical to a text answer's (``MPL-2.0`` and ``MPL-2.0-no-copyleft-exception``
share one text, so the text alone cannot choose). Empty for any other method,
for a licence alone, and for a database without the column."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import sqlite3
from collections.abc import Generator
from typing import cast
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings, public_match
from long_text_db import LONG_TEXTS, long_text_detector
from matcher_db import Lic, seeded_db

from licenseid import regionalign, wordregion
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.result import json_line, public_result, text_line
from licenseid.types import RawMatch


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


MPL = _text("MPL-2.0-no-copyleft-exception")
MPL_IDS = ["MPL-2.0", "MPL-2.0-no-copyleft-exception"]


@pytest.fixture(scope="module")
def mpl_db() -> Generator[str, None, None]:
    """MPL-2.0 and its no-copyleft twin, one text, as a build groups them,
    beside MIT (alone)."""
    text = normalize_text(MPL)
    rows = [Lic(i, i, search_text=text) for i in MPL_IDS]
    rows.append(Lic("MIT", "MIT License", search_text=normalize_text(_text("MIT"))))
    for db_path in seeded_db("test_same_text", rows):
        with sqlite3.connect(db_path, uri=True) as conn:
            conn.execute(
                "UPDATE licenses SET same_text = ? WHERE license_id LIKE 'MPL-2.0%'",
                (" ".join(MPL_IDS),),
            )
        yield db_path


def _top(db_path: str, text: str) -> dict[str, object]:
    return dict(LicenseDetector(db_path).detect(text=text)[0])


def test_a_text_names_the_licences_of_the_same_text(mpl_db: str) -> None:
    top = _top(mpl_db, MPL)
    assert (top["method"], top["exact"]) == ("text", True)
    assert top["expression"] in MPL_IDS
    # Each twin names the other, never itself.
    assert top["same_text"] == [i for i in MPL_IDS if i != top["expression"]]


def test_a_licence_alone_has_none(mpl_db: str) -> None:
    top = _top(mpl_db, _text("MIT"))
    assert (top["expression"], top["method"], top["same_text"]) == ("MIT", "text", None)


def test_a_family_names_its_members_but_the_answer(given: GivenWarnings) -> None:
    top = long_text_detector().detect(text=_text("GPL-2.0-only"))[0]
    assert given.conditions() == {"variant not stated"}
    assert top["method"] == "text"
    assert top["expression"] in {"GPL-2.0-only", "GPL-2.0-or-later"}
    # Whichever of the two settle_text chose, the other one is named.
    other = {"GPL-2.0-only", "GPL-2.0-or-later"} - {top["expression"]}
    assert top["same_text"] == sorted(other)


def test_a_large_group_is_sorted_and_leaves_the_answer_out(
    given: GivenWarnings,
) -> None:
    top = long_text_detector().detect(text=_text("GFDL-1.3-only"))[0]
    assert given.conditions() <= {"variant not stated"}
    group = sorted(
        i
        for i in (
            "GFDL-1.3-invariants-only",
            "GFDL-1.3-invariants-or-later",
            "GFDL-1.3-no-invariants-only",
            "GFDL-1.3-no-invariants-or-later",
            "GFDL-1.3-only",
            "GFDL-1.3-or-later",
        )
        if i != top["expression"]
    )
    assert len(group) == 5
    assert top["same_text"] == group


def test_a_declared_id_has_none(mpl_db: str) -> None:
    found = LicenseDetector(mpl_db).detect(license_id="MPL-2.0")
    assert (found[0]["expression"], found[0]["same_text"]) == ("MPL-2.0", None)


def test_an_id_or_a_name_given_as_text_has_none(mpl_db: str) -> None:
    detector = LicenseDetector(mpl_db)
    for value in ("MPL-2.0", "MPL-2.0-no-copyleft-exception"):
        top = detector.detect(text=value)[0]
        assert (top["method"], top["same_text"]) == ("id", None)


def test_a_tag_and_a_field_have_none(mpl_db: str) -> None:
    detector = LicenseDetector(mpl_db)
    for text in ("SPDX-License-Identifier: MPL-2.0", '{"license": "MPL-2.0"}'):
        found = detector.detect(text=text)
        assert found[0]["expression"] == "MPL-2.0"
        assert found[0]["method"] in {"tag", "field"}
        assert found[0]["same_text"] is None


def test_a_database_without_the_column_has_none(mpl_db: str) -> None:
    with sqlite3.connect(mpl_db, uri=True) as conn:
        conn.execute("UPDATE licenses SET same_text = NULL")
    try:
        assert _top(mpl_db, MPL)["same_text"] is None
    finally:
        with sqlite3.connect(mpl_db, uri=True) as conn:
            conn.execute(
                "UPDATE licenses SET same_text = ? WHERE license_id LIKE 'MPL-2.0%'",
                (" ".join(MPL_IDS),),
            )


RAW = {
    "license_id": "GPL-2.0-or-later",
    "method": "text",
    "exact": True,
    "score": 1.0,
    "similarity": 1.0,
    "coverage": 1.0,
}
TWINS = {"GPL-2.0-only": ["GPL-2.0-only", "GPL-2.0-or-later"]}


def _public(raw: dict[str, object], twins: dict[str, list[str]]) -> list[str] | None:
    return public_result(cast(RawMatch, raw), [], twins)["same_text"]


def test_the_final_expression_is_the_one_left_out() -> None:
    """settle_text switches -only to -or-later after the match: the group is
    the one of the ID the result names, minus that ID."""
    twins = {i: ["GPL-2.0-only", "GPL-2.0-or-later"] for i in TWINS["GPL-2.0-only"]}
    assert _public(RAW, twins) == ["GPL-2.0-only"]
    assert _public({**RAW, "license_id": "GPL-2.0-only"}, twins) == ["GPL-2.0-or-later"]


@pytest.mark.parametrize(
    "raw",
    [
        {**RAW, "method": "id"},
        {**RAW, "method": "name"},
        {**RAW, "license_id": "GPL-2.0-only OR MIT"},
        {**RAW, "license_id": "MIT"},
    ],
    ids=["id", "name", "compound", "unknown"],
)
def test_only_a_text_of_one_licence_has_a_group(raw: dict[str, object]) -> None:
    twins = {i: ["GPL-2.0-only", "GPL-2.0-or-later"] for i in TWINS["GPL-2.0-only"]}
    assert _public(raw, twins) is None


def test_the_text_line_and_the_json_carry_the_field() -> None:
    result = public_match("MPL-2.0", method="text", same_text=["A-1.0", "B-2.0+"])
    assert text_line(result).endswith(
        "\tVARIANT_STATED=\tSAME_TEXT=A-1.0 B-2.0+\tREASON=\tTEXTS="
    )
    assert json.loads(json_line(result))["same_text"] == ["A-1.0", "B-2.0+"]
    assert text_line(public_match()).endswith("\tSAME_TEXT=\tREASON=\tTEXTS=")
    assert json.loads(json_line(public_match()))["same_text"] is None


def test_the_cli_prints_it(mpl_db: str) -> None:
    for flag in ("-v", "--json"):
        result = CliRunner().invoke(
            cli, ["--db", mpl_db, "detect", flag, "--text", MPL]
        )
        assert result.exit_code == 0, result.output
        line = result.stdout.splitlines()[0]
        if flag == "--json":
            assert json.loads(line)["same_text"] in (["MPL-2.0"], [MPL_IDS[1]])
        else:
            assert line.rsplit("\t", 3)[1] in {
                "SAME_TEXT=MPL-2.0",
                f"SAME_TEXT={MPL_IDS[1]}",
            }


def test_is_lines_do_not_carry_it(mpl_db: str) -> None:
    result = CliRunner().invoke(cli, ["--db", mpl_db, "is-osi", "--text", MPL])
    assert "SAME_TEXT" not in result.output


def test_the_ids_are_sorted_whatever_order_they_were_stored_in() -> None:
    twins = {"MIT": ["MIT", "Z-1.0", "A-1.0", "M-1.0"]}
    assert _public({**RAW, "license_id": "MIT"}, twins) == ["A-1.0", "M-1.0", "Z-1.0"]


# -- Tier 2 scores a text once for the licences that share it -------------------

_WORDS = [f"{a}{b}" for a in "bcdfghklmnprstvz" for b in ("ant", "ell", "ore")]
_SHARED = [_WORDS[(i * 7 + i // 5) % len(_WORDS)] + str(i // 48) for i in range(300)]
_OTHER = [w if i % 5 else "zz" + w for i, w in enumerate(_SHARED)]


@pytest.fixture(scope="module")
def twin_db() -> Generator[str, None, None]:
    """Two licences of one text and a third that differs in every fifth word."""
    rows = [
        Lic("TWIN-A", "A", search_text=" ".join(_SHARED)),
        Lic("TWIN-B", "B", search_text=" ".join(_SHARED)),
        Lic("OTHER-C", "C", search_text=" ".join(_OTHER)),
    ]
    for db_path in seeded_db("test_twin_scores", rows):
        with sqlite3.connect(db_path, uri=True) as conn:
            conn.execute(
                "UPDATE licenses SET same_text = 'TWIN-A TWIN-B'"
                " WHERE license_id LIKE 'TWIN-%'"
            )
        yield db_path


@pytest.mark.parametrize(
    ("span", "scores"),
    [
        ((100, 180, 0), (1.0, 1.0, 0.7503)),
        ((0, 60, 0), (1.0, 1.0, 0.7549)),
        ((100, 180, 9), (0.9043, 0.9043, 0.7011)),
    ],
    ids=["middle", "head", "middle-edited"],
)
def test_twins_are_aligned_once_and_each_has_its_row(
    twin_db: str, span: tuple[int, int, int], scores: tuple[float, float, float]
) -> None:
    """Three candidates, two distinct texts: one character alignment and one
    word alignment a text, and every licence keeps its own row. The rows are
    those the base gives, which aligned each licence of a text alone. *span*:
    the words of the text the input takes, and every such word of it that is
    another (0: none)."""
    start, stop, edit = span
    given = [w if not edit or i % edit else "qq" for i, w in enumerate(_SHARED)]
    with (
        mock.patch.object(
            regionalign, "walled", autospec=True, side_effect=regionalign.walled
        ) as walled,
        mock.patch.object(
            wordregion, "located", autospec=True, side_effect=wordregion.located
        ) as located,
    ):
        found = LicenseDetector(twin_db).detect(
            " ".join(given[start:stop]), only_spdx=False
        )
    assert [(r["expression"], r["score"], r["same_text"]) for r in found] == [
        ("TWIN-A", scores[0], ["TWIN-B"]),
        ("TWIN-B", scores[1], ["TWIN-A"]),
        ("OTHER-C", scores[2], None),
    ]
    for call in (walled, located):
        texts = [c.args[2] for c in call.call_args_list]
        assert (len(texts), len(set(texts))) == (2, 2)

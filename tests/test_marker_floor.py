# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The marker floor (``similarity.floor_lift``) and where it is taken back
(``markerfloor``): an input longer than the marker's licence text that holds
whole texts of other licences keeps the additive boost only (roadmap item
67). The detector rows run on the real-sized fixture database, so the near
neighbours have their texts."""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from click.testing import CliRunner
from long_text_db import DB_PATH, LONG_TEXTS, long_text_detector

from licenseid import markerfloor
from licenseid.cli import cli
from licenseid.markerfloor import doubt_floors, floor_doubted
from licenseid.similarity import calculate_final_score, floor_lift
from licenseid.textnames import skipped
from licenseid.types import InternalMatch

if TYPE_CHECKING:
    from licenseid.database import LicenseDatabase

FIXTURES = Path(__file__).parent / "fixtures"
GPL_NOTICE = (
    "This program is free software; you can redistribute it and/or modify it "
    "under the terms of the GNU General Public License as published by the "
    "Free Software Foundation; either version 2 of the License, or (at your "
    "option) any later version."
)
GPL2_GROUP = ("GPL-2.0-only", "GPL-2.0-or-later")


def _text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text("utf-8"))
    return str(data["license_text"])


def _match(
    license_id: str = "MIT", base: float = 0.5, coverage: float = 0.3
) -> InternalMatch:
    return InternalMatch(
        license_id=license_id,
        method="text",
        exact=False,
        score=0.0,
        similarity=base,
        coverage=coverage,
        base_score=base,
        pop_score=0,
        best_window="",
    )


# -- Which texts doubt a floor (floor_doubted) ------------------------------


@pytest.mark.parametrize(
    ("rows", "marker", "groups", "doubted"),
    [
        (["MIT"], "MIT", {}, False),
        (["MIT"], "mit", {}, False),
        (["BSD-3-Clause", "MIT"], "MIT", {}, True),
        (["Apache-2.0"], "MIT", {}, True),
        (None, "MIT", {}, False),
        ([], "MIT", {}, False),
        (["GPL-2.0-only"], "GPL-2.0-or-later", {"GPL-2.0-only": GPL2_GROUP}, False),
        (["GPL-2.0-only"], "GPL-2.0-or-later", {}, True),
        (
            ["GPL-2.0-only"],
            "GPL-2.0-or-later WITH Font-exception-2.0",
            {"GPL-2.0-only": GPL2_GROUP},
            False,
        ),
        (["GPL-2.0-only"], "GPL-2.0+", {"GPL-2.0-only": GPL2_GROUP}, False),
        (["GPL-2.0-only"], "GPL-2.0", {}, False),
        (
            ["GPL-2.0-only", "MIT"],
            "GPL-2.0-or-later",
            {"GPL-2.0-only": GPL2_GROUP},
            True,
        ),
    ],
    ids=[
        "own",
        "own-case",
        "own-and-other",
        "other",
        "none",
        "empty",
        "twin",
        "no-group",
        "exception",
        "deprecated-plus",
        "deprecated-bare",
        "twin-and-other",
    ],
)
def test_floor_doubted(
    rows: list[str] | None,
    marker: str,
    groups: dict[str, Sequence[str]],
    doubted: bool,
) -> None:
    assert floor_doubted(rows, marker, groups) is doubted


# -- What the floor adds (similarity.floor_lift) ----------------------------


@pytest.mark.parametrize(
    ("base", "conf", "path", "expected"),
    [
        (0.5, 0.92, (False, 10), (0.874, 0.328)),
        (0.9, 0.92, (False, 10), (0.946, 0.0)),
        (0.5, 0.92, (True, 50), (0.5276, 0.0)),
        (0.5, 0.92, (True, 49), (0.874, 0.328)),
        (0.5, 0.95, (True, 50), (0.9025, 0.355)),
        (0.5, 0.84, (False, 10), (0.5, 0.0)),
    ],
    ids=["floor", "additive-higher", "pure-long", "pure-short", "structural", "low"],
)
def test_floor_lift(
    base: float, conf: float, path: tuple[bool, int], expected: tuple[float, float]
) -> None:
    """*path* is (whether the input is a pure licence text, its word count);
    *expected* the score and the part of it the floor added."""
    match, boosts = _match(base=base), {"MIT": conf}
    is_pure, q_len = path
    assert calculate_final_score(match, boosts, is_pure, False, q_len) == (
        pytest.approx(expected[0])
    )
    lift = floor_lift(match, boosts, is_pure, False, q_len)
    assert lift == pytest.approx(expected[1])


# -- Taking the floor back (doubt_floors) -----------------------------------


class _Search:
    """A stand-in for ``markerfloor._search``: *rows* found, calls counted."""

    def __init__(self, rows: list[str] | None) -> None:
        self.rows = rows
        self.calls: list[str] = []

    def __call__(
        self, _db: object, _norm: str, marker_id: str
    ) -> tuple[list[str] | None, dict[str, tuple[str, ...]]]:
        self.calls.append(marker_id)
        return self.rows, {}


def _lifted(license_id: str, coverage: float, lift: float = 0.3) -> InternalMatch:
    match = _match(license_id, coverage=coverage)
    match["score"] = 0.9
    if lift:
        match["floor_lift"] = lift
    return match


def _doubt(
    monkeypatch: pytest.MonkeyPatch, ranked: list[InternalMatch], rows: list[str]
) -> _Search:
    search = _Search(rows)
    monkeypatch.setattr(markerfloor, "_search", search)
    doubt_floors(ranked, "input", cast("LicenseDatabase", None))
    return search


@pytest.mark.parametrize(
    ("coverage", "score", "searches"),
    [(1.05, 0.9, 0), (1.0501, 0.6, 1)],
    ids=["at-1.05", "above-1.05"],
)
def test_only_coverage_above_1_05_asks_the_search(
    monkeypatch: pytest.MonkeyPatch, coverage: float, score: float, searches: int
) -> None:
    ranked = [_lifted("MIT", coverage)]
    search = _doubt(monkeypatch, ranked, ["Apache-2.0"])
    assert ranked[0]["score"] == pytest.approx(score)
    assert len(search.calls) == searches


def test_the_search_runs_once_per_input(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = [
        _lifted("MIT", 2.0),
        _lifted("Zlib", 0.5),
        _lifted("BSD-3-Clause", 3.0),
        _lifted("ISC", 3.0, lift=0.0),
    ]
    search = _doubt(monkeypatch, ranked, ["MIT"])
    assert search.calls == ["MIT"]
    assert [m["score"] for m in ranked] == pytest.approx([0.9, 0.9, 0.6, 0.9])
    assert "floor_lift" in ranked[0]
    assert "floor_lift" not in ranked[2]


def test_no_floor_no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    ranked = [_lifted("MIT", 3.0, lift=0.0), _lifted("ISC", 3.0, lift=-0.1)]
    assert not _doubt(monkeypatch, ranked, ["Apache-2.0"]).calls
    assert [m["score"] for m in ranked] == [0.9, 0.9]


# -- On real texts ----------------------------------------------------------

SEVERAL = "\n\n".join(
    [GPL_NOTICE, _text("MIT"), _text("BSD-3-Clause"), _text("BSD-2-Clause")]
)


def _top(text: str) -> tuple[str, float]:
    results = long_text_detector().detect(text=text)
    return results[0]["expression"], results[0]["score"]


def test_a_marker_does_not_answer_for_several_texts() -> None:
    """The BSD clauses of one of three texts (grpcio's and pandas' shape):
    0.947 on the floor before, now no answer at 0.85."""
    results = long_text_detector().detect(text=SEVERAL)
    assert results[0]["texts"] == ["BSD-2-Clause", "BSD-3-Clause", "MIT"]
    assert results[0]["score"] < 0.85
    assert all(r["expression"] != "BSD-3-Clause" for r in results[:3])


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (_text("BSD-2-Clause") + "\n\n" + _text("BSD-2-Clause"), "BSD-2-Clause"),
        (GPL_NOTICE, "GPL-2.0-or-later"),
        (
            "# Widget\n\nA tool to frob widgets.\n\n## License\n\n" + GPL_NOTICE,
            "GPL-2.0-or-later",
        ),
        (
            (FIXTURES / "mixed-content-curated/BSD-3-Clause/pytorch.txt").read_text(
                "utf-8"
            ),
            "BSD-3-Clause",
        ),
        (
            (FIXTURES / "mixed-content/ssh-keyscan/README.md").read_text("utf-8"),
            "ssh-keyscan",
        ),
    ],
    ids=["own-text-twice", "notice", "readme", "pytorch", "ssh-keyscan-readme"],
)
def test_the_floor_stays(text: str, answer: str) -> None:
    """Only its own text (sphinx's shape), a notice or pointer under coverage
    1.05, a text the search cannot confirm (PyTorch's copyright block):
    the floor answers as before."""
    expression, score = _top(text)
    assert expression == answer
    assert score >= 0.85


def test_terse_and_verbose_agree() -> None:
    """The search of the gate runs where ``TEXTS`` is skipped too."""
    detector = long_text_detector()
    shown = detector.detect(text=SEVERAL)[0]
    with skipped():
        terse = detector.detect(text=SEVERAL)[0]
    assert (terse["expression"], terse["score"]) == (
        shown["expression"],
        shown["score"],
    )
    assert terse["texts"] is None
    with skipped():
        assert detector.is_osi(text=SEVERAL) is None


@pytest.mark.terse_cli
@pytest.mark.parametrize(
    ("args", "stdout", "code"),
    [(["detect"], "\n", 1), (["is-osi"], None, 1)],
    ids=["detect", "is-osi"],
)
def test_the_cli_agrees_with_verbose(
    args: list[str], stdout: str | None, code: int
) -> None:
    """Terse ``detect`` and ``is-osi`` skip ``TEXTS``, not the gate: no answer,
    as ``-v``, where the floor gave BSD-3-Clause before."""
    long_text_detector()  # builds the shared database
    db_path = DB_PATH
    verbose = CliRunner().invoke(
        cli, ["--db", db_path, "detect", "-v", "--text", SEVERAL]
    )
    assert verbose.exit_code == 1
    assert verbose.stdout.startswith("EXPRESSION=\t")
    result = CliRunner().invoke(cli, ["--db", db_path, *args, "--text", SEVERAL])
    assert result.exit_code == code
    if stdout is not None:
        assert result.stdout == stdout

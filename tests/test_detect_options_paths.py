# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where the options of ``detect()`` act, pinned as they are (roadmap
item 46).

Characterization tests: they pin today's answers, right or wrong. A pin
marked ``# BUG:`` is a suspected bug, ``# DECISION:`` a behaviour to keep or
change on purpose; fixing either moves the pin. ``exclude``, ``only_common``
and ``only_spdx`` filter the full-text candidates of Tier 1
(``licenseid.retrieval.get_candidates``), and ``hint`` adds its IDs after
the filter. ``enable_popularity`` acts in the Tier 2 ranking and its
tie-breaker, on every candidate (more in ``tests/test_match_ordering.py``).

MIT, MIT-0, JSON, X11 and Acme-MIT carry their real text, as AGENTS.md asks:
a row with no ``search_text`` never reaches Tiers 1 and 2, so a filter test
on it passes trivially. The GPL rows carry only their names, enough for
full-text search to find them.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import itertools
import json
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import PROSE, Lic, seeded_db

import licenseid
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text

LONG = Path(__file__).parent / "fixtures" / "license-text-long"


def _fixture_text(license_id: str) -> str:
    data = json.loads((LONG / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


MIT = _fixture_text("MIT")  # starts "MIT License": a heading marker
BODY = MIT.split("\n", 2)[2]  # the same text without the heading
ACME = BODY.replace("Permission is hereby", "Acme grants that permission is hereby")
GPL_ONLY = "GNU General Public License v2.0 only"
MIT_URL = "https://opensource.org/licenses/MIT"

ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text=normalize_text(MIT)),
    Lic(
        "MIT-0",
        "MIT No Attribution",
        True,
        True,
        search_text=normalize_text(_fixture_text("MIT-0")),
    ),
    # Neither OSI nor FSF, nor high usage: what only_common drops.
    Lic("JSON", "JSON License", search_text=normalize_text(_fixture_text("JSON"))),
    Lic(
        "X11",
        "X11 License",
        True,
        False,
        True,
        search_text=normalize_text(_fixture_text("X11")),
    ),
    # Not on the List: what only_spdx (on by default) drops. A database
    # licenseid builds has no such row, so there only_spdx does nothing.
    Lic("Acme-MIT", "Acme MIT Licence", False, search_text=normalize_text(ACME)),
    Lic("GPL-2.0-only", GPL_ONLY, True, True, True, search_text=GPL_ONLY.lower()),
    Lic(
        "GPL-2.0",
        "GNU General Public License v2.0",
        is_deprecated=True,
        superseded_by="GPL-2.0-only",
        search_text="gnu general public license v2.0",
    ),
)


# Popularity, different for each row, so enable_popularity reorders a tie.
POPULARITY = {"Acme-MIT": 2000, "MIT-0": 1000, "MIT": 50, "X11": 5, "JSON": 1}


@pytest.fixture(scope="module")
def db_path() -> Generator[str, None, None]:
    urls = [("MIT", False, MIT_URL)]
    for path in seeded_db("test_detect_options_paths", ROWS, urls=urls):
        with sqlite3.connect(path, uri=True) as conn:
            conn.executemany(
                "UPDATE licenses SET pop_score = ? WHERE license_id = ?",
                [(pop, lic) for lic, pop in POPULARITY.items()],
            )
        yield path


@pytest.fixture(scope="module")
def detector(db_path: str) -> LicenseDetector:
    return LicenseDetector(db_path)


def answers(detector: LicenseDetector, **kwargs: Any) -> list[str]:
    return [r["expression"] for r in detector.detect(**kwargs)]


NEAR = ["MIT", "JSON", "MIT-0", "X11"]  # BODY's answers, best first
GPL = "GPL-2.0-only"


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, NEAR),
        ({"exclude": ["MIT"]}, NEAR[1:]),
        # DECISION: exclude compares in exact case; hint folds it.
        ({"exclude": ["mit"]}, NEAR),
        ({"exclude": ["Nope-1.0"]}, NEAR),
        ({"exclude": NEAR}, []),
        ({"hint": ["MIT"]}, NEAR),  # already a candidate: nothing added
        ({"hint": ["Nope-1.0"]}, NEAR),  # no row: nothing added
        ({"hint": [GPL]}, [*NEAR, GPL]),  # added last, scored 0
        ({"hint": ["gpl-2.0-only"]}, [*NEAR, GPL]),
        # BUG: a hint is compared in exact case with the candidates, then
        # looked up case-folded: MIT twice.
        ({"hint": ["mit"]}, [*NEAR, "MIT"]),
        # BUG: a repeated hint is added each time.
        ({"hint": [GPL, GPL]}, [*NEAR, GPL, GPL]),
        ({"hint": [GPL, "gpl-2.0-only"]}, [*NEAR, GPL, GPL]),
        # DECISION: a deprecated ID is hinted as written, not its successor.
        ({"hint": ["GPL-2.0"]}, [*NEAR, "GPL-2.0"]),
        # BUG: hint is added after the filter, so it undoes exclude.
        ({"exclude": ["MIT"], "hint": ["MIT"]}, [*NEAR[1:], "MIT"]),
        ({"only_common": True}, ["MIT", "MIT-0", "X11"]),
        # BUG: nor does a hint pass the only_common or only_spdx filter.
        ({"only_common": True, "hint": ["JSON"]}, ["MIT", "MIT-0", "X11", "JSON"]),
        ({"only_spdx": False}, ["MIT", "Acme-MIT", *NEAR[1:]]),
        ({"only_spdx": True, "hint": ["Acme-MIT"]}, [*NEAR, "Acme-MIT"]),
        ({"only_common": True, "exclude": ["MIT"]}, ["MIT-0", "X11"]),
        # No tie here, so popularity (a nudge of 1e-4 at most) moves nothing.
        ({"enable_popularity": True}, NEAR),
    ],
    ids=repr,
)
def test_the_options_shape_the_text_candidates(
    detector: LicenseDetector, options: dict[str, Any], expected: list[str]
) -> None:
    assert answers(detector, text=BODY, **options) == expected


def test_a_hinted_candidate_has_no_text_to_score(detector: LicenseDetector) -> None:
    """DECISION: a hint adds a candidate with no ``search_text``, so it is
    scored 0 on its own: it never lifts a licence above the text's own."""
    hinted = detector.detect(text=BODY, hint=[GPL])[-1]
    assert (hinted["expression"], hinted["score"], hinted["exact"]) == (GPL, 0, False)


def test_a_hint_hides_the_marker_candidate_of_the_same_licence(
    detector: LicenseDetector,
) -> None:
    """BUG: the marker candidates join after the hinted ones, skipping an ID
    already there; the hinted MIT has no text, so the heading's MIT, exact
    at 1.0, falls to the bottom."""
    plain = detector.detect(text=MIT, exclude=["MIT"])
    hinted = detector.detect(text=MIT, exclude=["MIT"], hint=["MIT"])
    assert (plain[0]["expression"], plain[0]["score"]) == ("MIT", 1.0)
    assert [r["expression"] for r in hinted][:3] == ["JSON", "X11", "MIT-0"]
    mit = next(r for r in hinted if r["expression"] == "MIT")
    assert mit["score"] < 0.1


def test_a_hint_buries_a_licence_its_heading_names(
    detector: LicenseDetector,
) -> None:
    """BUG: with no exclude too. only_common drops JSON from the full-text
    candidates; its heading brings it back, exact; a hint for it replaces
    that candidate with one that has no text, so JSON falls to the bottom."""
    text = _fixture_text("JSON")  # starts "JSON License"
    assert answers(detector, text=text)[0] == "JSON"
    assert answers(detector, text=text, only_common=True)[0] == "JSON"
    hinted = detector.detect(text=text, only_common=True, hint=["JSON"])
    assert [r["expression"] for r in hinted].count("JSON") == 1
    assert hinted[-1]["expression"] == "JSON"
    assert hinted[-1]["score"] < 0.1


MIXED = PROSE * 2 + "Licensed under the MIT License, see below.\n" + PROSE


def test_a_hint_can_skip_the_search_of_mixed_content(
    detector: LicenseDetector,
) -> None:
    """BUG: mixed content with under 5 full-text candidates is searched by
    section too (detector._run_tier1_and_tier2); a hinted candidate counts
    towards the 5, so a hint stops that search, and what it found goes."""
    plain = answers(detector, text=MIXED)
    hinted = answers(detector, text=MIXED, hint=[GPL])
    assert plain[-2:] == [GPL, "GPL-2.0"]
    assert hinted[-1] == GPL and "GPL-2.0" not in hinted
    assert detector.detect(text=MIXED, hint=[GPL])[-1]["score"] == 0


@pytest.mark.parametrize(
    ("text", "top"),
    [
        # BUG: the heading's marker candidate joins after the filter.
        (MIT, "MIT"),
        ("MIT License\n\n" + PROSE * 3, "MIT"),
        # BUG: a short-text window of mixed content is no Tier 1 candidate.
        (MIXED, None),
    ],
    ids=["heading_and_text", "heading_and_prose", "mixed_window"],
)
def test_exclude_misses_what_joins_after_the_filter(
    detector: LicenseDetector, text: str, top: str | None
) -> None:
    excluded = answers(detector, text=text, exclude=["MIT"], only_common=True)
    assert "MIT" in excluded
    if top is not None:
        assert excluded[0] == top


# Inputs answered before Tier 1: the options are checked, then not read.
WHOLE_INPUTS = {
    "license_id": {"license_id": "MIT"},
    "id": {"text": "MIT"},
    "name": {"text": "MIT License"},
    "expression": {"text": "MIT OR X11"},
    "tag": {"text": PROSE + "SPDX-License-Identifier: MIT\n"},
    "manifest": {"text": '{"license": "MIT"}'},
    "url": {"text": MIT_URL},
}
EVERY_OPTION: dict[str, Any] = {
    "exclude": ["MIT", "X11", "Acme-MIT"],
    "hint": [GPL, "JSON"],
    "only_common": True,
    "only_spdx": False,
    "enable_popularity": True,
}


@pytest.mark.parametrize("kwargs", WHOLE_INPUTS.values(), ids=list(WHOLE_INPUTS))
@pytest.mark.parametrize("name", [*EVERY_OPTION, "all"])
def test_an_input_answered_whole_ignores_the_options(
    detector: LicenseDetector, kwargs: dict[str, Any], name: str
) -> None:
    options = EVERY_OPTION if name == "all" else {name: EVERY_OPTION[name]}
    plain = detector.detect(**kwargs)
    assert plain[0]["expression"] in {"MIT", "MIT OR X11"}
    assert detector.detect(**kwargs, **options) == plain


def test_a_short_text_with_no_answer_ignores_a_hint(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    """Under 10 words and unread, it never reaches Tier 1, where hint acts."""
    assert answers(detector, text="the widget scheduler", hint=[GPL]) == []
    assert "too few words for text" in given.lines()


EMPTY: list[Any] = [[], (), set(), frozenset()]


@pytest.mark.parametrize("empty", EMPTY, ids=lambda v: type(v).__name__)
@pytest.mark.parametrize("name", ["exclude", "hint"])
def test_an_empty_collection_is_no_option(
    detector: LicenseDetector, name: str, empty: object
) -> None:
    assert answers(detector, text=BODY, **{name: empty}) == NEAR


@pytest.mark.parametrize("kind", [list, tuple, set, frozenset])
def test_every_collection_kind_answers_alike(
    detector: LicenseDetector, kind: type[Any]
) -> None:
    got = answers(detector, text=BODY, exclude=kind(["MIT"]), hint=kind([GPL]))
    assert got == [*NEAR[1:], GPL]


def test_the_order_of_the_ids_does_not_change_the_answer(
    detector: LicenseDetector,
) -> None:
    """Hinted candidates all score 0 and sort by ID, as any tie does."""
    forward = answers(detector, text=BODY, hint=[GPL, "GPL-2.0"], exclude=NEAR[:2])
    backward = answers(detector, text=BODY, hint=["GPL-2.0", GPL], exclude=NEAR[1::-1])
    assert forward == backward == [*NEAR[2:], GPL, "GPL-2.0"]


class _Id(str):
    """A str subclass: an ID all the same."""


def test_a_str_subclass_is_an_id(detector: LicenseDetector) -> None:
    got = answers(detector, text=BODY, exclude=[_Id("MIT")], hint=[_Id(GPL)])
    assert got == [*NEAR[1:], GPL]


def _ids() -> Generator[str, None, None]:
    yield "MIT"


NO_ID_LISTS: dict[str, object] = {
    "str_subclass": _Id("MIT"),  # a bare ID, even a str subclass
    "bytes": [b"MIT"],
    "dict": {"MIT": 1},  # no collection of IDs, whatever its keys
    "dict_keys": {"MIT": 1}.keys(),
    "generator": _ids(),  # refused before it is read
    "none": [None],
    "nested": [["MIT"]],
    "bool": True,
}


@pytest.mark.parametrize("value", NO_ID_LISTS.values(), ids=list(NO_ID_LISTS))
@pytest.mark.parametrize("name", ["exclude", "hint"])
def test_a_list_option_of_another_type_is_refused(
    detector: LicenseDetector, name: str, value: Any
) -> None:
    with pytest.raises(TypeError, match=f"^{name} must be a list of str$"):
        detector.detect(text=BODY, **{name: value})


@pytest.mark.parametrize("value", [0, 1, "true", None, [True]])
@pytest.mark.parametrize("name", ["only_common", "only_spdx", "enable_popularity"])
def test_a_flag_of_another_type_is_refused(
    detector: LicenseDetector, name: str, value: Any
) -> None:
    with pytest.raises(TypeError, match=f"^{name} must be bool, not "):
        detector.detect(text=BODY, **{name: value})


@pytest.mark.parametrize("predicate", ["is_spdx", "is_osi", "is_fsf"])
@pytest.mark.parametrize("name", sorted(EVERY_OPTION))
def test_a_predicate_takes_no_option(
    detector: LicenseDetector, predicate: str, name: str
) -> None:
    """DECISION: is_*() answer from detect() without its options."""
    check = getattr(detector, predicate)
    with pytest.raises(TypeError, match=f"unexpected keyword argument '{name}'"):
        check(text=BODY, **{name: EVERY_OPTION[name]})


# --- The options as axes (tests/test_option_matrix.py lists this surface) ---

# A text that reaches Tiers 1 and 2 with a tie (JSON, MIT and MIT-0), so
# every option changes its answer; the ID is answered whole, whatever they say.
TIE = "the widget scheduler keeps a queue of pending widgets and dispatches them"
TIE += " to worker threads"
TIED = ["X11", "JSON", "MIT", "MIT-0"]
OPTION_ANSWERS: dict[str, tuple[dict[str, Any], list[str]]] = {
    "none": ({}, TIED),
    "exclude": ({"exclude": ["MIT"]}, ["X11", "JSON", "MIT-0"]),
    "exclude_case": ({"exclude": ("mit",)}, TIED),  # exact case only
    "hint": ({"hint": {GPL}}, [*TIED, GPL]),
    "exclude_hint": (
        {"exclude": ["MIT"], "hint": ["MIT"]},
        [*TIED[:2], "MIT-0", "MIT"],
    ),
    "only_common": ({"only_common": True}, ["X11", "MIT", "MIT-0"]),
    "only_spdx": ({"only_spdx": False}, ["X11", "Acme-MIT", *TIED[1:]]),
    "enable_popularity": ({"enable_popularity": True}, ["X11", "MIT-0", "MIT", "JSON"]),
}
WHERE = list(
    itertools.product(["text", "license_id", "file_path"], ["method", "function"])
)


@pytest.mark.parametrize("where", WHERE, ids="-".join)
@pytest.mark.parametrize("option", list(OPTION_ANSWERS))
def test_api_option_matrix(
    db_path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    where: tuple[str, str],
) -> None:
    """``LicenseDetector.detect`` and ``licenseid.detect`` take each option
    on each input, and answer alike."""
    options, text_answer = OPTION_ANSWERS[option]
    name, entry = where
    path = tmp_path / "LICENSE"
    path.write_text(TIE, encoding="utf-8")
    inputs: dict[str, Any] = {"text": TIE, "license_id": "MIT"}
    value = inputs.get(name, str(path))
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: db_path)
    call = LicenseDetector(db_path).detect if entry == "method" else licenseid.detect
    results = call(**{name: value}, **options)
    expected = ["MIT"] if name == "license_id" else text_answer
    assert [r["expression"] for r in results] == expected


def test_the_function_hands_every_option_to_the_method(
    db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: db_path)
    with mock.patch.object(
        LicenseDetector, "detect", autospec=True, return_value=[]
    ) as spy:
        licenseid.detect(TIE, **EVERY_OPTION)
    spy.assert_called_once_with(
        mock.ANY, TIE, license_id=None, file_path=None, **EVERY_OPTION
    )

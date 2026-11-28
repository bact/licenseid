# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where the options of ``detect()`` act, pinned as they are (roadmap
item 46).

Characterization tests: they pin today's answers, right or wrong. A pin
marked ``# BUG:`` is a suspected bug, ``# DECISION:`` a behaviour to keep or
change on purpose; fixing either moves the pin. ``exclude``, ``only_common``
and ``only_spdx`` filter the score table of Tier 1 before its selection
(``licenseid.retrieval.get_candidates``, ``licenseid.gramselect``), so the
rows are the selection among what may answer; ``hint`` adds its IDs last,
with their text, through the same filters (``retrieval.hinted_candidates``).
``enable_popularity`` acts in the Tier 2 ranking and its tie-breaker, on every
candidate (more in ``tests/test_match_ordering.py``).

MIT, MIT-0, JSON, X11 and Acme-MIT carry their real text, as AGENTS.md asks:
a row with no ``search_text`` never reaches Tiers 1 and 2, so a filter test
on it passes trivially. The GPL rows carry only their names: a hint adds
them.
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
from conftest import FoundRows, GivenWarnings
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
    Lic("GPL-2.0-only", GPL_ONLY, True, True, True, search_text=GPL_ONLY.lower()),
    Lic(
        "GPL-2.0",
        "GNU General Public License v2.0",
        is_deprecated=True,
        superseded_by="GPL-2.0-only",
        search_text="gnu general public license v2.0",
    ),
)


# Not on the List: what only_spdx (on by default) drops. A database licenseid
# builds has no such row, so there only_spdx does nothing. It sits in a
# database of its own: dropped, a text that near is the bar under which no
# other text answers (``gramselect.beyond_bar``).
OFF_LIST = Lic("Acme-MIT", "Acme MIT Licence", False, search_text=normalize_text(ACME))


# Popularity, different for each row, so enable_popularity reorders a tie.
POPULARITY = {"Acme-MIT": 2000, "MIT-0": 1000, "MIT": 50, "X11": 5, "JSON": 1}


def _seeded(prefix: str, rows: tuple[Lic, ...]) -> Generator[str, None, None]:
    urls = [("MIT", False, MIT_URL)]
    for path in seeded_db(prefix, rows, urls=urls):
        with sqlite3.connect(path, uri=True) as conn:
            conn.executemany(
                "UPDATE licenses SET pop_score = ? WHERE license_id = ?",
                [(pop, lic) for lic, pop in POPULARITY.items()],
            )
        yield path


@pytest.fixture(scope="module")
def db_path() -> Generator[str, None, None]:
    yield from _seeded("test_detect_options_paths", ROWS)


@pytest.fixture(scope="module")
def off_list_path() -> Generator[str, None, None]:
    yield from _seeded("test_detect_options_paths_off_list", (*ROWS, OFF_LIST))


@pytest.fixture(scope="module")
def off_list_detector(off_list_path: str) -> LicenseDetector:
    return LicenseDetector(off_list_path)


@pytest.fixture(scope="module")
def detector(db_path: str) -> LicenseDetector:
    return LicenseDetector(db_path)


def answers(detector: LicenseDetector, **kwargs: Any) -> list[str]:
    return [r["expression"] for r in detector.detect(**kwargs)]


# BODY's answers, best first: BODY holds MIT's text whole, so Tier 2 scores
# MIT and the three runner-ups by gram score (whole text first), which rank
# under it: FOUND. NEAR is the top 3 by gram score (X11 is fourth, over 0.05
# under MIT). With MIT excluded, no text of the rest shares as much of BODY as
# MIT does, so none answers (``gramselect.beyond_bar``).
NEAR = ["MIT", "JSON", "MIT-0"]
FOUND = [*NEAR, "X11"]
GPL = "GPL-2.0-only"


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, FOUND),
        ({"exclude": ["MIT"]}, []),
        # DECISION: exclude and hint both fold case (IDs are case-insensitive).
        ({"exclude": ["mit"]}, []),
        # A text that shares less than the one left out is no candidate.
        ({"exclude": ["JSON"]}, ["MIT"]),
        ({"exclude": ["X11"]}, FOUND[:3]),
        ({"exclude": ["Nope-1.0"]}, FOUND),
        ({"exclude": FOUND}, []),
        ({"hint": ["MIT"]}, FOUND),  # already a candidate: nothing added
        ({"hint": ["Nope-1.0"]}, FOUND),  # no row: nothing added
        ({"hint": [GPL]}, [*FOUND, GPL]),  # added last, scored on its text
        ({"hint": ["gpl-2.0-only"]}, [*FOUND, GPL]),
        ({"hint": ["mit"]}, FOUND),  # folded: already a candidate
        ({"hint": [GPL, GPL]}, [*FOUND, GPL]),  # an ID given twice, once
        ({"hint": [GPL, "gpl-2.0-only"]}, [*FOUND, GPL]),
        # DECISION: every filter wins: a hint is a candidate that passes
        # them, so it never undoes exclude.
        ({"exclude": ["MIT"], "hint": ["MIT"]}, []),
        # only_common takes JSON out (0.9547 on BODY): MIT-0 and X11 share
        # less of BODY than JSON, which is no candidate, so they go too.
        ({"only_common": True}, ["MIT"]),
        # Nor does a hint pass only_common or only_spdx (on by default).
        ({"only_common": True, "hint": ["JSON"]}, ["MIT"]),
        ({"only_spdx": False}, FOUND),  # no off-list row here
        ({"hint": ["Acme-MIT"]}, FOUND),  # no row: nothing added
        ({"only_common": True, "exclude": ["MIT"]}, []),
        # No tie here, so popularity (a nudge of 1e-4 at most) moves nothing.
        ({"enable_popularity": True}, FOUND),
    ],
    ids=repr,
)
def test_the_options_shape_the_text_candidates(
    detector: LicenseDetector, options: dict[str, Any], expected: list[str]
) -> None:
    assert answers(detector, text=BODY, **options) == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        # Acme-MIT (0.9968) is off the List: only_spdx takes it out, and what
        # shares less of BODY than it is no candidate. A database licenseid
        # builds has no such row.
        ({}, ["MIT"]),
        ({"only_spdx": True, "hint": ["Acme-MIT"]}, ["MIT"]),
        ({"hint": ["Acme-MIT"]}, ["MIT"]),  # only_spdx is on by default
        # Acme-MIT (0.99) is the first runner-up: X11 is no longer one.
        ({"only_spdx": False}, ["MIT", "Acme-MIT", "JSON", "MIT-0"]),
        (
            {"only_spdx": False, "hint": ["Acme-MIT"]},
            ["MIT", "Acme-MIT", "JSON", "MIT-0"],
        ),
    ],
    ids=repr,
)
def test_an_off_list_text_is_a_text_a_filter_takes_out(
    off_list_detector: LicenseDetector, options: dict[str, Any], expected: list[str]
) -> None:
    assert answers(off_list_detector, text=BODY, **options) == expected


def test_a_hinted_candidate_scores_on_its_own_text(
    detector: LicenseDetector,
) -> None:
    """DECISION: a hint is added with its ``search_text``, so it ranks on its
    own similarity, not at 0: it never lifts a licence above the text's own."""
    hinted = detector.detect(text=BODY, hint=[GPL])[-1]
    assert (hinted["expression"], hinted["exact"]) == (GPL, False)
    assert 0 < hinted["score"] < 0.5


def test_exclude_wins_over_a_hint_for_a_marker_licence_too(
    detector: LicenseDetector,
) -> None:
    """exclude drops the heading's MIT (a prose marker is free text), and a
    hint for it adds nothing back."""
    plain = detector.detect(text=MIT, exclude=["MIT"])
    hinted = detector.detect(text=MIT, exclude=["MIT"], hint=["MIT"])
    assert "MIT" not in [r["expression"] for r in plain]
    assert hinted == plain


def test_a_hint_keeps_the_licence_its_heading_names(
    detector: LicenseDetector,
) -> None:
    """only_common drops JSON from the full-text candidates; its heading
    brings it back, exact; a hint for it is dropped by only_common as well,
    so the heading's candidate (with its text) stays first."""
    text = _fixture_text("JSON")  # starts "JSON License"
    assert answers(detector, text=text)[0] == "JSON"
    plain = detector.detect(text=text, only_common=True)
    hinted = detector.detect(text=text, only_common=True, hint=["JSON"])
    assert plain[0]["expression"] == "JSON"
    assert hinted == plain
    assert (hinted[0]["score"], hinted[0]["exact"]) == (1.0, True)


@pytest.mark.parametrize(
    "text",
    [MIT, "MIT License\n\n" + PROSE * 3],
    ids=["heading_and_text", "heading_and_prose"],
)
def test_exclude_drops_what_free_text_names_outside_tier_1(
    detector: LicenseDetector, text: str
) -> None:
    """A heading's marker candidate is free text, as Tier 1's candidates
    are: exclude drops it."""
    assert "MIT" in answers(detector, text=text, only_common=True)
    assert "MIT" not in answers(detector, text=text, exclude=["MIT"], only_common=True)


GPL_BODY = GPL_ONLY + "\n" + PROSE * 2  # a title the prose markers read


@pytest.mark.parametrize(
    ("exclude", "gone"),
    [
        ([GPL], {GPL}),
        ([GPL, "gpl-2.0-only"], {GPL}),
    ],
    ids=["twin", "folded"],
)
@pytest.mark.filterwarnings("ignore::licenseid.LicenseIdWarning")
def test_exclude_drops_a_licence_named_by_a_title(
    detector: LicenseDetector, exclude: list[str], gone: set[str]
) -> None:
    """The prose markers (a title, "version 2") are free text: excluded, the
    licence is no answer (it stayed one, at 0.836)."""
    assert GPL in answers(detector, text=GPL_BODY)
    assert gone.isdisjoint(answers(detector, text=GPL_BODY, exclude=exclude))


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
    assert answers(detector, text=BODY, **{name: empty}) == FOUND


@pytest.mark.parametrize("kind", [list, tuple, set, frozenset])
def test_every_collection_kind_answers_alike(
    detector: LicenseDetector, kind: type[Any]
) -> None:
    got = answers(detector, text=BODY, exclude=kind(["MIT"]), hint=kind([GPL]))
    assert got == [GPL]  # no text of the rest answers; the hint is added last


def test_the_order_of_the_ids_does_not_change_the_answer(
    detector: LicenseDetector,
) -> None:
    """Hinted candidates are added last, in no order that ranks them."""
    forward = answers(detector, text=BODY, hint=[GPL, "MIT"], exclude=NEAR[:2])
    backward = answers(detector, text=BODY, hint=["MIT", GPL], exclude=NEAR[1::-1])
    assert forward == backward == [GPL]


class _Id(str):
    """A str subclass: an ID all the same."""


def test_a_str_subclass_is_an_id(detector: LicenseDetector) -> None:
    got = answers(detector, text=BODY, exclude=[_Id("MIT")], hint=[_Id(GPL)])
    assert got == [GPL]


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

# A text that reaches Tiers 1 and 2 with a tie (JSON, MIT and MIT-0 hold its
# words alike), so every option changes its answer; the ID is answered whole,
# whatever they say. The first 40 words of the disclaimer, one word changed.
TIE = " ".join(BODY.split("\n\n")[3].split()[:40]).replace("KIND", "SORT")
TIED = ["JSON", "MIT", "MIT-0"]
OPTION_ANSWERS: dict[str, tuple[dict[str, Any], list[str]]] = {
    "none": ({}, TIED),
    # The tie holds: JSON and MIT-0 score as MIT does, X11 less.
    "exclude": ({"exclude": ["MIT"]}, ["JSON", "MIT-0"]),
    "exclude_case": ({"exclude": ("mit",)}, ["JSON", "MIT-0"]),  # folded
    "hint": ({"hint": {GPL}}, [*TIED, GPL]),
    "exclude_hint": ({"exclude": ["MIT"], "hint": ["MIT"]}, ["JSON", "MIT-0"]),
    "only_common": ({"only_common": True}, ["MIT", "MIT-0"]),
    "only_spdx": ({"only_spdx": False}, ["Acme-MIT", *TIED]),
    "enable_popularity": ({"enable_popularity": True}, ["MIT-0", "MIT", "JSON"]),
}
WHERE = list(
    itertools.product(["text", "license_id", "file_path"], ["method", "function"])
)


@pytest.mark.parametrize("where", WHERE, ids="-".join)
@pytest.mark.parametrize("option", list(OPTION_ANSWERS))
def test_api_option_matrix(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    where: tuple[str, str],
) -> None:
    """``LicenseDetector.detect`` and ``licenseid.detect`` take each option
    on each input, and answer alike."""
    options, text_answer = OPTION_ANSWERS[option]
    # Only the only_spdx row has an off-list text to take out.
    db_path = request.getfixturevalue(
        "off_list_path" if option == "only_spdx" else "db_path"
    )
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


@pytest.mark.parametrize("name", [*EVERY_OPTION, "all"])
def test_texts_ignores_every_option_that_filters_candidates(
    db_path: str, found_rows: FoundRows, name: str
) -> None:
    """TEXTS is a fact about the input: the corpus holds every row, the
    search is the same, and each result has the same list, whatever the
    options leave of the candidates (the answer may change, not the texts)."""
    found_rows.rows = ["MIT", "X11"]
    options = EVERY_OPTION if name == "all" else {name: EVERY_OPTION[name]}
    detector = LicenseDetector(db_path)  # not the module's: it keeps a corpus
    text = MIT + " Acme words"
    results = detector.detect(text=text, **options)
    if name in ("exclude", "all"):
        # MIT, the best text, is out: no other text answers (the hint, added
        # last, does), and TEXTS still names it.
        assert [r["expression"] for r in results] == (
            ["GPL-2.0-only"] * (name == "all")
        )
        assert detector.texts(text) == ["MIT", "X11"]
    else:
        assert results, name
        assert {tuple(r["texts"] or ()) for r in results} == {("MIT", "X11")}
    (rows,) = found_rows.built
    assert {row.license_id for row in rows} == {
        "MIT",
        "MIT-0",
        "JSON",
        "X11",
        "GPL-2.0-only",
        "GPL-2.0",
    }  # the deprecated one too: here it has a text
    # Several texts found: the search with no answer, then the answer's.
    assert {norm for norm, _ in found_rows.calls} == {
        normalize_text(MIT + " Acme words")
    }

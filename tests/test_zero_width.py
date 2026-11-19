# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A zero-width character at an end of a value is white space; any other
hidden character there is a cut.

``MIT\\u200b`` is ``MIT`` as written, as ``MIT `` is: the six zero-width
characters (:data:`licenseid.hiddenchars.ZERO_WIDTH`) carry no text and
reorder nothing, so they are trimmed (category ``lexical``, exact). A bidi
control, a control character, a run of Unicode tag characters (invisible
ASCII) or any other format character is still left off, but as a cut
(``separator``, not exact). Every channel agrees: the argument, a tag, and
a JSON, TOML or INI field. No answer changes.
"""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.hiddenchars import ZERO_WIDTH, only_zero_width

#: The six zero-width characters, by name.
ZERO = {
    "ZWSP": "\u200b",
    "ZWNJ": "\u200c",
    "ZWJ": "\u200d",
    "WJ": "\u2060",
    "BOM": "\ufeff",
    "SHY": "\u00ad",
}
ZWSP, LRM, RLO = "\u200b", "\u200e", "\u202e"
#: ``MIT`` followed by "GPL-3.0 applies" in Unicode tag characters.
SMUGGLED = "".join(chr(0xE0000 + ord(c)) for c in "GPL-3.0 applies")

#: Where a zero-width character *z* stands, and the answer.
PLACES: dict[str, tuple[Callable[[str], str], str]] = {
    "end": (lambda z: f"MIT{z}", "MIT"),
    "start": (lambda z: f"{z}MIT", "MIT"),
    "quoted": (lambda z: f'"MIT{z}"', "MIT"),
    "space-after": (lambda z: f"MIT {z}", "MIT"),
    "space-before": (lambda z: f"{z} MIT", "MIT"),
    "inside": (lambda z: f"MIT{z} OR ISC", "ISC OR MIT"),
    "compound": (lambda z: f"MIT OR ISC{z}", "ISC OR MIT"),
}

#: Still left off, but a cut: ``separator``, not exact, in every channel.
CUT = {
    "tag-chars": f"MIT{SMUGGLED}",
    "LRM": f"MIT{LRM}",
    "RLO": f"MIT{RLO}",
    "BEL": "MIT\x07",
    "US": "MIT\x1f",
    "C1-quotes": "\x93MIT\x94",
    "mixed": f"MIT{ZWSP}{LRM}",
    "mixed-start": f"{ZWSP}MIT{LRM}",
    "spaced-tag-char": f"MIT {chr(0xE0041)}",
}

#: Refused as before, whatever the character.
REFUSED = {
    "RLO-start": f"{RLO}MIT",
    "in-word": f"M{ZWSP}IT",
    "NUL": "MIT\x00",
}


def _toml(value: str) -> str:
    """*value* as a TOML basic string, every character outside printable
    ASCII escaped."""
    out = []
    for char in value:
        if char in '"\\':
            out.append("\\" + char)
        elif " " <= char <= "~":
            out.append(char)
        elif ord(char) > 0xFFFF:
            out.append(f"\\U{ord(char):08X}")
        else:
            out.append(f"\\u{ord(char):04X}")
    return '"' + "".join(out) + '"'


#: Each channel: a file name (None for a text) and the input of a value.
CHANNELS: dict[str, tuple[str | None, Callable[[str], str]]] = {
    "argument": (None, lambda v: v),
    "tag": (None, lambda v: f"# SPDX-License-Identifier: {v}\n"),
    "json": ("package.json", lambda v: json.dumps({"name": "x", "license": v})),
    "toml": ("Cargo.toml", lambda v: f'[package]\nname = "x"\nlicense = {_toml(v)}\n'),
    "ini": ("setup.cfg", lambda v: f"[metadata]\nname = x\nlicense = {v}\n"),
}


def _detect(db_path: str, tmp_path: Path, channel: str, value: str) -> list[object]:
    name, shape = CHANNELS[channel]
    detector = LicenseDetector(db_path)
    if name is None:
        found = detector.detect(text=shape(value))
    else:
        path = tmp_path / name
        path.write_text(shape(value), encoding="utf-8")
        found = detector.detect(file_path=str(path))
    return [(f["expression"], f["exact"]) for f in found]


def _details(value: str, db: LicenseDatabase) -> list[str | None]:
    return [s["detail"] for s in resolve(value, db)["steps"] if s["kind"] == "trim"]


ZERO_CASES = [
    pytest.param(place, z, id=f"{name}-{place}")
    for name, z in ZERO.items()
    for place in PLACES
]


@pytest.mark.parametrize(("place", "char"), ZERO_CASES)
def test_resolve_reads_a_zero_width_character_as_white_space(
    corpus_db: LicenseDatabase, place: str, char: str
) -> None:
    shape, answer = PLACES[place]
    got = resolve(shape(char), corpus_db)
    assert (got["expression"], got["category"]) == (answer, "lexical")
    assert "zero-width characters" in _details(shape(char), corpus_db)
    assert "invisible characters" not in _details(shape(char), corpus_db)


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize(("place", "char"), ZERO_CASES)
def test_a_zero_width_character_is_exact_in_every_channel(
    corpus_db: LicenseDatabase, tmp_path: Path, channel: str, place: str, char: str
) -> None:
    shape, answer = PLACES[place]
    found = _detect(corpus_db.location, tmp_path, channel, shape(char))
    assert found == [(answer, True)]


@pytest.mark.parametrize("value", CUT.values(), ids=CUT.keys())
def test_resolve_reads_another_hidden_character_as_a_cut(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == ("MIT", "separator")
    assert got["trust"] == "resolver_rule"
    assert "invisible characters" in _details(value, corpus_db)


CUT_CASES = [
    pytest.param(value, channel, id=f"{name}-{channel}")
    for name, value in CUT.items()
    for channel in CHANNELS
    if (name, channel) != ("US", "ini")  # pinned below
]


@pytest.mark.parametrize(("value", "channel"), CUT_CASES)
def test_another_hidden_character_is_inexact_in_every_channel(
    corpus_db: LicenseDatabase, tmp_path: Path, channel: str, value: str
) -> None:
    assert _detect(corpus_db.location, tmp_path, channel, value) == [("MIT", False)]


#: Inside the value, beside white space: made a space, but a cut.
CUT_INSIDE = {
    "tag-char": f"MIT{chr(0xE0041)} OR ISC",
    "function-application": "MIT OR \u2061ISC",
    "mixed": f"MIT OR{ZWSP}{chr(0xE0041)} ISC",
}


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("value", CUT_INSIDE.values(), ids=CUT_INSIDE.keys())
def test_another_format_character_beside_white_space_is_a_cut(
    corpus_db: LicenseDatabase, tmp_path: Path, channel: str, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == ("ISC OR MIT", "separator")
    assert _details(value, corpus_db) == ["invisible characters"]
    found = _detect(corpus_db.location, tmp_path, channel, value)
    assert found == [("ISC OR MIT", False)]


def test_an_ini_field_loses_a_separator_control_before_it_is_read(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    # BUG: configparser strips U+001C to U+001F as white space (str.strip),
    # so the field reads `MIT` as written; `--id 'MIT\x1f'` does the same.
    assert _detect(corpus_db.location, tmp_path, "ini", "MIT\x1f") == [("MIT", True)]


@pytest.mark.parametrize("value", REFUSED.values(), ids=REFUSED.keys())
def test_a_hidden_character_that_says_something_stays_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None
    assert not LicenseDetector(corpus_db.location).detect(text=value)
    assert given.conditions() <= {"too few words for text"}


def test_the_trim_step_names_zero_width_characters(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve(f'"{ZWSP}MIT"', corpus_db)
    assert [(s["kind"], s["from"], s["to"], s["detail"]) for s in got["steps"]] == [
        ("unquote", f'"{ZWSP}MIT"', f"{ZWSP}MIT", "balanced"),
        ("trim", f"{ZWSP}MIT", "MIT", "zero-width characters"),
    ]
    assert got["trust"] == resolve('"MIT"', corpus_db)["trust"]


@pytest.mark.parametrize(
    ("removed", "only"),
    [
        ("", True),
        (" \t", True),
        ("".join(ZERO.values()), True),
        (f" {ZWSP} ", True),
        (LRM, False),
        (f"{ZWSP}{LRM}", False),
        ("\x07", False),
        ("\x1f", False),
        (chr(0xE0041), False),
        ("\u2061", False),  # a format character outside the six
        ("x", False),
    ],
    ids=lambda v: ascii(v)[:20],
)
def test_only_zero_width(removed: str, only: bool) -> None:
    assert only_zero_width(removed) is only


def test_the_six_zero_width_characters() -> None:
    assert ZERO_WIDTH == frozenset(ZERO.values())


# Each with a short text to search, as a real row has: a value that falls
# through to Tiers 1 and 2 must meet its near neighbours there.
NAMES = {
    "MIT": "MIT License",
    "MIT-0": "MIT No Attribution",
    "ISC": "ISC License",
    "0BSD": "BSD Zero Clause License",
}
ROWS = tuple(
    Lic(lic_id, name, is_osi_approved=True, search_text=f"{lic_id} {name}".lower())
    for lic_id, name in NAMES.items()
)


@pytest.fixture(name="db_path")
def _db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_zero_width", ROWS)


@pytest.mark.parametrize(
    ("value", "exact"),
    [
        (f"MIT{ZWSP}", True),
        ("\ufeffMIT-0", True),
        (f"MIT-0{ZWSP}", True),
        ("MIT\x07", False),
        (f"MIT-0{LRM}", False),
        (f"ISC{SMUGGLED}", False),
    ],
    ids=lambda v: ascii(v)[:20],
)
def test_detect_says_exact_on_a_seeded_database(
    db_path: str, tmp_path: Path, value: str, exact: bool
) -> None:
    answer = value.strip("".join(ZERO.values()) + "\x07" + LRM + SMUGGLED)
    for channel in CHANNELS:
        assert _detect(db_path, tmp_path, channel, value) == [(answer, exact)]

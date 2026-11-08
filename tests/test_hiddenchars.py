# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A control or format character at an end of a declared value is left off
(``licenseid.hiddenchars``, 0.8.1); inside the value, first as a bidi
control, or alone, it is still refused. Unit table of ``strip_hidden``, the
``resolve()`` table, the length gate, and the CLI.
"""
# pylint: disable=missing-function-docstring

import json
import time

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.hiddenchars import (
    BIDI_CONTROLS,
    is_hidden,
    space_out_hidden,
    strip_hidden,
)
from licenseid.resolver import MAX_EXPRESSION_CHARS, read_length
from licenseid.result import json_line

ZWSP, ZWNJ, BOM, SHY, WJ = "\u200b", "\u200c", "\ufeff", "\u00ad", "\u2060"
LRM, RLM, RLO, RLI = "\u200e", "\u200f", "\u202e", "\u2067"


def _id(value: object) -> str:
    return ascii(value)[:40]


# --- strip_hidden ------------------------------------------------------------

#: ``{value: (shown, lead)}``
STRIPPED = [
    (f"MIT{ZWSP}", ("MIT", 0)),
    (f"{BOM}MIT", ("MIT", 1)),
    (f"{ZWSP}{BOM}{WJ}MIT{SHY}", ("MIT", 3)),
    (f"MIT{LRM}{RLM}", ("MIT", 0)),  # a bidi control last has nothing to reorder
    (f"MIT{RLO}", ("MIT", 0)),
    (f"MIT{RLI}", ("MIT", 0)),
    ("MIT\x07", ("MIT", 0)),
    ("\x1fMIT\x1c", ("MIT", 1)),
    (f" {ZWSP} MIT", ("MIT", 3)),  # the offset counts the white space beside
    (f"MIT {ZWSP} ", ("MIT", 0)),
    (f"\t{BOM}MIT{ZWSP}\n", ("MIT", 2)),
    (f"M{ZWSP}IT{ZWSP}", (f"M{ZWSP}IT", 0)),  # inside: left for the caller to refuse
    (f"MIT\x00{ZWSP}", ("MIT\x00", 0)),  # a NUL is never left off
]


@pytest.mark.parametrize(("value", "expected"), STRIPPED, ids=_id)
def test_hidden_characters_at_the_ends_are_left_off(
    value: str, expected: tuple[str, int]
) -> None:
    assert strip_hidden(value) == expected


#: Returned as it is: nothing hidden at an end, one of nothing else, a bidi
#: control at the start, a NUL, white space only.
UNCHANGED = [
    "",
    "MIT",
    " MIT ",  # white space alone is the caller's (`trim`), not this one's
    "MIT\u00a0\x85",
    f"M{ZWSP}IT",
    ZWSP,
    f" {ZWSP} {BOM}",
    f"{RLO}MIT",
    f"{LRM}MIT",
    f"{ZWSP}{RLO}MIT",  # a bidi control after other hidden ones is still first
    f" {RLM}MIT{ZWSP}",
    "MIT\x00",
    "\x00MIT",
    "\x00",
]


@pytest.mark.parametrize("value", UNCHANGED, ids=_id)
def test_a_value_to_refuse_or_to_keep_comes_back_as_it_is(value: str) -> None:
    shown, lead = strip_hidden(value)
    assert shown is value
    assert lead == 0


@pytest.mark.parametrize(
    ("char", "hidden"),
    [
        (ZWSP, True),
        (BOM, True),
        (SHY, True),
        (RLO, True),
        ("\x07", True),
        ("\x1f", True),  # an information separator is no white space here
        ("\x00", False),  # NUL: binary
        (" ", False),
        ("\t", False),
        ("\xa0", False),
        ("\x85", False),
        ("\u3000", False),
        ("M", False),
        ("\udcff", False),  # a lone surrogate (Cs) is refused as it is
    ],
    ids=_id,
)
def test_what_is_hidden(char: str, hidden: bool) -> None:
    assert is_hidden(char) is hidden


def test_the_bidi_controls_are_format_characters() -> None:
    assert len(BIDI_CONTROLS) == 12
    assert all(is_hidden(char) for char in BIDI_CONTROLS)


# --- resolve() -----------------------------------------------------------------

#: A value that reads as MIT with its hidden characters left off.
READ = [
    f"MIT{ZWSP}",
    f"{ZWSP}MIT",
    f"{ZWSP}MIT{ZWSP}",
    f"MIT{ZWNJ}",
    f"{ZWNJ}MIT",
    f"MIT{BOM}",
    f"{BOM}MIT",
    f"MIT{SHY}",
    f"{SHY}MIT",
    f"MIT{WJ}",
    f"MIT{LRM}",
    f"MIT{RLM}",
    f"MIT{RLO}",
    f"MIT{RLI}",
    f"MIT{LRM}{RLO}",
    f"{ZWSP}{BOM}MIT",
    "MIT\x07",
    "\x07MIT",
    "MIT\x1f",
    f"  {ZWSP}  MIT  {ZWSP}  ",
]


@pytest.mark.parametrize("value", READ, ids=_id)
def test_a_value_with_hidden_characters_at_its_ends_reads(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        "MIT",
        "separator",
        "resolver_rule",
    )
    assert got["reason"] is None
    assert got["input"] == value
    assert got["steps"] == [
        {
            "kind": "trim",
            "applied": True,
            "from": value,
            "to": "MIT",
            "detail": "invisible characters",
            "list": None,
        }
    ]
    (operand,) = got["operands"]
    start, end = operand["span"]
    assert value[start:end] == "MIT"


#: ``{value: (expression, step kinds, spans)}``
BESIDE = {
    f'"MIT"{ZWSP}': ("MIT", ["trim", "unquote"], [[1, 4]]),
    f'{BOM}"MIT"': ("MIT", ["trim", "unquote"], [[2, 5]]),
    f"(MIT){BOM}": ("MIT", ["trim", "brackets"], [[1, 4]]),
    f'("MIT"){ZWSP}': ("MIT", ["trim", "brackets", "unquote"], [[2, 5]]),
    f"MIT OR ISC{ZWSP}": ("ISC OR MIT", ["trim", "reorder"], [[0, 3], [7, 10]]),
    f"{BOM}MIT AND ISC": ("ISC AND MIT", ["trim", "reorder"], [[1, 4], [9, 12]]),
    f"{ZWSP}(MIT OR ISC){RLO}": (
        "ISC OR MIT",
        ["trim", "brackets", "reorder"],
        [[2, 5], [9, 12]],
    ),
    f"https://spdx.org/licenses/MIT{ZWSP}": (
        "MIT",
        ["trim", "license_url"],
        [[0, 29]],
    ),
}


@pytest.mark.parametrize("value", BESIDE, ids=_id)
def test_quotes_brackets_operators_and_urls_read_beside_them(
    corpus_db: LicenseDatabase, value: str
) -> None:
    expression, kinds, spans = BESIDE[value]
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert [s["kind"] for s in got["steps"]] == kinds
    assert got["steps"][0]["detail"] == "invisible characters"
    assert got["steps"][0]["from"] == value
    assert got["trust"] == "resolver_rule"
    assert [o["span"] for o in got["operands"]] == spans
    for operand in got["operands"]:  # the span indexes the raw value
        start, end = operand["span"]
        assert value[start:end] == operand["text"]


def test_the_trim_of_white_space_alone_keeps_its_own_shape(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve(" MIT ", corpus_db)
    assert (got["category"], got["trust"]) == ("lexical", "identity")
    assert got["steps"][0]["detail"] is None


REFUSED = [
    (f"{RLO}MIT", "U+202E"),  # it shows other than it reads
    (f"{LRM}MIT", "U+200E"),
    (f"{ZWSP}{RLO}MIT", "U+200B"),
    (f" {RLI}MIT", "U+2067"),
    (f"M{ZWSP}IT", "U+200B"),
    (f"MIT{ZWSP}x", "U+200B"),
    (f'"MIT{ZWSP}"', "U+200B"),
    (f"MIT OR{RLO} Apache-2.0", "U+202E"),
    (f"MIT{ZWSP}{ZWSP}OR ISC", "U+200B"),  # touches no white space
    (f"MIT OR{RLO} ISC", "U+202E"),  # a bidi control is no space
    ("MIT OR\x07 ISC", "U+0007"),  # nor a control character
    (f"MIT{ZWSP}OR ISC", "U+200B"),
    (f"MIT\x07{ZWSP}\x07x", "U+0007"),
    (ZWSP, "U+200B"),  # nothing else
    (f" {ZWSP} {BOM}", "U+200B"),
    (RLO, "U+202E"),
    ("MIT\x00", "U+0000"),
    ("\x00MIT", "U+0000"),
    (f"{ZWSP}MIT\x00", "U+0000"),
    (f"MIT\x00{ZWSP}", "U+0000"),
]


@pytest.mark.parametrize(("value", "code"), REFUSED, ids=_id)
def test_a_value_to_refuse_is_still_refused(
    corpus_db: LicenseDatabase, value: str, code: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["category"] == "unresolved"
    assert got["reason"] == f"control or format character: {code}"
    assert got["steps"] == []


@pytest.mark.parametrize(
    "value", [f"{ZWSP}MIT\udcff", f"MIT{ZWSP}\udcff", f"\udcff{ZWSP}"], ids=_id
)
def test_a_lone_surrogate_beside_a_hidden_character_is_still_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, "lone surrogate")
    assert json_line(got)  # the result is writable: `input` shows U+FFFD


# --- the length gate -----------------------------------------------------------


def test_the_gate_counts_the_value_after_the_hidden_characters_are_left_off(
    corpus_db: LicenseDatabase,
) -> None:
    """2,001 hidden characters beside ``MIT`` are no length; 2,001 letters
    are, whatever hidden characters stand beside them."""
    over = MAX_EXPRESSION_CHARS + 1
    for value in (f"MIT{ZWSP * over}", f"{ZWSP * over}MIT", f"{BOM * over}MIT{RLO}"):
        assert read_length(value) == 3
        assert resolve(value, corpus_db)["expression"] == "MIT"
    long = "M" * over
    for value in (long, f"{long}{ZWSP}", f"{ZWSP}{long}"):
        assert read_length(value) == over
        got = resolve(value, corpus_db)
        assert got["reason"] == f"too long: {over} characters"
    edge = "M" * MAX_EXPRESSION_CHARS
    assert (
        resolve(f"{edge}{ZWSP}", corpus_db)["reason"] != f"too long: {over} characters"
    )


@pytest.mark.parametrize("where", ["after", "before"])
def test_a_long_run_of_hidden_characters_is_read_in_linear_time(
    corpus_db: LicenseDatabase, where: str
) -> None:
    size = 50_000
    value = f"MIT{ZWSP * size}" if where == "after" else f"{ZWSP * size}MIT"
    start = time.monotonic()
    got = resolve(value, corpus_db)
    assert got["expression"] == "MIT"
    assert time.monotonic() - start < max(2.0, size / 20_000)
    assert got["steps"][0]["from"] == value


# --- the command line ----------------------------------------------------------


def _run(db: LicenseDatabase, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["--db", db.location, *args])
    return result.exit_code, result.stdout, result.stderr


@pytest.mark.parametrize("value", [f"MIT{RLO}", f"{BOM}MIT", f"MIT{ZWSP}"], ids=_id)
def test_resolve_reads_a_value_with_a_hidden_character_at_an_end(
    corpus_db: LicenseDatabase, value: str
) -> None:
    code, out, err = _run(corpus_db, "resolve", value)
    assert (code, err) == (0, "")
    assert (
        out.splitlines()[0] == "EXPRESSION=MIT\tCATEGORY=separator\tTRUST=resolver_rule"
    )
    assert out.splitlines()[1] == f"STEP=trim\tFROM={value}\tTO=MIT"

    code, out, err = _run(corpus_db, "resolve", "--json", value)
    assert (code, err) == (0, "")
    assert out.count("\n") == 1  # one object, one line
    record = json.loads(out)
    assert (record["expression"], record["category"], record["input"]) == (
        "MIT",
        "separator",
        value,
    )
    assert record["steps"][0]["detail"] == "invisible characters"
    assert out == f"{json_line(record)}\n"  # RFC 8785, as written


def test_resolve_refuses_a_value_with_a_bidi_control_first(
    corpus_db: LicenseDatabase,
) -> None:
    code, out, err = _run(corpus_db, "resolve", f"{RLO}MIT")
    assert (code, err) == (1, "")
    assert out == (
        "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none\n"
        "REASON=control or format character: U+202E\n"
    )


def test_an_argument_over_the_limit_before_the_trim_is_read(
    corpus_db: LicenseDatabase,
) -> None:
    """The CLI counts the value as ``resolve()`` does (``read_length``): it
    cannot refuse as too long what the library reads."""
    code, out, err = _run(corpus_db, "resolve", f"MIT{ZWSP * 5000}")
    assert (code, err) == (0, "")
    assert out.startswith("EXPRESSION=MIT\t")
    code, _, err = _run(corpus_db, "resolve", "M" * 5000 + ZWSP)
    assert (code, err) == (
        2,
        "ERROR: input: invalid: over 2000 characters; run 'licenseid detect'\n",
    )


@pytest.mark.parametrize(
    "args",
    [["detect"], ["detect", "--text"], ["detect", "-v"], ["is-osi"]],
    ids=" ".join,
)
def test_detect_and_the_flags_agree_with_resolve(
    corpus_db: LicenseDatabase, args: list[str]
) -> None:
    value = f"MIT{RLO}"
    _, out, _ = _run(corpus_db, *args, value)
    assert out.splitlines()[0].removeprefix("EXPRESSION=").split("\t")[0] == "MIT"
    assert resolve(value, corpus_db)["expression"] == "MIT"


@pytest.mark.parametrize("command", ["detect", "is-osi"])
def test_id_still_declares_one_licence_id_exactly(
    corpus_db: LicenseDatabase, command: str
) -> None:
    """``--id`` is not widened: ``is_simple_expression`` judges it."""
    code, out, err = _run(corpus_db, command, "--id", f"MIT{RLO}")
    assert (code, out) == (2, "")
    assert err.startswith("ERROR: option: invalid: --id: ")


SPACED = [
    (f"MIT OR{ZWSP} ISC", "MIT OR  ISC"),
    (f"MIT{ZWSP} OR ISC", "MIT  OR ISC"),
    (f"MIT OR {ZWSP}ISC", "MIT OR  ISC"),
    (f"MIT OR {ZWSP}{BOM}{ZWNJ} ISC", "MIT OR     ISC"),
    (f"MIT{SHY} OR{WJ} ISC", "MIT  OR  ISC"),
    (f"MIT{ZWSP}OR ISC", f"MIT{ZWSP}OR ISC"),  # between two characters
    (f"MIT OR{RLO} ISC", f"MIT OR{RLO} ISC"),  # a bidi control is no space
    (f"MIT OR{LRM} ISC", f"MIT OR{LRM} ISC"),
    ("MIT OR\x07 ISC", "MIT OR\x07 ISC"),  # a control character neither
    ("MIT OR ISC", "MIT OR ISC"),
    (ZWSP, ZWSP),
    ("", ""),
]


@pytest.mark.parametrize(("value", "expected"), SPACED, ids=_id)
def test_a_format_character_beside_white_space_is_a_space(
    value: str, expected: str
) -> None:
    got = space_out_hidden(value)
    assert got == expected
    assert len(got) == len(value)  # a span still indexes the input


@pytest.mark.parametrize(
    "value", [f"MIT OR{ZWSP} ISC", f"MIT{ZWSP} OR ISC", f"MIT OR {ZWSP}ISC"], ids=_id
)
def test_a_compound_with_a_hidden_character_beside_a_space_reads(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        "ISC OR MIT",
        "separator",
        "resolver_rule",
    )
    assert got["steps"][0]["kind"] == "trim"
    assert got["steps"][0]["detail"] == "invisible characters"
    assert [(o["text"], o["span"]) for o in got["operands"]] == [
        ("MIT", [value.index("MIT"), value.index("MIT") + 3]),
        ("ISC", [value.index("ISC"), value.index("ISC") + 3]),
    ]

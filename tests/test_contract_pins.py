# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterisation pins for the pre-freeze contract batch of 0.7.0 (items
C1 to C11, F1 to F3, P1 to P7 of the maintainer's list, 2026-10-30).

Each pin records what the CLI or the API does before the batch. A later
commit of the batch flips the pin to the new answer and names the item, so
this file is the before-and-after record of every changed behaviour.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import GPL2_ROWS, Lic, seeded_db

import licenseid
from licenseid import LicenseDatabase, match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.result import fields_line, record_json

FRESH = "UPDATE db_metadata SET value = ? WHERE key = 'last_check_datetime'"
ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text="mit licence text"),
    Lic("ISC", "ISC License", True, True, True),
    Lic("0BSD", "BSD Zero Clause License", True, True, False),
    Lic("WTFPL", "Do What The F*ck You Want To Public License", True, False, True),
    *GPL2_ROWS,
)


@pytest.fixture
def db() -> Generator[str, None, None]:
    for path in seeded_db("contract_pins", ROWS, ["Classpath-exception-2.0"]):
        with sqlite3.connect(path, uri=True) as conn:  # no staleness warning
            conn.execute(FRESH, (datetime.now(timezone.utc).isoformat(),))
        yield path


def run(db: str, *args: str, stdin: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["--db", db, *args], input=stdin)


# --- C: commands and options ---------------------------------------------


@pytest.mark.parametrize("command", ["is-open", "is-free"])
def test_c1_the_union_commands_are_gone(db: str, command: str) -> None:
    """C1 (was: ``is-open MIT`` printed ``EXPRESSION=MIT\tIS_OPEN=true``):
    the union is ``is-osi X || is-fsf X``."""
    result = run(db, command, "MIT")
    assert result.exit_code == 2
    assert result.stderr.startswith(f"ERROR: command: not found: {command}")


def test_c1_the_union_method_is_gone() -> None:
    """C1 (was: ``LicenseDetector.is_open``)."""
    assert not hasattr(LicenseDetector, "is_open")


def test_c2_update_takes_list() -> None:
    """C2 (was: ``update --version V``): ``update --list ID[@VERSION]``."""
    help_text = CliRunner().invoke(cli, ["update", "--help"]).stdout
    assert "--list" in help_text and "--version" not in help_text


def test_c3_clear_cache_is_a_command(tmp_path: Path) -> None:
    """C3 (was: the global flag ``--clear-cache``, which printed nothing):
    the command ``clear-cache`` prints its record; the flag is refused."""
    path = str(tmp_path / "licenses.db")
    result = CliRunner().invoke(cli, ["--db", path, "clear-cache"])
    assert (result.exit_code, result.stdout) == (
        0,
        f"STATUS=nothing\tPATH={path}\n",
    )
    result = CliRunner().invoke(cli, ["--db", path, "--clear-cache"])
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: option: not found: --clear-cache")


def test_c4_id_only(db: str) -> None:
    """C4 (was: ``detect --bold``): ``--id-only`` prints the top expression."""
    result = run(db, "detect", "--id-only", "MIT")
    assert (result.exit_code, result.stdout) == (0, "MIT\n")
    assert run(db, "detect", "--bold", "MIT").exit_code == 2


def test_c5_a_dash_is_standard_input(db: str) -> None:
    """C5 (was: ``-`` read as the text ``-``, exit 1): standard input."""
    result = run(db, "detect", "-", stdin="MIT")
    assert result.exit_code == 0
    assert result.stdout.startswith("EXPRESSION=MIT\t")


def test_c6_text_is_taken_as_written(db: str) -> None:
    """C6 (was: ``--text M\\x49T`` decoded to MIT): a backslash is a
    backslash, so ``M\\x49T`` names no licence."""
    result = run(db, "detect", "--text", "M\\x49T")
    assert result.exit_code == 1
    assert not result.stdout.startswith("EXPRESSION=MIT\t")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["detect", "--id", "MIT", "--text", "ISC"], "--id: with --text"),
        (["detect", "--text", "MIT", "ISC"], "--text: with an argument"),
        (["detect", "--id", "MIT", "ISC"], "--id: with an argument"),
        (["detect", "--json", "--id-only", "MIT"], "--id-only: with --json"),
        (["detect", "--json", "--diff", "MIT"], "--diff: with --json"),
        (["detect", "--top", "0", "MIT"], "--top: 0; pass 1 or more"),
        (["is-osi", "--id", "MIT", "ISC"], "--id: with an argument"),
    ],
    ids=[
        "id-text",
        "text-arg",
        "id-arg",
        "json-id-only",
        "json-diff",
        "top0",
        "is-id-arg",
    ],
)
def test_c7_conflicts_are_refused(db: str, args: list[str], message: str) -> None:
    """C7 (was: one input or one output won, exit 0; ``--top 0`` exit 1
    with nothing): a usage error, exit 2, nothing on standard output."""
    result = run(db, *args)
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith(f"ERROR: option: invalid: {message}")


def test_c8_match_does_not_read_standard_input() -> None:
    """C8 (was: ``match`` read standard input to refuse it): no value is
    missing input, whatever is piped (``test_cli_match`` runs it on a pipe
    that never ends)."""
    result = CliRunner().invoke(cli, ["match"], input="MIT")
    assert result.exit_code == 2
    assert result.stderr == (
        "ERROR: input: missing; pass one declared licence value\n"
    )


@pytest.mark.parametrize("flags", [[], ["--json"]], ids=["text", "json"])
def test_c9_detect_prints_an_empty_record_on_exit_1(
    db: str, flags: list[str]
) -> None:
    """C9 (was: nothing on exit 1): one record, every field empty."""
    result = run(db, "detect", *flags, "--id", "No-Such-1.0")
    line = (
        '{"coverage":null,"exact":null,"expression":null,"is_fsf_libre":null,'
        '"is_osi_approved":null,"is_spdx":null,"method":null,"score":null,'
        '"similarity":null}'
        if flags
        else "EXPRESSION=\tMETHOD=\tEXACT=\tSCORE=\tSIMILARITY=\tCOVERAGE="
    )
    assert (result.exit_code, result.stdout) == (1, line + "\n")


@pytest.mark.parametrize("command", ["is-osi", "detect"])
def test_c11_the_subject_is_input(db: str, command: str) -> None:
    """C11 (was: ``detect:``, from ``is-osi`` too): the subject names the
    thing affected, the input, for every command (P146)."""
    result = run(db, command, "GPL2")
    assert result.stderr == (
        "WARNING: input: variant not stated: GPL2; using GPL-2.0-only\n"
    )


# --- F: flags and meanings -----------------------------------------------


@pytest.mark.parametrize(
    ("expression", "osi", "fsf"),
    [
        ("MIT OR ISC", True, True),
        ("ISC AND MIT", True, True),
        ("0BSD AND MIT", True, False),  # 0BSD: OSI, not FSF; AND: every one
        ("MIT OR WTFPL", True, True),  # WTFPL: FSF, not OSI; OR: any one
        ("MIT AND WTFPL", False, True),
        ("GPL-2.0-only WITH Classpath-exception-2.0", True, True),  # the licence's
        ("MIT AND LicenseRef-x", None, None),  # cannot be judged
        ("MIT OR LicenseRef-x", None, None),  # no Kleene shortcut (P140)
        ("MIT AND Foo-1.0", None, None),  # not on the List
    ],
)
def test_f1_compound_flags_are_evaluated(
    db: str, expression: str, osi: bool | None, fsf: bool | None
) -> None:
    """F1 (was: always False): AND every operand, OR any, WITH the licence's;
    None when an operand cannot be judged."""
    found = LicenseDetector(db).detect(text=f"SPDX-License-Identifier: {expression}")
    assert (found[0]["is_osi_approved"], found[0]["is_fsf_libre"]) == (osi, fsf)


@pytest.mark.parametrize(
    ("expression", "status", "flag"),
    [
        ("MIT OR ISC", 0, "true"),
        ("0BSD AND WTFPL", 1, "false"),
        ("MIT AND LicenseRef-x", 1, ""),
    ],
)
@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
def test_f1_is_osi_on_a_compound(
    db: str, expression: str, status: int, flag: str, as_json: bool
) -> None:
    """F1: exit 0 true, 1 false, 1 with the empty flag (JSON null) when it
    cannot be judged; the record is printed every time."""
    tag = f"SPDX-License-Identifier: {expression}"
    result = run(db, "is-osi", *(["--json"] if as_json else []), "--text", tag)
    canonical = LicenseDetector(db).detect(text=tag)[0]["expression"]
    value = {"true": True, "false": False, "": None}[flag]
    expected = (
        record_json(EXPRESSION=canonical, IS_OSI_APPROVED=value)
        if as_json
        else fields_line(EXPRESSION=canonical, IS_OSI_APPROVED=value)
    )
    assert (result.exit_code, result.stdout) == (status, expected + "\n")


def test_f2_a_reference_is_not_on_the_list(db: str) -> None:
    """F2 (was: True): a ``LicenseRef-*`` is valid SPDX, not on the List."""
    assert LicenseDetector(db).detect(license_id="LicenseRef-x")[0]["is_spdx"] is False
    assert run(db, "is-spdx", "LicenseRef-x").exit_code == 1


def test_f3_a_bare_deprecated_id_is_a_guess(db: str) -> None:
    """F3 (was: exact and silent): ``detect GPL-2.0`` answers GPL-2.0-only,
    not exact, with the warning ``GPL2`` gets."""
    result = run(db, "detect", "GPL-2.0")
    assert result.stdout.startswith("EXPRESSION=GPL-2.0-only\tMETHOD=id\tEXACT=false\t")
    assert result.stderr == (
        "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only\n"
    )


@pytest.mark.parametrize("args", [["--id", "GPL2"], ["GPL2"]], ids=["id", "argument"])
def test_f3_id_and_argument_agree(db: str, args: list[str]) -> None:
    """F3 (was: ``--id GPL2`` false, exit 1): both read the loose ID."""
    result = run(db, "is-osi", *args)
    assert (result.exit_code, result.stdout) == (
        0,
        "EXPRESSION=GPL-2.0-only\tIS_OSI_APPROVED=true\n",
    )


# --- P: the Python API ---------------------------------------------------


@pytest.mark.parametrize(
    "name", ["Resolution", "Category", "Trust", "Step", "Operand", "json_line"]
)
def test_p1_result_types_are_not_exported(name: str) -> None:
    """PIN (P1): the types of a result are not exported from ``licenseid``."""
    assert not hasattr(licenseid, name)


def test_p2_the_public_surface() -> None:
    """PIN (P2): ``resolve_record`` and ``diff_pair`` are public;
    ``normalize_text`` and ``DetectRequest`` are exported."""
    assert hasattr(LicenseDetector, "resolve_record")
    assert hasattr(LicenseDetector, "diff_pair")
    assert {"normalize_text", "DetectRequest", "LicenseDatabase"} <= set(
        licenseid.__all__
    )


def test_p3_a_path_is_no_database(db: str) -> None:
    """PIN (P3): ``match(value, db=<path>)`` fails on the path."""
    with pytest.raises(AttributeError):
        match("MIT", db)  # type: ignore[arg-type]


def test_p4_empty_strings_and_by(db: str) -> None:
    """PIN (P4): a step says nothing with ``""`` and has ``by``."""
    steps = match("Apache2", LicenseDatabase(db, create=False))["steps"]
    assert steps == []  # Apache-2.0 is not in this database
    step = match("mit", LicenseDatabase(db, create=False))["steps"][0]
    assert (step["detail"], step["by"]) == ("", "")
    assert step["list"] == "spdx-license-list"
    trim = match(" MIT", LicenseDatabase(db, create=False))["steps"][0]
    assert trim["list"] == ""


@pytest.mark.parametrize(
    ("value", "category", "reason"),
    [
        ("Foo", "unresolved", "not found: Foo"),
        ("", "unresolved", "empty"),
        ("NOASSERTION", "unresolved", "special value: NOASSERTION"),
        ("NONE", "unresolved", "special value: NONE"),
        ("none", "unresolved", "not found: none"),  # case-sensitive (P147)
        ("MIT WITH Foo-exception", "unresolved", "exception not found: Foo-exception"),
        ("Foo WITH Bar", "unresolved", "not found: Foo WITH Bar"),
        ("x" * 2001, "unresolved", "too long: 2001 characters"),
        ("GPL-2.0-only+", "malformed", "qualifier stated twice: GPL-2.0-only+"),
        ("MIT++", "malformed", "qualifier stated twice: MIT++"),
        ("LicenseRef-x+", "malformed", "qualifier on a reference: LicenseRef-x+"),
        ("(MIT)+", "malformed", "plus after a bracket: (MIT)+"),
    ],
    ids=lambda v: str(v)[:20],
)
def test_p5_every_refusal_has_a_reason(
    db: str, value: str, category: str, reason: str
) -> None:
    """P5 (was: None for all of these): a reason for every refusal."""
    resolution = match(value, LicenseDatabase(db, create=False))
    assert (resolution["category"], resolution["reason"]) == (category, reason)


def test_p5_an_operand_has_a_reason(db: str) -> None:
    """P5 (was: None): a refused operand says why too."""
    operands = match("MIT OR Foo", LicenseDatabase(db, create=False))["operands"]
    assert [o["reason"] for o in operands] == [None, "not found: Foo"]


@pytest.mark.parametrize(
    ("call", "error"),
    [
        (lambda d: d.detect(text=1), AttributeError),
        (lambda d: d.detect(license_id=1), AttributeError),
        (lambda d: d.is_osi(text="MIT", enable_popularity=True), TypeError),
    ],
    ids=["text-int", "id-int", "is-kwarg"],
)
def test_p6_input_errors(db: str, call: object, error: type[Exception]) -> None:
    """PIN (P6): a non-str input fails inside the detector."""
    with pytest.raises(error):
        call(LicenseDetector(db))  # type: ignore[operator]


def test_p6_no_input_and_two_inputs(db: str) -> None:
    """PIN (P6): no input answers nothing; of two, ``license_id`` wins."""
    detector = LicenseDetector(db)
    assert detector.detect() == []
    assert detector.detect(text="ISC", license_id="MIT")[0]["expression"] == "MIT"

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

import pytest
from click.testing import CliRunner, Result
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import GPL2_ROWS, Lic, seeded_db

import licenseid
from licenseid import LicenseDatabase, match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector

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


@pytest.mark.parametrize(
    ("command", "line"),
    [
        ("is-open", "EXPRESSION=MIT\tIS_OPEN=true\n"),
        ("is-free", "EXPRESSION=MIT\tIS_FREE=true\n"),
    ],
)
def test_c1_the_union_commands(db: str, command: str, line: str) -> None:
    """PIN (C1): ``is-open`` and ``is-free`` answer the OSI-or-FSF union."""
    result = run(db, command, "MIT")
    assert (result.exit_code, result.stdout) == (0, line)


def test_c1_the_union_method(db: str) -> None:
    """PIN (C1): ``LicenseDetector.is_open`` exists."""
    assert LicenseDetector(db).is_open(license_id="MIT") is True


def test_c2_update_takes_version() -> None:
    """PIN (C2): ``update --version`` names the list version; no ``--list``."""
    help_text = CliRunner().invoke(cli, ["update", "--help"]).stdout
    assert "--version" in help_text and "--list" not in help_text


def test_c3_clear_cache_is_a_flag() -> None:
    """PIN (C3): ``--clear-cache`` is a global flag that prints nothing."""
    result = CliRunner().invoke(cli, ["--clear-cache"])
    assert (result.exit_code, result.stdout) == (0, "")


def test_c4_bold(db: str) -> None:
    """PIN (C4): ``detect --bold`` prints the top expression alone."""
    result = run(db, "detect", "--bold", "MIT")
    assert (result.exit_code, result.stdout) == (0, "MIT\n")


def test_c5_a_dash_is_text(db: str) -> None:
    """PIN (C5): ``-`` is read as the text ``-``, not standard input."""
    result = run(db, "detect", "-", stdin="MIT")
    assert (result.exit_code, result.stdout) == (1, "")


def test_c6_text_escapes_are_decoded(db: str) -> None:
    """PIN (C6): ``--text`` decodes backslash escapes (``\\x49`` is I)."""
    result = run(db, "detect", "--text", "M\\x49T")
    assert result.exit_code == 0
    assert result.stdout.startswith("EXPRESSION=MIT\t")


@pytest.mark.parametrize(
    ("args", "status", "head"),
    [
        (["detect", "--id", "MIT", "--text", "ISC"], 0, "EXPRESSION=MIT\t"),
        (["detect", "--text", "MIT", "ISC"], 0, "EXPRESSION=MIT\t"),
        (["detect", "--id", "MIT", "ISC"], 0, "EXPRESSION=MIT\t"),
        (["detect", "--json", "--bold", "MIT"], 0, "MIT\n"),
        (["detect", "--json", "--diff", "MIT"], 0, '{"coverage":null'),
        (["detect", "--top", "0", "MIT"], 1, ""),
        (["is-osi", "--id", "MIT", "ISC"], 0, "EXPRESSION=MIT\t"),
    ],
    ids=[
        "id-text",
        "text-arg",
        "id-arg",
        "json-bold",
        "json-diff",
        "top0",
        "is-id-arg",
    ],
)
def test_c7_conflicts_pass(db: str, args: list[str], status: int, head: str) -> None:
    """PIN (C7): two inputs, ``--json`` with ``--bold`` or ``--diff`` and a
    ``--top`` below 1 are not refused: one input or one output wins."""
    result = run(db, *args)
    assert result.exit_code == status
    assert result.stdout.startswith(head)


def test_c8_match_reads_standard_input() -> None:
    """PIN (C8): ``match`` with no value reads standard input to refuse it."""
    result = CliRunner().invoke(cli, ["match"], input="MIT")
    assert result.exit_code == 2
    assert result.stderr == (
        "ERROR: input: invalid: standard input; run 'licenseid detect'\n"
    )


@pytest.mark.parametrize("flags", [[], ["--json"]], ids=["text", "json"])
def test_c9_detect_prints_nothing_on_exit_1(db: str, flags: list[str]) -> None:
    """PIN (C9): ``detect`` with no answer prints nothing."""
    result = run(db, "detect", *flags, "--id", "No-Such-1.0")
    assert (result.exit_code, result.stdout) == (1, "")


def test_c11_the_subject_is_detect(db: str) -> None:
    """PIN (C11): ``is-osi`` warns with the subject ``detect``."""
    result = run(db, "is-osi", "GPL2")
    assert result.stderr == (
        "WARNING: detect: variant not stated: GPL2; using GPL-2.0-only\n"
    )


# --- F: flags and meanings -----------------------------------------------


@pytest.mark.parametrize(
    ("expression", "osi", "fsf"),
    [
        ("MIT OR ISC", False, False),
        ("ISC AND MIT", False, False),
        ("0BSD AND MIT", False, False),
        ("MIT OR WTFPL", False, False),
        ("MIT AND LicenseRef-x", False, False),
    ],
)
def test_f1_compound_flags_are_false(
    db: str, expression: str, osi: bool, fsf: bool
) -> None:
    """PIN (F1): a compound's OSI and FSF flags are always False."""
    found = LicenseDetector(db).detect(text=f"SPDX-License-Identifier: {expression}")
    assert (found[0]["is_osi_approved"], found[0]["is_fsf_libre"]) == (osi, fsf)


def test_f2_a_reference_is_spdx(db: str) -> None:
    """PIN (F2): a ``LicenseRef-*`` counts as on the SPDX List."""
    assert LicenseDetector(db).detect(license_id="LicenseRef-x")[0]["is_spdx"] is True


def test_f3_a_bare_deprecated_id_is_exact(db: str) -> None:
    """PIN (F3): ``detect GPL-2.0`` answers GPL-2.0-only, exact, silent."""
    result = run(db, "detect", "GPL-2.0")
    assert result.stdout.startswith("EXPRESSION=GPL-2.0-only\tMETHOD=id\tEXACT=true\t")
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("args", "status", "line"),
    [
        (["--id", "GPL2"], 1, "EXPRESSION=\tIS_OSI_APPROVED=false\n"),
        (["GPL2"], 0, "EXPRESSION=GPL-2.0-only\tIS_OSI_APPROVED=true\n"),
    ],
    ids=["id", "argument"],
)
def test_f3_id_and_argument_differ(
    db: str, args: list[str], status: int, line: str
) -> None:
    """PIN (F3): ``--id GPL2`` names nothing, the argument GPL2 names GPL-2.0."""
    result = run(db, "is-osi", *args)
    assert (result.exit_code, result.stdout) == (status, line)


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


@pytest.mark.parametrize("value", ["Foo", "", "NOASSERTION", "MIT WITH Foo-exception"])
def test_p5_a_refusal_with_no_reason(db: str, value: str) -> None:
    """PIN (P5): some refusals carry no reason."""
    resolution = match(value, LicenseDatabase(db, create=False))
    assert (resolution["category"], resolution["reason"]) == ("unresolved", None)


def test_p5_malformed_with_no_reason(db: str) -> None:
    """PIN (P5): a qualifier stated twice is malformed with no reason."""
    resolution = match("GPL-2.0-only+", LicenseDatabase(db, create=False))
    assert (resolution["category"], resolution["reason"]) == ("malformed", None)


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

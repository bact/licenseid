# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The public surface of the CLI and the API after the pre-freeze changes
of 0.7.0 (the maintainer's list, 2026-10-30): commands, options, inputs,
exports and refusal reasons.

Each pin records what the CLI or the API does before the changes. A later
commit of them flips the pin to the new answer and names the change, so
this file is the before-and-after record of every changed behaviour.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import inspect
import sqlite3
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import get_type_hints

import pytest
from click.testing import CliRunner, Result
from conftest import NO_DETECTION, clear_cache_line
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db
from matcher_db import GPL2_ROWS, Lic, seeded_db

import licenseid
from licenseid import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseDatabase,
    resolve,
    resolvertypes,
)
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
    for path in seeded_db("public_surface", ROWS, ["Classpath-exception-2.0"]):
        with sqlite3.connect(path, uri=True) as conn:  # no staleness warning
            conn.execute(FRESH, (datetime.now(timezone.utc).isoformat(),))
        yield path


def run(db: str, *args: str, stdin: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["--db", db, *args], input=stdin)


# --- C: commands and options ---------------------------------------------


@pytest.mark.parametrize("command", ["is-open", "is-free"])
def test_the_union_commands_are_gone(db: str, command: str) -> None:
    """Was: ``is-open MIT`` printed ``EXPRESSION=MIT\tIS_OPEN=true``; now
    the union is ``is-osi X || is-fsf X``."""
    result = run(db, command, "MIT")
    assert result.exit_code == 2
    assert result.stderr.startswith(f"ERROR: command: not found: {command}")


def test_the_union_method_is_gone() -> None:
    """Was: ``LicenseDetector.is_open``."""
    assert not hasattr(LicenseDetector, "is_open")


def test_update_takes_list() -> None:
    """Was: ``update --version V``; now ``update --list ID[@VERSION]``."""
    help_text = CliRunner().invoke(cli, ["update", "--help"]).stdout
    assert "--list" in help_text and "--version" not in help_text


def test_clear_cache_is_a_command(tmp_path: Path) -> None:
    """Was: the global flag ``--clear-cache``, which printed nothing; now
    the command ``clear-cache`` prints its record; the flag is refused."""
    path = str(tmp_path / "licenses.db")
    result = CliRunner().invoke(cli, ["--db", path, "clear-cache"])
    assert (result.exit_code, result.stdout) == (0, clear_cache_line("nothing", path))
    result = CliRunner().invoke(cli, ["--db", path, "--clear-cache"])
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: option: not found: --clear-cache")


def test_id_only_is_gone(db: str) -> None:
    """``--id-only`` was the terse output, now the default of ``detect``;
    the option is gone. Same for ``--bold``."""
    result = run(db, "detect", "--id-only", "MIT")
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: option: not found: --id-only")
    assert run(db, "detect", "--bold", "MIT").exit_code == 2


def test_a_dash_is_standard_input(db: str) -> None:
    """Was: ``-`` read as the text ``-``, exit 1; now standard input."""
    result = run(db, "detect", "-", stdin="MIT")
    assert result.exit_code == 0
    assert result.stdout.startswith("EXPRESSION=MIT\t")


def test_text_is_taken_as_written(db: str) -> None:
    """Was: ``--text M\\x49T`` decoded to MIT; now a backslash is a
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
        (["detect", "--json", "--diff", "MIT"], "--diff: with --json"),
        (["detect", "--top", "0", "MIT"], "--top: 0; pass 1 or more"),
        (["detect", "--top", "-1", "MIT"], "--top: -1; pass 1 or more"),
        (["is-osi", "--id", "MIT", "ISC"], "--id: with an argument"),
    ],
    ids=[
        "id-text",
        "text-arg",
        "id-arg",
        "json-diff",
        "top0",
        "top-negative",
        "is-id-arg",
    ],
)
def test_conflicts_are_refused(db: str, args: list[str], message: str) -> None:
    """Was: one input or one output won, exit 0; ``--top 0`` exit 1
    with nothing; now a usage error, exit 2, nothing on standard output."""
    result = run(db, *args)
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith(f"ERROR: option: invalid: {message}")


def test_match_does_not_read_standard_input() -> None:
    """Was: ``resolve`` read standard input to refuse it; now no value is
    missing input, whatever is piped (``test_cli_resolve`` runs it on a pipe
    that never ends)."""
    result = CliRunner().invoke(cli, ["resolve"], input="MIT")
    assert result.exit_code == 2
    assert result.stderr == ("ERROR: input: missing; pass one declared licence value\n")


@pytest.mark.parametrize("flags", [[], ["--json"]], ids=["text", "json"])
def test_detect_prints_an_empty_record_on_exit_1(db: str, flags: list[str]) -> None:
    """Was: nothing on exit 1; now one record, every field empty."""
    result = run(db, "detect", *flags, "--id", "No-Such-1.0")
    line = (
        '{"coverage":null,"exact":null,"expression":null,"is_fsf_libre":null,'
        '"is_osi_approved":null,"is_spdx":null,"lists":null,"method":null,'
        '"reason":"no match","same_text":null,"score":null,"similarity":null,'
        '"texts":null,"variant_stated":null}'
        if flags
        else NO_DETECTION.rstrip("\n")
    )
    assert (result.exit_code, result.stdout) == (1, line + "\n")


@pytest.mark.parametrize(
    ("args", "warning"),
    [
        (["detect", "--variant", "only", "GPL2"], "variant not stated: GPL-2.0;"),
        (["is-osi", "Foo"], "too few words for text: not found: Foo"),
    ],
)
def test_the_subject_is_input(db: str, args: list[str], warning: str) -> None:
    """Was: ``detect:``, from ``is-osi`` too; now the subject names the
    thing affected, the input, for every command."""
    result = run(db, *args)
    assert result.stderr.startswith(f"WARNING: input: {warning}")


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
        ("MIT OR LicenseRef-x", True, True),  # one true operand decides
    ],
)
def test_compound_flags_are_evaluated(
    db: str, expression: str, osi: bool | None, fsf: bool | None
) -> None:
    """Was: always False; now AND every operand, OR any, WITH the licence's;
    None when an operand cannot be judged and the others do not decide it
    (was: None for any such operand)."""
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
def test_is_osi_on_a_compound(
    db: str, expression: str, status: int, flag: str, as_json: bool
) -> None:
    """Exit 0 true, 1 false, 1 with the empty flag (JSON null) when it
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


def test_a_reference_is_not_on_the_list(db: str) -> None:
    """Was: True; now a ``LicenseRef-*`` is valid SPDX, not on the List."""
    assert LicenseDetector(db).detect(license_id="LicenseRef-x")[0]["is_spdx"] is False
    assert run(db, "is-spdx", "LicenseRef-x").exit_code == 1


def test_a_bare_deprecated_id_is_a_guess(db: str) -> None:
    """Was: exact and silent; now ``detect GPL-2.0`` answers GPL-2.0-only,
    not exact, with the warning ``GPL2`` gets."""
    result = run(db, "detect", "--variant", "only", "GPL-2.0")
    assert result.stdout.startswith("EXPRESSION=GPL-2.0-only\tMETHOD=id\tEXACT=false\t")
    assert result.stderr == (
        "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only\n"
    )


@pytest.mark.parametrize("args", [["--id", "GPL2"], ["GPL2"]], ids=["id", "argument"])
def test_id_and_argument_agree(db: str, args: list[str]) -> None:
    """Was: ``--id GPL2`` false, exit 1; now both read the loose ID."""
    result = run(db, "is-osi", *args)
    assert (result.exit_code, result.stdout) == (
        0,
        "EXPRESSION=GPL-2.0\tIS_OSI_APPROVED=true\n",  # as written
    )


# --- P: the Python API ---------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "Resolution",
        "Category",
        "Trust",
        "Step",
        "Operand",
        "ListInfo",
        "ListSource",
        "Source",
        "Detection",
        "Method",
        "ToolInfo",
        "DetectOptions",
        "Variant",
        "json_line",
    ],
)
def test_result_types_are_exported(name: str) -> None:
    """Was: only ``Detection`` and ``Method``; now the types of a result,
    the options of ``detect()`` (``DetectOptions``, whose ``variant`` is a
    ``Variant``) and ``json_line`` are exported from ``licenseid``."""
    assert hasattr(licenseid, name) and name in licenseid.__all__


def test_the_exports_are_sorted() -> None:
    assert licenseid.__all__ == sorted(licenseid.__all__)


def test_resolver_and_component_are_one_type() -> None:
    """Was: ``Resolver`` and ``Component``, two classes of the same four keys;
    now ``ToolInfo`` is both, and they are gone."""
    hints = get_type_hints(licenseid.Resolution)
    assert hints["resolver"] is licenseid.ToolInfo
    assert hints["components"] == list[licenseid.ToolInfo]
    assert set(get_type_hints(licenseid.ToolInfo)) == {"name", "version", "url", "purl"}
    assert not hasattr(resolvertypes, "Resolver")
    assert not hasattr(resolvertypes, "Component")


def test_the_cli_helpers_are_private() -> None:
    """Was: ``resolve_record`` and ``diff_pair`` public; now the helpers
    the CLI reads are ``_resolve_record`` and ``_diff_pair``."""
    assert not hasattr(LicenseDetector, "resolve_record")
    assert not hasattr(LicenseDetector, "diff_pair")
    assert hasattr(LicenseDetector, "_resolve_record")
    assert hasattr(LicenseDetector, "_diff_pair")


def test_the_public_surface() -> None:
    """Was: ``normalize_text`` and ``DetectRequest`` exported; now
    ``LicenseDatabase`` stays, as an opaque handle."""
    assert not {"normalize_text", "DetectRequest"} & set(licenseid.__all__)
    assert not hasattr(licenseid, "normalize_text")
    assert "LicenseDatabase" in licenseid.__all__


def test_a_path_is_a_database(db: str, tmp_path: Path) -> None:
    """Was: ``AttributeError`` on a path; now a path opens read-only; a
    missing one is ``not found`` and stays missing."""
    assert resolve("MIT", db)["expression"] == "MIT"  # a file: URI
    on_disk = make_ready_file_db(tmp_path / "licenses.db")
    assert resolve("MIT", on_disk)["expression"] == "MIT"  # a Path
    assert resolve("MIT", str(on_disk))["expression"] == "MIT"
    missing = tmp_path / "no" / "licenses.db"
    with pytest.raises(DatabaseNotReadyError, match="^database: not found: "):
        resolve("MIT", missing)
    assert not missing.exists() and not missing.parent.exists()


def test_none_means_nothing(db: str) -> None:
    """Was: ``detail`` and ``list`` ``""``, and ``by`` ``""``; now None
    means nothing; ``by`` is gone."""
    steps = resolve("Apache2", LicenseDatabase(db, create=False))["steps"]
    assert steps == []  # Apache-2.0 is not in this database
    step = resolve("mit", LicenseDatabase(db, create=False))["steps"][0]
    assert step["detail"] is None and "by" not in step
    assert step["list"] == "spdx-license-list"
    trim = resolve(" MIT", LicenseDatabase(db, create=False))["steps"][0]
    assert trim["list"] is None


@pytest.mark.parametrize(
    ("value", "category", "reason"),
    [
        ("Foo", "unresolved", "not found: Foo"),
        ("", "unresolved", "empty"),
        ("NOASSERTION", "unresolved", "special value: NOASSERTION"),
        ("NONE", "unresolved", "special value: NONE"),
        ("none", "unresolved", "not found: none"),  # case-sensitive
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
def test_every_refusal_has_a_reason(
    db: str, value: str, category: str, reason: str
) -> None:
    """Was: None for all of these; now a reason for every refusal."""
    resolution = resolve(value, LicenseDatabase(db, create=False))
    assert (resolution["category"], resolution["reason"]) == (category, reason)


def test_an_operand_has_a_reason(db: str) -> None:
    """Was: None; now a refused operand says why too."""
    operands = resolve("MIT OR Foo", LicenseDatabase(db, create=False))["operands"]
    assert [o["reason"] for o in operands] == [None, "not found: Foo"]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda d: d.detect(text=1), "^text must be str, not int$"),
        (lambda d: d.detect(license_id=1), "^license_id must be str, not int$"),
        (lambda d: d.detect(text=b"MIT"), "^text must be str, not bytes$"),
        (lambda d: d.is_osi(license_id=["MIT"]), "^license_id must be str, not list$"),
    ],
    ids=["text-int", "id-int", "text-bytes", "is-id-list"],
)
def test_a_non_str_input_is_a_type_error(
    db: str, call: Callable[[LicenseDetector], object], message: str
) -> None:
    """Was: ``AttributeError`` from deep inside; now ``TypeError``, naming
    the parameter and the type."""
    with pytest.raises(TypeError, match=message):
        call(LicenseDetector(db))


@pytest.mark.parametrize("predicate", ["is_osi", "is_fsf", "is_spdx"])
def test_a_predicate_takes_named_inputs_only(db: str, predicate: str) -> None:
    """Was: ``**kwargs`` passed on; now an option of detect() is a
    ``TypeError`` of the signature, and the inputs are named parameters."""
    check = getattr(LicenseDetector(db), predicate)
    params = inspect.signature(check).parameters
    assert list(params) == ["text", "license_id", "file_path"]
    with pytest.raises(TypeError):
        check(text="MIT", enable_popularity=True)


def test_no_input_and_two_inputs(db: str) -> None:
    """Was: no input answered ``[]``; of two, ``license_id`` won; now
    ``InvalidInputError`` for both."""
    detector = LicenseDetector(db)
    with pytest.raises(InvalidInputError, match="^input: missing; "):
        detector.detect()
    with pytest.raises(
        InvalidInputError, match="^input: invalid: text: with license_id; pass one"
    ):
        detector.detect(text="ISC", license_id="MIT")
    with pytest.raises(InvalidInputError, match="^input: missing; "):
        detector.is_osi()

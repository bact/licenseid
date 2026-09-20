# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Adversarial tests for the database readiness gate.

READY iff tables ``licenses`` and ``db_metadata`` exist (as tables, not
views), ``db_metadata`` holds a non-blank ``license_list_version``, and
``licenses`` has a row with the columns every answer reads. Anything else is
refused before the database is opened, read-only, with one stderr line and
exit 2. Written from the contract alone, then adapted where the contract was
open; ``tests/db_variants.py`` has every database variant.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import contextlib
import hashlib
import os
import random
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from db_asserts import (
    assert_no_traceback,
    assert_one_diagnostic_line,
    assert_refused,
    expected_refusal,
    run_cli,
)
from db_variants import (
    COMMANDS,
    EMPTY,
    INPUTS,
    INVALID,
    LENIENT_NAMES,
    MIT_TEXT,
    NOT_FOUND,
    NOT_READY_NAMES,
    READY_NAMES,
    REFUSED,
    UNREADABLE,
    Variant,
    build_variant,
    make_ready_file_db,
    writer,
)

from licenseid.database import LicenseDatabase
from licenseid.errors import DatabaseNotReadyError, LicenseIdError
from licenseid.matcher import AggregatedLicenseMatcher

# One per refusal message, for the full command x input matrix.
REPRESENTATIVE_NAMES = ["missing", "both_tables_empty", "plain_text"]


@pytest.fixture
def variant(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[Variant, None, None]:
    built = build_variant(request.param, tmp_path)
    yield built
    if built.keep_alive is not None:
        built.keep_alive.close()
    if built.name == "no_permission" and built.path is not None:
        built.path.chmod(0o600)  # so pytest can clean tmp_path up


def input_args(source: str, tmp_path: Path) -> tuple[list[str], str]:
    """CLI arguments and stdin for one input source."""
    fixed = {
        "arg_id": (["MIT"], ""),
        "text": (["--text", MIT_TEXT], ""),
        "id": (["--id", "MIT"], ""),
        "stdin": ([], MIT_TEXT),
        "none": ([], ""),
        "blank": (["--", ""], ""),
        "blank_text": (["--text", ""], ""),
    }
    if source in fixed:
        return fixed[source]
    assert source == "arg_file", f"unknown input: {source}"
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    path = input_dir / "LICENSE"
    path.write_text(MIT_TEXT, encoding="utf-8")
    return [str(path)], ""


# (a) Every not-ready state is refused, whatever the command and input


@pytest.mark.parametrize("variant", NOT_READY_NAMES, indirect=True)
@pytest.mark.parametrize("output", [[], ["--json"], ["--bold"], ["--diff"]])
def test_not_ready_refused(variant: Variant, output: list[str]) -> None:
    """No output option may turn the refusal into stdout (empty JSON too)."""
    result = run_cli(variant.db_arg, ["match", *output, "--id", "MIT"])
    assert_refused(result, variant.kind, variant.db_arg)


@pytest.mark.parametrize("variant", REPRESENTATIVE_NAMES, indirect=True)
@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("source", INPUTS)
def test_not_ready_refused_for_every_command_and_input(
    variant: Variant, command: str, source: str, tmp_path: Path
) -> None:
    """The database check comes first: a missing or blank input, otherwise an
    "input:" error, must still report the database."""
    args, stdin = input_args(source, tmp_path)
    result = run_cli(variant.db_arg, [command, *args], stdin)
    assert_refused(result, variant.kind, variant.db_arg)


@pytest.mark.parametrize("variant", LENIENT_NAMES, indirect=True)
@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_lenient_states_never_crash(variant: Variant, command: str) -> None:
    """States the contract calls READY but the query layer may choke on."""
    result = run_cli(variant.db_arg, [command, "--id", "MIT"])
    assert_no_traceback(result)
    assert result.exit_code in (0, 1, 2)
    if result.exit_code == 2:
        assert result.stdout == ""
    for line in result.stderr.splitlines():
        assert line.startswith(("ERROR: ", "WARNING: ")), line


def test_non_ascii_path_printed_intact(tmp_path: Path) -> None:
    built = build_variant("path_non_ascii", tmp_path)
    result = run_cli(built.db_arg, ["match", "--id", "MIT"])
    assert_refused(result, built.kind, built.db_arg)
    assert "授权" in result.stderr and "ünïcödé" in result.stderr
    assert "\\u" not in result.stderr and "\\x" not in result.stderr


@pytest.mark.parametrize("blank", ["", "  "])
def test_empty_db_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    """``--db ''`` is a usage error, not a silent fall-back to the default
    database: the answer would come from a file the user did not name. The
    default path is patched, so the real ~/.local/share one cannot answer."""
    default = tmp_path / "default" / "licenses.db"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "home" / "share"))
    for module in ("licenseid.cli", "licenseid.database", "licenseid.matcher"):
        monkeypatch.setattr(
            f"{module}.get_default_db_path", lambda: str(default), raising=False
        )
    result = run_cli(blank, ["match", "--id", "MIT"])
    assert_no_traceback(result)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert_one_diagnostic_line(result.stderr)
    assert result.stderr == "ERROR: database: missing: --db; pass a path or drop --db\n"
    assert str(default) not in result.stderr
    assert not default.exists()


# (b) The refusal is read-only


def is_wal_file(path: Path) -> bool:
    """Whether *path* is an SQLite file in write-ahead-log mode."""
    try:
        return path.read_bytes()[18:20] == b"\x02\x02"
    except OSError:
        return False


def fs_state(path: Path) -> dict[str, Any]:
    """What a read-only check must leave untouched. The -shm and -wal files
    that SQLite makes when it reads a write-ahead-log database are not."""
    state: dict[str, Any] = {
        "siblings": sorted(
            p.name
            for p in path.parent.iterdir()
            if not p.name.endswith(("-shm", "-wal"))
        ),
        "lexists": path.is_symlink() or path.exists(),
    }
    if path.is_symlink():
        state["symlink_target"] = os.readlink(path)
    if path.is_dir():
        state["listing"] = sorted(p.name for p in path.iterdir())
    elif path.is_file():
        stat = path.stat()
        state["size"] = stat.st_size
        state["mtime_ns"] = stat.st_mtime_ns
        state["mode"] = stat.st_mode
        try:
            state["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except PermissionError:
            state["sha256"] = "unreadable"
    return state


def assert_untouched(path: Path, before: dict[str, Any]) -> None:
    assert fs_state(path) == before
    suffixes = ("-journal",) if is_wal_file(path) else ("-journal", "-wal", "-shm")
    for suffix in suffixes:
        sidecar = path.with_name(path.name + suffix)
        assert not sidecar.exists(), f"{sidecar.name} was created"


@pytest.mark.parametrize("variant", NOT_READY_NAMES, indirect=True)
def test_refusal_has_no_side_effects(variant: Variant) -> None:
    if variant.path is None:
        pytest.skip("not file-backed")
    before = fs_state(variant.path)
    result = run_cli(variant.db_arg, ["match", "--id", "MIT"])
    assert_refused(result, variant.kind, variant.db_arg)
    assert_untouched(variant.path, before)


@pytest.mark.parametrize("variant", NOT_READY_NAMES, indirect=True)
def test_api_refusal_has_no_side_effects(variant: Variant) -> None:
    if variant.path is None:
        pytest.skip("not file-backed")
    before = fs_state(variant.path)
    with pytest.raises(DatabaseNotReadyError):
        AggregatedLicenseMatcher(db_path=variant.db_arg)
    assert_untouched(variant.path, before)


@pytest.mark.parametrize(
    "variant", ["missing", "dangling_symlink", "file_uri_missing"], indirect=True
)
def test_missing_database_is_not_created(variant: Variant) -> None:
    """Opening a path with sqlite3 creates it -- the check must not."""
    assert variant.path is not None
    result = run_cli(variant.db_arg, ["is-osi", "MIT"])
    assert_refused(result, variant.kind, variant.db_arg)
    assert not variant.path.exists()
    expected = [variant.path.name] if variant.name == "dangling_symlink" else []
    assert sorted(p.name for p in variant.path.parent.iterdir()) == expected


# (c) The Python API refuses in the constructor


@pytest.mark.parametrize("variant", NOT_READY_NAMES, indirect=True)
def test_api_constructor_raises(variant: Variant) -> None:
    with pytest.raises(DatabaseNotReadyError) as excinfo:
        AggregatedLicenseMatcher(db_path=variant.db_arg)
    message = str(excinfo.value)
    assert "\n" not in message
    assert not message.startswith("ERROR: ")
    if variant.kind in (NOT_FOUND, EMPTY, INVALID):
        head = len("ERROR: ")
        assert message == expected_refusal(variant.kind, variant.db_arg)[head:-1]
    elif variant.kind == UNREADABLE:
        assert message.startswith(f"database: unreadable: {variant.db_arg}: ")
    else:
        assert message.startswith("database: ")


@pytest.mark.parametrize("variant", ["missing", "both_tables_empty"], indirect=True)
def test_api_error_is_catchable_as_runtime_error(variant: Variant) -> None:
    assert issubclass(DatabaseNotReadyError, LicenseIdError)
    assert issubclass(LicenseIdError, RuntimeError)
    caught: RuntimeError | None = None
    try:
        AggregatedLicenseMatcher(db_path=variant.db_arg)
    except RuntimeError as error:  # a pre-existing caller's except clause
        caught = error
    assert isinstance(caught, DatabaseNotReadyError)


@pytest.mark.parametrize("enable_popularity", [False, True])
def test_api_default_path_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enable_popularity: bool
) -> None:
    """db_path=None must not reach ~/.local/share: the default is patched."""
    default = tmp_path / "default" / "licenses.db"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "home" / "share"))
    monkeypatch.setattr("licenseid.matcher.get_default_db_path", lambda: str(default))
    with pytest.raises(DatabaseNotReadyError) as excinfo:
        AggregatedLicenseMatcher(enable_popularity=enable_popularity)
    assert str(excinfo.value) == (
        f"database: not found: {default}; run 'licenseid update'"
    )
    assert not default.exists()


@pytest.mark.parametrize("variant", ["both_tables_empty"], indirect=True)
def test_api_refuses_before_any_query(variant: Variant) -> None:
    """The failure is the constructor's, not the first match()'s."""
    with pytest.raises(DatabaseNotReadyError):
        matcher = AggregatedLicenseMatcher(db_path=variant.db_arg)
        matcher.match(text=MIT_TEXT)  # must never be reached


@pytest.mark.parametrize("variant", NOT_READY_NAMES, indirect=True)
def test_license_database_stays_permissive(variant: Variant) -> None:
    """LicenseDatabase stays permissive; only the matcher and the CLI gate."""
    if variant.kind in (UNREADABLE, REFUSED):
        pytest.skip("not a database SQLite can open, so nothing to build on")
    if variant.name in (
        "views_not_tables",
        "memory_uri",
        "file_colon_memory",
    ):
        pytest.skip("LicenseDatabase cannot index a view or share a private memory db")
    if variant.name == "file_uri_mode_ro_missing":
        pytest.skip("mode=ro cannot create the missing file")
    if variant.name in ("wrong_columns", "column_name_case_flipped"):
        pytest.skip("the table has other columns than LicenseDatabase adds to")
    LicenseDatabase(variant.db_arg)


# (d) Ready databases still behave exactly as before


@pytest.mark.parametrize("variant", READY_NAMES, indirect=True)
def test_ready_database_matches(variant: Variant) -> None:
    result = run_cli(variant.db_arg, ["match", "--bold", "--id", "MIT"])
    assert_no_traceback(result)
    assert result.exit_code == 0
    assert result.stdout == "MIT\n"
    assert result.stderr == ""


@pytest.mark.parametrize("variant", READY_NAMES, indirect=True)
@pytest.mark.parametrize("command", COMMANDS)
def test_ready_database_answers_yes_and_no(variant: Variant, command: str) -> None:
    yes = run_cli(variant.db_arg, [command, "MIT"])
    assert_no_traceback(yes)
    assert yes.exit_code == 0
    assert yes.stderr == ""
    no = run_cli(variant.db_arg, [command, "--id", "No-Such-License-1.0"])
    assert_no_traceback(no)
    assert no.exit_code == 1
    assert no.stdout in ("", "false\n")
    # "no" is an answer, not a fault: nothing but the match's own ERROR line.
    assert no.stderr in ("", "ERROR: match: no license found\n")


@pytest.mark.parametrize("variant", ["ready_file", "ready_memory_uri"], indirect=True)
def test_ready_database_api(variant: Variant) -> None:
    matcher = AggregatedLicenseMatcher(db_path=variant.db_arg)
    assert matcher.is_osi(license_id="MIT") is True
    assert [m["license_id"] for m in matcher.match(text=MIT_TEXT)] == ["MIT"]


# (e) State changes around an already-constructed matcher


def test_match_after_database_deleted(tmp_path: Path) -> None:
    """The gate runs once, at construction, so a file deleted afterwards is
    outside its remit.

    # BUG: current, wrong behaviour: the next call reaches SQLite, which
    # recreates an empty file, and a raw sqlite3.OperationalError escapes.
    Wording it as a licenseid error is roadmap item 10 (environment
    failures); flip this pin when that lands.
    """
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    matcher = AggregatedLicenseMatcher(db_path=str(db_path))
    assert matcher.match(license_id="MIT")
    db_path.unlink()
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        matcher.match(license_id="MIT")


def test_two_matchers_on_one_database(tmp_path: Path) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    first = AggregatedLicenseMatcher(db_path=str(db_path))
    second = AggregatedLicenseMatcher(db_path=str(db_path))
    assert first.match(license_id="MIT")
    assert second.match(license_id="MIT")
    assert first.is_spdx(license_id="MIT") == second.is_spdx(license_id="MIT")


def test_database_emptied_between_two_runs(tmp_path: Path) -> None:
    """A ready database that loses its rows is refused on the next run."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    assert run_cli(str(db_path), ["match", "--bold", "--id", "MIT"]).exit_code == 0
    with writer(db_path) as conn:
        conn.execute("DELETE FROM licenses")
    result = run_cli(str(db_path), ["match", "--bold", "--id", "MIT"])
    assert_refused(result, EMPTY, str(db_path))


# (f) Seeded corruption sweep


def _mit_row_readable(path: Path) -> bool:
    """Whether an independent read-only reader still finds the MIT row."""
    try:
        with contextlib.closing(
            sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        ) as conn:
            row = conn.execute(
                "SELECT 1 FROM licenses WHERE license_id = 'MIT'"
            ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


def _mutate(payload: bytes, rng: random.Random, truncate: bool) -> tuple[bytes, str]:
    """One deterministic mutation of a ready database's bytes."""
    if truncate:
        cut = rng.randrange(0, len(payload))
        return payload[:cut], f"truncate@{cut}"
    data = bytearray(payload)
    offsets = [rng.randrange(0, len(payload)) for _ in range(rng.randint(1, 4))]
    for offset in offsets:
        data[offset] ^= 1 << rng.randrange(8)
    return bytes(data), f"flip@{offsets}"


def test_random_corruption_sweep(tmp_path: Path) -> None:
    """200 deterministic mutations of a ready database: the CLI may only give
    the right answer or a single-line refusal with exit 2. Exit 1 is tolerated
    solely when the mutation destroyed the MIT row itself."""
    source = make_ready_file_db(tmp_path / "source.db")
    payload = source.read_bytes()
    work = tmp_path / "work"
    work.mkdir()
    target = work / "licenses.db"
    rng = random.Random(1234)

    for iteration in range(200):
        data, what = _mutate(payload, rng, truncate=bool(iteration % 2))
        target.write_bytes(data)
        result = run_cli(str(target), ["match", "--bold", "--id", "MIT"])
        context = f"iteration {iteration} ({what}): "
        assert_no_traceback(result)
        if result.exit_code == 0:
            assert result.stdout == "MIT\n", context + repr(result.stdout)
            continue
        if result.exit_code == 1:
            assert not _mit_row_readable(target), (
                context + "exit 1 although the MIT row is intact"
            )
            assert result.stdout == "", context + repr(result.stdout)
            continue
        assert result.exit_code == 2, context + f"exit {result.exit_code}"
        assert result.stdout == "", context + repr(result.stdout)
        assert_one_diagnostic_line(result.stderr)
        assert result.stderr.startswith(
            (
                f"ERROR: database: empty: {target};",
                f"ERROR: database: invalid: {target}\n",
                f"ERROR: database: unreadable: {target}: ",
            )
        ), context + repr(result.stderr)

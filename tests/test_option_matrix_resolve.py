# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` x source x database state x bundle, and CLI ``resolve``
(axes of ``tests/test_option_matrix.py``, kept apart for its size). Every
combination is one test case; see that file for the other surfaces."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import contextlib
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db
from packaged_list import fixture_bundle
from release_fakes import release_bundle, ship
from resolve_states import MISSING as NO_DATABASE
from resolve_states import (
    NO_HOME,
    OUTDATED,
    OUTDATED_WARNING,
    STATES,
    VERSION,
    build,
    refusal,
)

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.datadir import get_default_db_path
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.resolvertypes import Source

pytestmark = pytest.mark.terse_cli  # the matrix names --verbose itself


# --- API resolve(): source x the database at the default path x bundle ---

RESOLVE_SOURCES = ["auto", "database", "packaged"]
BUNDLES = ["shipped", "none", "invalid"]
_BUNDLE_BYTES = {"shipped": release_bundle(VERSION), "none": None, "invalid": b"bad"}
_BAD_BUNDLE = "spdx-bundle.json.gz: invalid: BadGzipFile: Not a gzipped file (b'ba')"
# What each bundle prints when resolve() loads it: an unusable one warns once.
_LOADED = {"shipped": "", "none": "", "invalid": f"WARNING: {_BAD_BUNDLE}\n"}
_NO_LIST = {"none": "spdx-bundle.json.gz: not found", "invalid": _BAD_BUNDLE}


def _resolve_outcome(source: str, state: str, bundle: str) -> tuple[str, str, str]:
    """What resolve("MIT", source=source) does, as ``(list source or
    "raise", what it raises, what it prints)``, the last two as regular
    expressions. The bundle holds the database's version, so a usable
    database wins the tie, an outdated one loses it. Only
    ``database`` leaves the bundle unread."""
    refused = refusal(state)
    loaded = "" if source == "database" else _LOADED[bundle]
    if source == "packaged":
        if bundle != "shipped":
            return "raise", re.escape(_NO_LIST[bundle]), re.escape(loaded)
        return "packaged", "", ""
    if source == "database" or bundle != "shipped":
        if refused:
            return "raise", refused[0] + re.escape(refused[1]), re.escape(loaded)
        opened = OUTDATED_WARNING if state == OUTDATED else ""
        return "database", "", re.escape(opened + loaded)
    return _auto_with_a_bundle(state, refused)


def _auto_with_a_bundle(
    state: str, refused: tuple[str, str] | None
) -> tuple[str, str, str]:
    """``auto`` with the bundle shipped: the database, the bundle silently,
    or the bundle after a warning."""
    if state == OUTDATED:
        return "packaged", "", re.escape(OUTDATED_WARNING)
    if refused is None:
        return "database", "", ""
    if state in (NO_DATABASE, NO_HOME):  # no database file: silent
        return "packaged", "", ""
    fallback = re.escape(f"; using packaged data v{VERSION}\n")
    return "packaged", "", f"WARNING: {refused[0]}{fallback}"


@pytest.mark.parametrize("bundle", BUNDLES)
@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("source", RESOLVE_SOURCES)
def test_resolve_matrix(
    monkeypatch: pytest.MonkeyPatch,
    given: GivenWarnings,
    source: Source,
    state: str,
    bundle: str,
) -> None:
    """With no database given, resolve() reads the database at the default
    path or the bundle shipped in the wheel, as *source* says; a list it
    cannot read raises, a database's message unchanged from 0.6.0."""
    ship(monkeypatch, _BUNDLE_BYTES[bundle])
    build(state, monkeypatch)
    given.take()
    where, raised, said = _resolve_outcome(source, state, bundle)
    if where == "raise":
        with pytest.raises(DatabaseNotReadyError) as error:
            resolve("MIT", source=source)
        assert re.fullmatch(raised, str(error.value)), str(error.value)
    else:
        got = resolve("MIT", source=source)
        assert (got["expression"], got["category"]) == ("MIT", "exact")
        assert [(e["source"], e["version"]) for e in got["lists"]] == [(where, VERSION)]
    err = given.lines()
    assert re.fullmatch(said, err), err
    # Every warning, an opened database's and the bundle's included, is given
    # once per process (and never printed: test_library_warnings).
    with contextlib.suppress(DatabaseNotReadyError):
        resolve("MIT", source=source)
    assert given.lines() == ""


#: How a database is given to resolve(db=...).
_DB_FORMS: dict[str, Callable[[Path], object]] = {
    "handle": lambda p: LicenseDatabase(str(p), create=False),
    "new-handle": lambda p: LicenseDatabase(str(p)),  # create: the default
    "str": str,
    "path": lambda p: p,
}


@pytest.mark.parametrize("state", ["ready", "missing", "foreign"])
@pytest.mark.parametrize("form", sorted(_DB_FORMS))
@pytest.mark.parametrize("source", RESOLVE_SOURCES)
def test_resolve_matrix_with_a_database_given(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: Source,
    form: str,
    state: str,
) -> None:
    """A database given, as a handle or a path, is read as
    source="database", checked ready first; packaged contradicts it, and is
    refused rather than one of the two ignored. A missing path is never
    created."""
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "given.db"
    if state == "ready":
        make_ready_file_db(path)
    elif state == "foreign":
        path.write_text("not a database, " * 8, encoding="utf-8")
    if form == "handle" and state != "ready":
        return  # no handle to give: LicenseDatabase() itself fails on the file
    if form == "new-handle" and state == "foreign":
        # Neither is a handle to give: it refuses another program's file, and
        # leaves it as it was.
        with pytest.raises(
            DatabaseNotReadyError, match="^database: (invalid|unreadable)"
        ):
            _DB_FORMS[form](path)
        assert path.read_text(encoding="utf-8") == "not a database, " * 8
        return
    db = _DB_FORMS[form](path)
    if source == "packaged":
        message = "option: invalid: source: 'packaged' with db; pass db or source"
        with pytest.raises(InvalidInputError, match=f"^{re.escape(message)}$"):
            resolve("MIT", db, source=source)  # type: ignore[arg-type]
    elif state == "ready":
        got = resolve("MIT", db, source=source)  # type: ignore[arg-type]
        assert [entry["source"] for entry in got["lists"]] == ["database"]
    else:
        condition = "not found" if state == "missing" else "(invalid|unreadable)"
        with pytest.raises(DatabaseNotReadyError, match=f"^database: {condition}: "):
            resolve("MIT", db, source=source)  # type: ignore[arg-type]
    assert path.exists() is (state != "missing")


@pytest.mark.parametrize(
    "db", [b"licenses.db", 3, object()], ids=["bytes", "int", "object"]
)
def test_resolve_refuses_a_db_that_is_no_database(db: object) -> None:
    """Neither a database nor a path is a mistake of the caller."""
    with pytest.raises(TypeError, match="^db must be a LicenseDatabase, str or "):
        resolve("MIT", db)  # type: ignore[arg-type]


# --- CLI resolve: --source x the database at the default path x --db x --json ---

DEFAULT_DATABASES = ["usable", "missing"]


def _cli_match_outcome(source: str, default: str, given: bool) -> str | None:
    """Where ``licenseid resolve`` reads the list, or None for exit 2. The
    database and the bundle hold one List, built by this licenseid: a tie,
    which the database wins."""
    if given:
        return None if source == "packaged" else "database"
    if source == "packaged":
        return "packaged"
    if default == "missing":
        return None if source == "database" else "packaged"
    return "database"


@pytest.mark.parametrize(
    "output",
    [(), ("--verbose",), ("--json",), ("--json", "--verbose")],
    ids=["terse", "verbose", "json", "json-verbose"],
)
@pytest.mark.parametrize("given", [False, True], ids=["no-db", "db"])
@pytest.mark.parametrize("default", DEFAULT_DATABASES)
@pytest.mark.parametrize("source", RESOLVE_SOURCES)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_cli_resolve_matrix(
    monkeypatch: pytest.MonkeyPatch,
    bundle_db: LicenseDatabase,
    source: str,
    default: str,
    given: bool,
    output: tuple[str, ...],
) -> None:
    """``--db`` is read as ``resolve(value, db)``; without it, the list
    ``--source`` names, as resolve() reads it. No database is needed."""
    ship(monkeypatch, fixture_bundle())
    if default == "usable":
        path = Path(get_default_db_path())
        path.parent.mkdir(parents=True)
        shutil.copyfile(bundle_db.db_path, path)
    db = ["--db", str(bundle_db.db_path)] if given else []
    result = CliRunner().invoke(
        cli, [*db, "resolve", "--source", source, *output, "Apache2"]
    )
    where = _cli_match_outcome(source, default, given)
    if where is None:
        refused = (
            "option: invalid: --source: packaged with --db; pass --db or --source"
            if given
            else f"database: not found: {get_default_db_path()}; run 'licenseid update'"
        )
        assert (result.exit_code, result.stdout, result.stderr) == (
            2,
            "",
            f"ERROR: {refused}\n",
        )
        return
    assert (result.exit_code, result.stderr) == (0, "")
    if "--json" in output:
        got = json.loads(result.stdout)
        assert got["expression"] == "Apache-2.0"
        assert [entry["source"] for entry in got["lists"]] == [where]
    elif "--verbose" not in output:
        assert result.stdout == "Apache-2.0\n"
    else:
        assert result.stdout.splitlines()[0] == (
            "EXPRESSION=Apache-2.0\tCATEGORY=version_spelling\tTRUST=resolver_rule"
        )

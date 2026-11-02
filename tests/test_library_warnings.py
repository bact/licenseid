# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The warnings licenseid gives: each a :class:`licenseid.LicenseIdWarning`
through Python's ``warnings`` (one emitter, ``licenseid.warning.warn``), and
one ``WARNING:`` line per event from the CLI."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import copy
import inspect
import json
import os
import re
import time
import warnings
from collections.abc import Callable, Generator
from pathlib import Path
from unittest import mock

import pytest
import requests
from click.testing import CliRunner
from conftest import fake_requests_get, invoke_match
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db, writer
from matcher_db import seeded_db
from release_fakes import (
    bundle_url,
    online,
    release_bundle,
    serve,
    ship,
    tarball_url,
    without,
)
from resolve_states import EMPTY, OUTDATED_WARNING, VERSION, build
from test_looseid import ROWS as LOOSE_ROWS

import licenseid
from licenseid import keptdetector, listsource, spdx_source, warning
from licenseid.cli import cli
from licenseid.clicommon import printed_warnings
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.records import BUILD_VERSION
from licenseid.textinput import decode_input
from licenseid.warning import LicenseIdWarning, once, parts

ROWS = LOOSE_ROWS  # the GPL and LGPL rows, deprecated IDs included
TWO_TAGS = (
    "SPDX-License-Identifier: GPL-2.0\n/* x */\nSPDX-License-Identifier: LGPL-2.1\n"
)
STALE = re.compile(r"WARNING: database: \d+ days old; run 'licenseid update'")
NARROWED = "WARNING: input: variant not stated: {}; using {}\n"


Parts = tuple[str, str, str | None, str | None]
OUTDATED: Parts = (
    "database",
    "build v1 outdated",
    f"current v{BUILD_VERSION}",
    "run 'licenseid update'",
)


def parts_of(given: list[warnings.WarningMessage]) -> list[Parts]:
    """The parts of each LicenseIdWarning *given*, in order."""
    return [
        (w.message.subject, w.message.condition, w.message.detail, w.message.action)
        for w in given
        if isinstance(w.message, LicenseIdWarning)
    ]


def narrowed(value: str, resolved: str) -> Parts:
    return ("input", "variant not stated", value, f"using {resolved}")


@pytest.fixture(autouse=True)
def forget() -> Generator[None, None, None]:
    """No warning given once, and no detector kept, by an earlier test."""
    warning.reset_once()
    keptdetector.reset()
    listsource.reset_choice()
    yield
    warning.reset_once()
    keptdetector.reset()
    listsource.reset_choice()


@pytest.fixture
def memory_db() -> Generator[str, None, None]:
    yield from seeded_db("test_library_warnings", ROWS)


@pytest.fixture
def outdated_db(tmp_path: Path) -> Path:
    """A ready file database stamped with an older build."""
    path = make_ready_file_db(tmp_path / "old.db")
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '1' WHERE key = 'build_version'")
    return path


# --- The CLI: one line per warning, as before -------------------------------


def test_cli_prints_two_tag_warnings_in_one_run(memory_db: str, tmp_path: Path) -> None:
    source = tmp_path / "two.c"
    source.write_text(TWO_TAGS, encoding="utf-8")
    result = invoke_match(memory_db, str(source))
    assert result.exit_code == 0
    # The CLI's own warning first (the seeded database was checked long ago),
    # then the library's, in the order they were given.
    stale, rest = result.stderr.split("\n", 1)
    assert STALE.fullmatch(stale)
    assert rest == NARROWED.format("GPL-2.0", "GPL-2.0-only") + NARROWED.format(
        "LGPL-2.1", "LGPL-2.1-only"
    )


def test_cli_prints_the_outdated_database(outdated_db: Path) -> None:
    for command in (["detect", "--id", "MIT"], ["match", "MIT"]):
        result = CliRunner().invoke(cli, ["--db", str(outdated_db), *command])
        assert result.exit_code == 0, result.output
        assert result.stderr == OUTDATED_WARNING


def test_cli_prints_latin1_input(memory_db: str, tmp_path: Path) -> None:
    source = tmp_path / "latin.txt"
    source.write_bytes(b"MIT caf\xe9\n")
    result = invoke_match(memory_db, str(source))
    stale, rest = result.stderr.split("\n", 1)
    assert STALE.fullmatch(stale)
    assert rest == f"WARNING: input: not UTF-8, read as Latin-1: {source}\n"


# --- The warning and its parts ---------------------------------------------


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (("database", "compact failed"), "database: compact failed"),
        (("input", "c", "d"), "input: c: d"),
        (("popularity.csv", "missing", None, "a"), "popularity.csv: missing; a"),
        (("input", "c", "d: e", "a b"), "input: c: d: e; a b"),
        (("database", "empty", ""), "database: empty: "),  # "" is a detail
    ],
)
def test_a_warning_is_its_parts_in_the_grammar(args: Parts, text: str) -> None:
    given = LicenseIdWarning(*args)
    padded = (*args, None, None)[:4]
    assert (str(given), given.args) == (text, (text,))
    assert (given.subject, given.condition, given.detail, given.action) == padded
    again = copy.deepcopy(given)  # rebuilt from its parts, not its text
    assert (again.subject, again.condition, again.detail, again.action) == padded
    assert str(again) == text


def test_the_warning_is_public_and_a_user_warning() -> None:
    assert licenseid.LicenseIdWarning is LicenseIdWarning
    assert "LicenseIdWarning" in licenseid.__all__
    assert issubclass(LicenseIdWarning, UserWarning)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("licenses.json: download failed", ("licenses.json", "download failed", None)),
        ("a.gz: invalid: Type: x: y", ("a.gz", "invalid", "Type: x: y")),
        ("database: empty: C:\\db", ("database", "empty", "C:\\db")),
    ],
)
def test_parts_reads_subject_condition_and_detail(
    text: str, expected: tuple[str, str, str | None]
) -> None:
    assert parts(text) == expected
    assert str(LicenseIdWarning(*parts(text))) == text


def test_report_is_gone() -> None:
    for made in (LicenseDatabase, LicenseDetector):
        assert "report" not in inspect.signature(made).parameters


# --- Each source of a warning, through warnings and never stderr ------------


def _detect_tags(db: str) -> object:
    return LicenseDetector(db).detect(text=TWO_TAGS)


def _is_osi_tags(db: str) -> object:
    return LicenseDetector(db).is_osi(text=TWO_TAGS)


def _detect_function_tags(db: str) -> object:
    with mock.patch(
        "licenseid.keptdetector.get_default_db_path",
        mock.create_autospec(get_default_db_path, return_value=db),
    ):
        return licenseid.detect(text=TWO_TAGS)


@pytest.mark.parametrize("call", [_detect_tags, _is_osi_tags, _detect_function_tags])
def test_a_narrowed_tag_is_a_warning(
    memory_db: str, capsys: pytest.CaptureFixture[str], call: Callable[[str], object]
) -> None:
    with pytest.warns(LicenseIdWarning) as given:
        call(memory_db)
    assert parts_of(given.list) == [
        narrowed("GPL-2.0", "GPL-2.0-only"),
        narrowed("LGPL-2.1", "LGPL-2.1-only"),
    ]
    # Attributed to the caller's line, not to licenseid's.
    assert {w.filename for w in given.list} == {__file__}
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        ("1", OUTDATED),
        ("99", ("database", "build v99 newer", f"current v{BUILD_VERSION}", None)),
    ],
)
def test_a_database_stamp_is_a_warning(
    outdated_db: Path,
    capsys: pytest.CaptureFixture[str],
    stamp: str,
    expected: Parts,
) -> None:
    with writer(outdated_db) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = ? WHERE key = 'build_version'", (stamp,)
        )
    with pytest.warns(LicenseIdWarning) as given:
        LicenseDetector(str(outdated_db))
    assert parts_of(given.list) == [expected]
    assert given.list[0].filename == __file__
    assert capsys.readouterr() == ("", "")


def test_latin1_input_is_a_warning(
    memory_db: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "LICENSE"
    source.write_bytes(b"MIT caf\xe9\n")
    with pytest.warns(LicenseIdWarning) as given:
        decoded = decode_input(b"caf\xe9", "stdin")
    with pytest.warns(LicenseIdWarning) as read:
        LicenseDetector(memory_db).detect(file_path=str(source))
    assert decoded == "caf\xe9"
    given.list.extend(read.list)
    latin1 = ("input", "not UTF-8, read as Latin-1")
    assert parts_of(given.list) == [
        (*latin1, "stdin", None),
        (*latin1, str(source), None),
    ]
    assert capsys.readouterr() == ("", "")


def test_a_cache_fallback_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A step of update, called on its own: its fallbacks are warnings too."""
    cache = tmp_path / spdx_source.CACHE_LICENSES_JSON
    cache.write_text(json.dumps({"licenseListVersion": "3.28.0"}), encoding="utf-8")
    old = time.time() - 100 * 86400
    os.utime(cache, (old, old))
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    with pytest.warns(LicenseIdWarning) as given:
        got = spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert got[0] == "3.28.0"
    assert parts_of(given.list) == [
        (
            "licenses.json",
            "download failed",
            "ConnectionError: down",
            "using stale cache",
        )
    ]
    # Fetching prints its progress; the warning is given, not printed.
    assert "WARNING" not in capsys.readouterr().err


def test_the_packaged_list_fallback_is_a_warning_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    build(EMPTY, monkeypatch)
    with pytest.warns(LicenseIdWarning) as given:
        assert licenseid.match("MIT")["lists"][0]["source"] == "packaged"
    assert parts_of(given.list) == [
        (
            "database",
            "empty",
            get_default_db_path(),
            f"using packaged data v{VERSION}",
        )
    ]
    with warnings.catch_warnings(record=True) as again:
        warnings.simplefilter("always")
        licenseid.match("MIT")
    assert parts_of(again) == []  # once per process, as before
    assert capsys.readouterr() == ("", "")


def test_an_unusable_packaged_list_is_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, b"bad")
    with pytest.warns(LicenseIdWarning) as given:
        assert licenseid.listindex.packaged_index() is None
    ((subject, condition, detail, action),) = parts_of(given.list)
    assert (subject, condition, action) == ("spdx-bundle.json.gz", "invalid", None)
    assert detail is not None and detail.startswith("BadGzipFile: ")


def test_an_error_filter_makes_the_api_raise(memory_db: str, outdated_db: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", LicenseIdWarning)
        with pytest.raises(LicenseIdWarning, match="^database: build v1 outdated"):
            LicenseDetector(str(outdated_db))
        with pytest.raises(LicenseIdWarning) as raised:
            LicenseDetector(memory_db).detect(text=TWO_TAGS)
    assert raised.value.condition == "variant not stated"


def test_an_ignore_filter_silences_them(
    memory_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("ignore", LicenseIdWarning)
        LicenseDetector(memory_db).detect(text=TWO_TAGS)
    assert (given, capsys.readouterr()) == ([], ("", ""))


def _give_twice() -> None:
    for _ in range(2):
        warning.warn("input", "variant not stated", "GPL-2.0", "using GPL-2.0-only")


def test_once_gives_a_text_once_per_process() -> None:
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always")
        _give_twice()
        with once():
            _give_twice()  # given before, but not within once()
            _give_twice()
        with once():
            _give_twice()
    assert len(parts_of(given)) == 3


def _outdated_at_default_path() -> Path:
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    make_ready_file_db(path)
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '1' WHERE key = 'build_version'")
    return path


def _by_path(outdated_db: Path, _: pytest.MonkeyPatch) -> Callable[[], object]:
    return lambda: licenseid.match("MIT", db=str(outdated_db))


def _by_detect(_db: Path, _: pytest.MonkeyPatch) -> Callable[[], object]:
    _outdated_at_default_path()
    return lambda: licenseid.detect(license_id="MIT")


def _by_fallback(_db: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], object]:
    ship(monkeypatch, release_bundle(VERSION))
    build(EMPTY, monkeypatch)
    return lambda: licenseid.match("MIT")


def _reopen() -> None:
    """Forget what was kept, as a change to the file would."""
    keptdetector.reset()
    listsource.reset_choice()


@pytest.mark.parametrize("path", [_by_path, _by_detect, _by_fallback])
def test_a_raised_or_ignored_warning_is_not_counted_as_given(
    outdated_db: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: Callable[[Path, pytest.MonkeyPatch], Callable[[], object]],
) -> None:
    """P188: within once(), only a warning given counts. One a filter raised
    raises again at the next call; one a filter ignored is given at the next
    call that is not ignored, and then no more."""
    call = path(outdated_db, monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("error", LicenseIdWarning)
        for _ in range(3):
            with pytest.raises(LicenseIdWarning):
                call()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        call()
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always", LicenseIdWarning)
        for _ in range(3):
            _reopen()
            call()
    assert len(parts_of(given)) == 1


def test_an_ignore_filter_for_something_else_still_counts_as_given() -> None:
    """A filter for another line, or another category, does not apply: the
    warning is shown, so once() gives it once."""
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", category=LicenseIdWarning, lineno=1)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        with once():
            _give_twice()
    assert len(parts_of(given)) == 1


def test_match_with_a_path_warns_once_when_it_opens_again(outdated_db: Path) -> None:
    """match(db=path) opens the file again when it changes; its stamp warning
    is still given once per process (listsource._opened, within once())."""
    with pytest.warns(LicenseIdWarning) as first:
        licenseid.match("MIT", db=str(outdated_db))
    # pylint: disable-next=protected-access
    opened = listsource._paths[str(outdated_db)][1]
    with writer(outdated_db) as conn:
        conn.execute("INSERT OR REPLACE INTO db_metadata VALUES ('k', 'v')")
    with warnings.catch_warnings(record=True) as again:
        warnings.simplefilter("always")
        assert licenseid.match("MIT", db=str(outdated_db))["expression"] == "MIT"
    # pylint: disable-next=protected-access
    assert listsource._paths[str(outdated_db)][1] is not opened  # opened again
    assert (parts_of(first.list), parts_of(again)) == ([OUTDATED], [])


def test_a_warning_behind_a_cached_property_names_the_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P177: an unusable snapshot is said in ReleaseChain._fallback, a
    functools.cached_property, whose frame stands between licenseid's: the
    warning still names this file, not functools."""
    serve(monkeypatch, without(online(), bundle_url(), tarball_url()))
    ship(monkeypatch, b"garbage")
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always", LicenseIdWarning)
        with pytest.raises(licenseid.LicenseIdError):
            LicenseDatabase(str(tmp_path / "licenses.db")).update_from_remote()
    snapshot = [w for w in given if "spdx-bundle.json.gz" in str(w.message)]
    assert len(snapshot) == 1
    assert {w.filename for w in given} == {__file__}


# --- The CLI's printer --------------------------------------------------------


def test_the_cli_prints_every_event(capsys: pytest.CaptureFixture[str]) -> None:
    """The same warning from the same line twice is two lines: no filter of
    the caller's (here "ignore") and no registry hides the second."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _give_twice()  # registered nowhere, printed nowhere
        with printed_warnings():
            _give_twice()
    line = "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-only\n"
    assert capsys.readouterr() == ("", line * 2)


def test_the_cli_leaves_other_warnings_to_python(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always")
        with printed_warnings():
            warnings.warn("not ours", DeprecationWarning, stacklevel=1)
            warning.warn("input", "empty")
    assert [str(w.message) for w in given] == ["not ours"]
    assert capsys.readouterr() == ("", "WARNING: input: empty\n")


def test_the_cli_restores_python_after_a_command(memory_db: str) -> None:
    shown = warnings.showwarning
    filters = list(warnings.filters)
    invoke_match(memory_db, "--id", "MIT")
    assert (warnings.showwarning, warnings.filters) == (shown, filters)

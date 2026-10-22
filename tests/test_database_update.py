# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for LicenseDatabase.update_from_remote() and tarball
extraction: a small synthetic SPDX release and a faked requests.get."""
# pylint: disable=missing-function-docstring,protected-access

import contextlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import requests
from click.testing import CliRunner
from conftest import assert_cached_tarball_removed
from db_variants import make_ready_file_db
from release_fakes import (
    POPULARITY_CSV,
    bundle_url,
    listing,
    release_tarball,
    serve,
    stub_chain,
    tarball,
    tarball_url,
    urls,
    version_json,
)

from licenseid import AggregatedLicenseMatcher, spdx_source
from licenseid.cli import cli
from licenseid.console import warn
from licenseid.database import LicenseDatabase
from licenseid.errors import LicenseIdError
from licenseid.spdxdata import SpdxData

_LICENSES = listing()


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    tarball_bytes: bytes,
    popularity_csv: str = POPULARITY_CSV,
) -> mock.MagicMock:
    """Fake the remote sources of the tarball path by URL: spdx.org's
    licenses.json, the popularity data and the 9.99 tarball. Our latest.json
    and bundle are a 404, as before they are published."""
    return serve(
        monkeypatch,
        {
            spdx_source.LICENSES_JSON_URL: version_json(),
            spdx_source.POPULARITY_DATA_URL: popularity_csv,
            tarball_url(): tarball_bytes,
        },
    )


def test_update_from_remote_end_to_end_then_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    fake = _serve(monkeypatch, release_tarball())

    assert db.update_from_remote()
    # Our latest.json and bundle are a 404, so spdx.org and the tarball follow.
    assert urls(fake) == [
        spdx_source.LATEST_JSON_URL,
        spdx_source.LICENSES_JSON_URL,
        bundle_url(),
        tarball_url(),
        spdx_source.POPULARITY_DATA_URL,  # after the data: a skip needs none
    ]
    assert db.get_metadata()["license_list_version"] == "9.99"
    details = db.get_license_details("MIT")
    assert details is not None
    assert details["pop_score"] == 1000  # from the popularity data
    err = capsys.readouterr().err
    assert "GitHub license ranking data  : remote" in err
    assert "SPDX License List data       : tarball (remote)" in err

    cache_files = {p.name for p in tmp_path.iterdir()}
    assert {"licenses.json", "popularity.csv", "spdx-data-v9.99.tar.gz"} <= cache_files
    assert not [name for name in cache_files if name.endswith(".tmp")]

    # Second run: everything cached and the version matches, so no requests.
    fake.reset_mock()
    assert not db.update_from_remote()
    fake.assert_not_called()


@pytest.mark.parametrize("template", ["file:{p}", "file://{p}", "file://localhost{p}"])
def test_update_of_a_file_uri_caches_beside_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str
) -> None:
    """The cache goes where the URI says the database is, not into a
    "file:" directory made from the URI's text."""
    posix = (tmp_path / "licenses.db").as_posix()
    where = posix if posix.startswith("/") else f"/{posix}"
    (tmp_path / "cwd").mkdir()
    monkeypatch.chdir(tmp_path / "cwd")
    db = LicenseDatabase(template.format(p=where))
    _serve(monkeypatch, release_tarball())
    assert db.update_from_remote()
    cache_files = {p.name for p in tmp_path.iterdir()}
    assert {"licenses.json", "popularity.csv", "spdx-data-v9.99.tar.gz"} <= cache_files
    assert not list((tmp_path / "cwd").iterdir())


def test_a_file_uri_keeps_its_query_when_opened(tmp_path: Path) -> None:
    """SQLite gets the URI as given: a bare path would drop ``mode=ro``."""
    path = make_ready_file_db(tmp_path / "ro.db")
    posix = path.as_posix()
    where = posix if posix.startswith("/") else f"/{posix}"
    db = LicenseDatabase(f"file://{where}?mode=ro")
    connections = db._connections  # pylint: disable=protected-access
    with (
        pytest.raises(sqlite3.OperationalError, match="readonly"),
        connections.connect() as conn,
    ):
        conn.execute("DELETE FROM db_metadata")


def test_update_succeeds_when_the_temporary_files_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows: antivirus or the indexer holds an extracted file, so the
    clean-up raises after the database was already updated."""
    held = {"MIT.txt", "licenses.json", "exceptions.json"}
    real_unlink = os.unlink

    def unlink(
        path: str | bytes | os.PathLike[str], *args: object, **kw: object
    ) -> None:
        if os.path.basename(os.fsdecode(path)) in held:
            raise PermissionError(13, "in use")
        real_unlink(path, *args, **kw)  # type: ignore[arg-type]

    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    _serve(monkeypatch, release_tarball())
    # The clean-up is stopped, so what it leaves must land under tmp_path.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    # The same names in the cache directory are never unlinked by update.
    monkeypatch.setattr(os, "unlink", unlink)
    assert db.update_from_remote()
    assert db.get_metadata()["license_list_version"] == "9.99"


def test_a_tarball_that_cannot_be_written_is_a_cache_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows: the destination is open (another update, a virus scan), so the
    rename is refused. One grammar line, not "update failed: PermissionError"."""
    _serve(monkeypatch, release_tarball())

    def refuse(src: object, dst: object) -> None:
        raise PermissionError(13, "in use")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_tarball_path(tmp_path, "9.99", use_cache=False)
    assert str(info.value).startswith("spdx-data-v9.99.tar.gz: cache write failed: ")


def test_forced_update_reuses_all_caches_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    fake = _serve(monkeypatch, release_tarball())
    db.update_from_remote()
    fake.reset_mock()
    capsys.readouterr()

    assert db.update_from_remote(force=True)
    fake.assert_not_called()
    err = capsys.readouterr().err
    assert "GitHub license ranking data  : cache" in err
    assert "SPDX License List data       : tarball (cache)" in err


def test_unsafe_cached_tarball_is_removed_and_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    tar_path.write_bytes(tarball({"../evil.txt": b"pwned"}))
    assert_cached_tarball_removed(db, tar_path, capsys)


def test_cli_update_reports_success_then_no_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "licenses.db")
    _serve(monkeypatch, release_tarball())
    runner = CliRunner()

    first = runner.invoke(cli, ["--db", db_path, "update"])
    assert first.exit_code == 0, first.output
    assert first.stdout == f"Database updated at {db_path}\n"
    assert "Data sources:" in first.stderr
    assert "Update complete." in first.stderr

    second = runner.invoke(cli, ["--db", db_path, "update"])
    assert second.exit_code == 0, second.output
    assert second.stdout == f"Database remains at version 9.99 at {db_path}\n"
    assert "Skipping update" in second.stderr


def test_cli_clear_cache_prints_nothing_on_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "licenses.db"
    _serve(monkeypatch, release_tarball())
    runner = CliRunner()
    assert runner.invoke(cli, ["--db", str(db_path), "update"]).exit_code == 0

    result = runner.invoke(cli, ["--db", str(db_path), "--clear-cache"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Clearing cache..." in result.stderr
    assert not db_path.exists()


def test_cli_update_warnings_go_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Warnings must not mix with the result line on standard output."""
    db_path = str(tmp_path / "licenses.db")
    _serve(
        monkeypatch,
        release_tarball(),
        popularity_csv="spdx_license,num_pushers\nMIT,1000\nApache-2.0,\n",
    )
    result = CliRunner().invoke(cli, ["--db", db_path, "update"])
    assert result.exit_code == 0, result.output
    assert "WARNING: popularity.csv: 1 rows with missing" in result.stderr
    assert "WARNING" not in result.stdout
    assert "Warning" not in result.stdout
    assert f"Database updated at {db_path}" in result.stdout


def test_cli_update_unexpected_error_keeps_message_grammar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception that is not one of the worded RuntimeErrors (here a
    KeyError from an exception entry without a name) still prints one
    grammar line, not the bare exception text."""
    root = "license-list-data-9.99"
    exceptions = {"exceptions": [{"licenseExceptionId": "E-1"}]}
    archive = tarball(
        {
            f"{root}/json/licenses.json": json.dumps(_LICENSES).encode(),
            f"{root}/json/exceptions.json": json.dumps(exceptions).encode(),
        }
    )
    _serve(monkeypatch, archive)
    result = CliRunner().invoke(cli, ["--db", str(tmp_path / "x.db"), "update"])
    assert result.exit_code == 1
    assert result.stdout == ""
    errors = [line for line in result.stderr.splitlines() if line.startswith("ERROR")]
    assert errors == ["ERROR: database: update failed: KeyError: 'name'"]


def test_cli_update_recursion_error_is_not_passed_through_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RecursionError subclasses RuntimeError; a deeply nested licenses.json
    in the release must still give a grammar line, not the bare text."""
    root = "license-list-data-9.99"
    nested = ("[" * 200_000 + "]" * 200_000).encode()
    _serve(monkeypatch, tarball({f"{root}/json/licenses.json": nested}))
    result = CliRunner().invoke(cli, ["--db", str(tmp_path / "x.db"), "update"])
    assert result.exit_code == 1
    errors = [line for line in result.stderr.splitlines() if line.startswith("ERROR")]
    assert len(errors) == 1
    assert errors[0].startswith(
        "ERROR: spdx-data-v9.99.tar.gz: download unusable: RecursionError: "
    )


def test_cli_update_unopenable_database_path_is_an_error_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _serve(monkeypatch, release_tarball())
    db_path = tmp_path / "no" / "such" / "x.db"
    result = CliRunner().invoke(cli, ["--db", str(db_path), "update"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR: database: update failed: OperationalError: "
        "unable to open database file\n"
    )
    fake.assert_not_called()


def test_cli_update_exception_without_message_has_no_dangling_colon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        LicenseDatabase,
        "update_from_remote",
        mock.create_autospec(
            LicenseDatabase.update_from_remote, side_effect=StopIteration
        ),
    )
    result = CliRunner().invoke(cli, ["--db", str(tmp_path / "x.db"), "update"])
    assert result.exit_code == 1
    assert result.stderr == "ERROR: database: update failed: StopIteration\n"


def test_cli_update_failure_is_a_short_error_and_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake: mock.MagicMock = mock.create_autospec(
        requests.get, side_effect=requests.ConnectionError("network down")
    )
    monkeypatch.setattr(requests, "get", fake)
    result = CliRunner().invoke(cli, ["--db", str(tmp_path / "x.db"), "update"])
    assert result.exit_code == 1
    assert "ERROR: licenses.json: download failed: " in result.stderr
    assert "network down" in result.output
    assert "Traceback" not in result.output
    # One attempt per version file (latest.json, licenses.json), no retry loop.
    assert fake.call_count == 2


@pytest.mark.parametrize("version", ["../../evil", ""])
def test_cli_update_rejects_unsafe_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    """An empty --version is invalid too, not silently "latest"."""
    fake = _serve(monkeypatch, release_tarball())
    result = CliRunner().invoke(
        cli, ["--db", str(tmp_path / "x.db"), "update", "--version", version]
    )
    assert result.exit_code == 2  # invalid parameter: usage error (README)
    assert result.stderr == f"ERROR: version: invalid: {version!r}\n"
    fake.assert_not_called()
    assert not list(tmp_path.glob("**/*evil*"))


@pytest.mark.parametrize("use_cache", [True, False])
def test_update_passes_no_cache_flag_to_stale_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_cache: bool
) -> None:
    """--no-cache must also disable the stale-cache fallback."""
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    fetch = mock.create_autospec(
        spdx_source.fetch_popularity_data, return_value=({"MIT": 1}, "remote")
    )
    monkeypatch.setattr(spdx_source, "fetch_popularity_data", fetch)
    monkeypatch.setattr(
        spdx_source, "get_version_info", lambda *_: ("9.99", None, "remote")
    )
    stub_chain(monkeypatch, db)
    assert db.update_from_remote(force=True, use_cache=use_cache)
    assert fetch.call_args.kwargs["allow_stale"] is use_cache


def test_failure_mid_progress_line_leaves_stderr_at_line_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A library caller that catches the exception and writes its own
    stderr text must not have it glued to the progress dots."""
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    root = "license-list-data-9.99"
    exceptions = {"exceptions": [{"licenseExceptionId": "E-1"}]}
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    tar_path.write_bytes(
        tarball(
            {
                f"{root}/json/licenses.json": json.dumps(_LICENSES).encode(),
                f"{root}/json/exceptions.json": json.dumps(exceptions).encode(),
            }
        )
    )
    capsys.readouterr()
    with pytest.raises(KeyError):
        db._store(SpdxData.from_tarball(tar_path), {}, None)
    err = capsys.readouterr().err
    assert "Preparing license data..." in err
    assert err.endswith("\n")
    warn("popularity.csv: using stale cache")
    assert capsys.readouterr().err == "WARNING: popularity.csv: using stale cache\n"


def _journal_mode(path: Path) -> str:
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return str(conn.execute("PRAGMA journal_mode").fetchone()[0])


def test_update_builds_a_database_without_wal_and_a_lookup_leaves_no_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "licenses.db"
    db = LicenseDatabase(str(path))
    _serve(monkeypatch, release_tarball())
    assert db.update_from_remote()
    assert _journal_mode(path) == "delete"
    AggregatedLicenseMatcher(db_path=str(path)).match(license_id="MIT")
    assert sorted(p.name for p in tmp_path.glob("licenses.db*")) == ["licenses.db"]


def test_update_takes_a_database_of_an_earlier_version_out_of_wal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Also when it has nothing to download: the next run converts it."""
    path = tmp_path / "licenses.db"
    db = LicenseDatabase(str(path))
    _serve(monkeypatch, release_tarball())
    assert db.update_from_remote()
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
    assert _journal_mode(path) == "wal"
    assert not db.update_from_remote()  # already at the version
    assert _journal_mode(path) == "delete"


def test_a_failed_fingerprint_write_leaves_a_database_update_does_not_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The version is stamped after the fingerprints: a lock that fails their
    write must not make the next plain update skip them for ever."""
    path = tmp_path / "licenses.db"
    db = LicenseDatabase(str(path))
    _serve(monkeypatch, release_tarball())
    with (
        mock.patch(
            "licenseid.database.store_fingerprints",
            autospec=True,
            side_effect=sqlite3.OperationalError("database is locked"),
        ),
        pytest.raises(LicenseIdError, match="update failed"),
    ):
        db.update_from_remote()
    assert not db.get_metadata().get("license_list_version")
    assert db.update_from_remote()  # not skipped
    assert db.get_metadata().get("license_list_version")


def test_a_failed_update_leaves_no_old_version_over_new_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``update --version <old>`` must not skip a half-updated database."""
    path = tmp_path / "licenses.db"
    db = LicenseDatabase(str(path))
    _serve(monkeypatch, release_tarball())
    assert db.update_from_remote()
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = '1.0' WHERE key = 'license_list_version'"
        )
        conn.commit()
    with (
        mock.patch(
            "licenseid.database.store_fingerprints",
            autospec=True,
            side_effect=sqlite3.OperationalError("database is locked"),
        ),
        pytest.raises(LicenseIdError),
    ):
        db.update_from_remote(force=True)
    assert db.get_metadata().get("license_list_version") is None

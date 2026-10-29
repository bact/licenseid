# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Each source of ``update`` on its own (licenseid.releasesource): where its
version and data come from, that an explicit source has no fallback, and the
request and CLI option. No test touches the network."""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from click.testing import CliRunner
from release_fakes import (
    BUNDLE,
    LATEST,
    POPULARITY,
    SPDX_ORG,
    TARBALL,
    bundle_url,
    data_line,
    db_version,
    online,
    open_db,
    release_bundle,
    release_tarball,
    serve,
    ship,
    tarball_url,
    urls,
    version_json,
    warnings_of,
    without,
)

from licenseid import releasesource
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.errors import InvalidInputError, LicenseIdError
from licenseid.spdxdata import is_older
from licenseid.types import UpdateSource

# --- each source on its own ---


def test_auto_takes_the_compact_bundle_and_the_version_from_latest_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, online())
    assert db.update_from_remote()
    assert urls(fake) == [LATEST, bundle_url(), POPULARITY]
    assert db_version(db) == "9.99"
    err = capsys.readouterr().err
    assert data_line(err) == "  - SPDX License List data       : compact (remote)"
    assert not warnings_of(err)
    assert (tmp_path / BUNDLE).exists()
    assert not (tmp_path / TARBALL).exists()
    details = db.get_license_details("MIT")
    assert details is not None and details["pop_score"] == 1000


def test_a_forced_rerun_reads_the_cached_compact_file_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, online())
    assert db.update_from_remote()
    fake.reset_mock()
    capsys.readouterr()
    assert db.update_from_remote(force=True)
    fake.assert_not_called()
    assert "data       : compact (cache)" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("compact", [LATEST, bundle_url(), POPULARITY]),
        ("upstream", [SPDX_ORG, tarball_url(), POPULARITY]),
    ],
)
def test_an_explicit_source_reads_its_own_version_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: UpdateSource,
    expected: list[str],
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, online())
    assert db.update_from_remote(source=source)
    assert urls(fake) == expected
    assert db_version(db) == "9.99"


def test_the_compact_source_never_asks_spdx_org_for_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spdx.org can name a version the compact source does not have yet."""
    fake = serve(monkeypatch, without(online(), LATEST))
    with pytest.raises(LicenseIdError, match="^latest.json: download failed: "):
        open_db(tmp_path).update_from_remote(source="compact")
    assert urls(fake) == [LATEST]


def test_an_upstream_run_does_not_steer_a_later_compact_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spdx.org names 9.99 before our compact file of it is out: the version
    the upstream run cached must not send the compact run to a 404."""
    routes = online("9.98")
    routes.update({SPDX_ORG: version_json("9.99"), tarball_url(): release_tarball()})
    fake = serve(monkeypatch, routes)
    assert open_db(tmp_path).update_from_remote(source="upstream")
    assert (tmp_path / "licenses.json").exists()
    assert not (tmp_path / "latest.json").exists()

    fake.reset_mock()
    other = LicenseDatabase(str(tmp_path / "other.db"))  # the same cache files
    assert other.update_from_remote(source="compact")
    assert db_version(other) == "9.98"
    assert urls(fake) == [LATEST, bundle_url("9.98")]  # popularity: cached

    fake.reset_mock()  # each file is read from its own cache now
    assert open_db(tmp_path).update_from_remote(source="upstream", force=True)
    assert other.update_from_remote(source="compact", force=True)
    assert urls(fake) == []


def test_the_packaged_source_makes_no_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, online())
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote(source="packaged")
    fake.assert_not_called()
    assert db_version(db) == "9.98"
    err = capsys.readouterr().err
    assert "  - SPDX License List metadata   : packaged\n" in err
    assert "  - SPDX License List data       : packaged\n" in err
    assert "  - GitHub license ranking data  : unavailable\n" in err
    assert warnings_of(err) == ["WARNING: popularity.csv: missing"]


def test_the_packaged_source_uses_a_cached_popularity_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "popularity.csv").write_text("spdx_license,num_pushers\nMIT,700\n")
    db = open_db(tmp_path)
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote(source="packaged")
    assert "ranking data  : cache" in capsys.readouterr().err
    details = db.get_license_details("MIT")
    assert details is not None and details["pop_score"] == 700


@pytest.mark.parametrize(
    ("raw", "version", "error"),
    [
        (None, None, "spdx-bundle.json.gz: not found"),
        (b"garbage", None, "spdx-bundle.json.gz: invalid: BadGzipFile: "),
        (
            release_bundle("9.98"),
            "9.99",
            "spdx-bundle.json.gz: not found: version 9.99 (packaged: 9.98)",
        ),
    ],
    ids=["absent", "invalid", "other_version"],
)
def test_the_packaged_source_without_the_data_is_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes | None,
    version: str | None,
    error: str,
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, online())
    ship(monkeypatch, raw)
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote(version=version, source="packaged")
    assert str(info.value).startswith(error)
    fake.assert_not_called()
    assert db_version(db) is None


@pytest.mark.parametrize("source", ["compact", "upstream"])
def test_an_explicit_source_has_no_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: str,
) -> None:
    db_path = str(tmp_path / "licenses.db")
    fake = serve(monkeypatch, without(online(), bundle_url(), tarball_url()))
    ship(monkeypatch, release_bundle())
    result = CliRunner().invoke(cli, ["--db", db_path, "update", "--source", source])
    assert result.exit_code == 1
    name = BUNDLE if source == "compact" else TARBALL
    assert result.stderr.endswith(
        f"ERROR: {name}: download failed: HTTPError: 404 "
        f"Client Error: Not Found for url: "
        f"{bundle_url() if source == 'compact' else tarball_url()}\n"
    )
    assert not warnings_of(result.stderr)
    assert urls(fake)[-1] == (bundle_url() if source == "compact" else tarball_url())
    capsys.readouterr()


# --- the packaged source never makes a database older by default ---


def test_an_older_snapshot_is_refused_unless_forced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, online())
    assert db.update_from_remote()
    ship(monkeypatch, release_bundle("9.98"))
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote(source="packaged")
    assert str(info.value) == (
        "spdx-bundle.json.gz: older than the database: v9.98 < v9.99; "
        "run 'licenseid update --source packaged --force'"
    )
    assert db_version(db) == "9.99"
    assert db.update_from_remote(source="packaged", force=True)
    assert db_version(db) == "9.98"


def test_an_older_snapshot_named_by_version_is_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--version names the downgrade, as it does for compact and upstream."""
    db = open_db(tmp_path)
    serve(monkeypatch, online())
    assert db.update_from_remote()
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote(version="9.98", source="packaged")
    assert db_version(db) == "9.98"


def test_the_cli_refuses_an_older_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "licenses.db")
    serve(monkeypatch, online())
    runner = CliRunner()
    assert runner.invoke(cli, ["--db", db_path, "update"]).exit_code == 0
    ship(monkeypatch, release_bundle("9.98"))
    result = runner.invoke(cli, ["--db", db_path, "update", "--source", "packaged"])
    assert (result.exit_code, result.stdout) == (1, "")
    assert result.stderr.endswith(
        "ERROR: spdx-bundle.json.gz: older than the database: v9.98 < v9.99; "
        "run 'licenseid update --source packaged --force'\n"
    )
    forced = ["--db", db_path, "update", "--source", "packaged", "--force"]
    result = runner.invoke(cli, forced)
    assert result.exit_code == 0, result.output


# --- the request ---


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"source": "nope"},
            (
                "option: invalid: source: 'nope'; pass one of auto, compact, "
                "upstream, packaged"
            ),
        ),
        ({"version": "../x", "source": "packaged"}, "version: invalid: '../x'"),
    ],
    ids=["source", "version"],
)
def test_an_invalid_request_is_refused_before_any_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, str],
    message: str,
) -> None:
    fake = serve(monkeypatch, online())
    with pytest.raises(InvalidInputError) as info:
        open_db(tmp_path).update_from_remote(**kwargs)  # type: ignore[arg-type]
    assert str(info.value) == message
    fake.assert_not_called()


def test_the_cli_refuses_an_unknown_source(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli, ["--db", str(tmp_path / "x.db"), "update", "--source", "nope"]
    )
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: option: invalid: --source: ")
    assert not (tmp_path / "x.db").exists()


@pytest.mark.parametrize(
    ("version", "than", "older"),
    [
        ("3.28.0", "3.29.0", True),
        ("3.29.0", "3.29", False),
        ("3.29", "3.29.0", False),
        ("3.9", "3.10", True),
        ("3.30", "3.29.1", False),
        ("3.0rc1", "3.29", False),
        ("3.29", "v3", False),
    ],
)
def test_is_older(version: str, than: str, older: bool) -> None:
    assert is_older(version, than) is older


def test_the_sources_are_the_options_of_the_cli() -> None:
    assert releasesource.SOURCES == ("auto", "compact", "upstream", "packaged")

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The fallbacks of ``update --source auto`` (licenseid.releasesource): each is
one warning naming the next source; when the snapshot shipped in the wheel
may be used; caches before downloads. No test touches the network."""
# pylint: disable=missing-function-docstring

import gzip
import os
import time
from pathlib import Path

import pytest
from release_fakes import (
    BUNDLE,
    DOWN,
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
    warnings_of,
    without,
)

from licenseid.errors import LicenseIdError

# --- auto: each fallback is one warning naming the next source ---


def test_a_missing_bundle_falls_back_to_the_tarball(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, without(online(), bundle_url()))
    assert db.update_from_remote()
    assert urls(fake) == [LATEST, bundle_url(), tarball_url(), POPULARITY]
    err = capsys.readouterr().err
    assert warnings_of(err) == [
        (
            f"WARNING: {BUNDLE}: download failed: HTTPError: 404 Client Error: "
            f"Not Found for url: {bundle_url()}; downloading {TARBALL}"
        )
    ]
    assert data_line(err).endswith(": tarball (remote)")


def test_a_failed_tarball_falls_back_to_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    routes = without(online(), bundle_url())
    routes[tarball_url()] = DOWN
    serve(monkeypatch, routes)
    ship(monkeypatch, release_bundle())
    assert db.update_from_remote()
    err = capsys.readouterr().err
    assert warnings_of(err)[1] == (
        f"WARNING: {TARBALL}: download failed: ConnectionError: down; "
        "using packaged data v9.99"
    )
    assert data_line(err).endswith(": packaged")
    assert db_version(db) == "9.99"


def test_offline_the_version_and_the_data_come_from_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    fake = serve(monkeypatch, {LATEST: DOWN, SPDX_ORG: DOWN, POPULARITY: DOWN})
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote()
    assert urls(fake) == [LATEST, SPDX_ORG]  # not tried again for the data
    assert warnings_of(capsys.readouterr().err) == [
        (
            "WARNING: latest.json: download failed: ConnectionError: down; "
            "downloading licenses.json"
        ),
        (
            "WARNING: licenses.json: download failed: ConnectionError: down; "
            "using packaged data v9.98"
        ),
        "WARNING: popularity.csv: missing",
    ]
    assert db_version(db) == "9.98"


def test_offline_without_a_snapshot_is_the_lookup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {LATEST: DOWN, SPDX_ORG: DOWN})
    with pytest.raises(LicenseIdError, match="^licenses.json: download failed: "):
        open_db(tmp_path).update_from_remote()


def test_no_cache_takes_the_snapshot_not_a_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, online())
    assert db.update_from_remote()
    for name in ("latest.json", BUNDLE):
        old = time.time() - 100 * 86400
        os.utime(tmp_path / name, (old, old))
    serve(monkeypatch, {})
    ship(monkeypatch, release_bundle("10.0"))
    assert db.update_from_remote(use_cache=False)
    assert db_version(db) == "10.0"


# --- --version ---


def test_an_explicit_version_falls_back_to_a_snapshot_of_that_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, online())  # serves 9.99 only
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote(version="9.98")
    assert db_version(db) == "9.98"


def test_a_snapshot_of_another_version_is_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, online())
    ship(monkeypatch, release_bundle("9.98"))
    with pytest.raises(LicenseIdError, match=r"^spdx-data-v9\.97\.tar\.gz: download"):
        db.update_from_remote(version="9.97")
    assert len(warnings_of(capsys.readouterr().err)) == 1  # the bundle's, only


# --- the snapshot never downgrades, and is not stored twice ---


def test_a_snapshot_older_than_the_database_is_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, online())
    assert db.update_from_remote()
    routes = without(online("10.0"), bundle_url("10.0"), tarball_url("10.0"))
    serve(monkeypatch, routes)
    ship(monkeypatch, release_bundle("9.98"))
    with pytest.raises(LicenseIdError, match=r"^spdx-data-v10\.0\.tar\.gz: "):
        db.update_from_remote(use_cache=False)
    assert db_version(db) == "9.99"


def test_a_database_at_the_snapshot_version_is_not_rebuilt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    serve(monkeypatch, {})
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote()
    capsys.readouterr()
    assert not db.update_from_remote()
    assert "Database is already at version 9.98. Skipping" in capsys.readouterr().err
    assert db.update_from_remote(force=True)


def test_a_data_fallback_to_the_database_version_is_not_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The lookup names 9.99, every download fails, and the snapshot holds the
    9.98 the database already has."""
    db = open_db(tmp_path)
    serve(monkeypatch, {})
    ship(monkeypatch, release_bundle("9.98"))
    assert db.update_from_remote()
    fake = serve(monkeypatch, without(online(), bundle_url(), tarball_url()))
    capsys.readouterr()
    assert not db.update_from_remote(use_cache=False)
    assert POPULARITY not in urls(fake)  # a skip fetches no popularity data
    err = capsys.readouterr().err
    assert "using packaged data v9.98" in err
    assert "Database is already at version 9.98. Skipping" in err
    assert "Data sources" not in err


# --- caches ---


def test_a_cached_tarball_comes_before_a_bundle_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / TARBALL).write_bytes(release_tarball())
    fake = serve(monkeypatch, online())
    assert open_db(tmp_path).update_from_remote()
    assert bundle_url() not in urls(fake)


def test_an_unusable_cached_tarball_is_downloaded_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / TARBALL).write_bytes(b"garbage")
    serve(monkeypatch, online())
    db = open_db(tmp_path)
    assert db.update_from_remote(source="tarball")
    err = capsys.readouterr().err
    assert warnings_of(err) == [
        f"WARNING: {TARBALL}: cache unusable: ReadError: not a gzip file; downloading"
    ]
    assert data_line(err).endswith(": tarball (remote)")
    assert (tmp_path / TARBALL).read_bytes() == release_tarball()


def test_an_unusable_downloaded_tarball_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes = online()
    routes[tarball_url()] = gzip.compress(b"not a tar")
    serve(monkeypatch, routes)
    with pytest.raises(LicenseIdError, match=f"^{TARBALL}: download unusable: "):
        open_db(tmp_path).update_from_remote(source="tarball")
    assert not (tmp_path / TARBALL).exists()


@pytest.mark.parametrize("cached", [False, True], ids=["download", "cache"])
def test_a_tarball_of_another_version_is_removed_and_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached: bool
) -> None:
    routes = online()
    routes[tarball_url()] = release_tarball("1.0")
    serve(monkeypatch, routes)
    if cached:
        (tmp_path / TARBALL).write_bytes(release_tarball("1.0"))
    with pytest.raises(
        LicenseIdError,
        match=f"^{TARBALL}: download unusable: .*version 1.0 is not the expected",
    ):
        open_db(tmp_path).update_from_remote(source="tarball")
    assert not (tmp_path / TARBALL).exists()


def test_a_cached_tarball_that_cannot_be_removed_is_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows: another process holds it; a download could not replace it."""
    (tmp_path / TARBALL).write_bytes(b"garbage")
    fake = serve(monkeypatch, online())
    real_unlink = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path.name == TARBALL:
            raise PermissionError(13, "in use")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(LicenseIdError, match=f"^{TARBALL}: cache unusable: "):
        open_db(tmp_path).update_from_remote(source="tarball")
    assert tarball_url() not in urls(fake)


def test_a_held_tarball_in_auto_warns_with_the_next_source_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ACTION "remove it and run ..." is for the error alone: a fallback's
    warning has one ACTION, the next source."""
    (tmp_path / TARBALL).write_bytes(b"garbage")
    serve(monkeypatch, online())
    real_unlink = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path.name == TARBALL:
            raise PermissionError(13, "in use")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    assert open_db(tmp_path).update_from_remote()
    assert warnings_of(capsys.readouterr().err) == [
        (
            f"WARNING: {TARBALL}: cache unusable: ReadError: not a gzip file; "
            f"downloading {BUNDLE}"
        )
    ]


def test_after_a_failed_bundle_a_cached_tarball_is_named_as_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / BUNDLE).write_bytes(b"garbage")
    (tmp_path / TARBALL).write_bytes(release_tarball())
    serve(monkeypatch, without(online(), bundle_url()))
    assert open_db(tmp_path).update_from_remote()
    warnings = warnings_of(capsys.readouterr().err)
    assert warnings[0].startswith(f"WARNING: {BUNDLE}: cache unusable: ")
    assert warnings[1].endswith(f"; using cached {TARBALL}")


def test_an_unreadable_snapshot_is_reported_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, without(online(), bundle_url(), tarball_url()))
    ship(monkeypatch, b"garbage")
    with pytest.raises(LicenseIdError, match=f"^{TARBALL}: download failed: "):
        open_db(tmp_path).update_from_remote()
    warnings = warnings_of(capsys.readouterr().err)
    assert [w for w in warnings if "spdx-bundle.json.gz" in w] == [
        "WARNING: spdx-bundle.json.gz: invalid: BadGzipFile: Not a gzipped file (b'ga')"
    ]

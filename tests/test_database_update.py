# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for LicenseDatabase.update_from_remote() and tarball
extraction: a small synthetic SPDX release and a faked requests.get."""
# pylint: disable=missing-function-docstring,protected-access

import io
import json
import tarfile
from pathlib import Path
from unittest import mock

import pytest
import requests
from click.testing import CliRunner

from licenseid import spdx_source
from licenseid.cli import cli
from licenseid.database import LicenseDatabase

# The manual-extraction tests simulate a Python without extraction filters, so
# tarfile (3.12-3.13) warns that extracting without a filter is deprecated.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Python 3.14 will, by default, filter extracted tar archives"
    ":DeprecationWarning"
)

_LICENSES = {
    "licenseListVersion": "9.99",
    "releaseDate": "2030-01-01",
    "licenses": [
        {
            "licenseId": "MIT",
            "name": "MIT License",
            "isOsiApproved": True,
            "isFsfLibre": True,
            "isDeprecatedLicenseId": False,
        }
    ],
}
_MIT_TEXT = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software and associated documentation files."
)


def _tarball(members: dict[str, bytes], links: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buf.getvalue()


def _release_tarball() -> bytes:
    root = "license-list-data-9.99"
    return _tarball(
        {
            f"{root}/json/licenses.json": json.dumps(_LICENSES).encode(),
            f"{root}/json/exceptions.json": json.dumps({"exceptions": []}).encode(),
            f"{root}/text/MIT.txt": _MIT_TEXT.encode(),
        }
    )


def _serve(monkeypatch: pytest.MonkeyPatch, tarball: bytes) -> mock.MagicMock:
    """Fake the three remote sources by URL."""

    def fake_get(url: str, **_: object) -> mock.MagicMock:
        response = mock.create_autospec(requests.Response, instance=True)
        if url == spdx_source.LICENSES_JSON_URL:
            response.json.return_value = {
                "licenseListVersion": "9.99",
                "releaseDate": "2030-01-01",
            }
        elif url == spdx_source.POPULARITY_DATA_URL:
            response.text = "spdx_license,num_pushers\nMIT,1000\n"
        else:
            response.iter_content.return_value = [tarball]
        return response  # type: ignore[no-any-return]

    fake: mock.MagicMock = mock.create_autospec(requests.get, side_effect=fake_get)
    monkeypatch.setattr(requests, "get", fake)
    return fake


def test_update_from_remote_end_to_end_then_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    fake = _serve(monkeypatch, _release_tarball())

    assert db.update_from_remote()
    assert fake.call_count == 3  # licenses.json, popularity, tarball
    assert db.get_metadata()["license_list_version"] == "9.99"
    details = db.get_license_details("MIT")
    assert details is not None
    assert details["pop_score"] == 1000  # from the popularity data
    out = capsys.readouterr().out
    assert "GitHub license ranking data  : remote" in out

    cache_files = {p.name for p in tmp_path.iterdir()}
    assert {"licenses.json", "popularity.csv", "spdx-data-v9.99.tar.gz"} <= cache_files
    assert not [name for name in cache_files if name.endswith(".tmp")]

    # Second run: everything cached and the version matches, so no requests.
    fake.reset_mock()
    assert not db.update_from_remote()
    fake.assert_not_called()


def test_forced_update_reuses_all_caches_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    fake = _serve(monkeypatch, _release_tarball())
    db.update_from_remote()
    fake.reset_mock()
    capsys.readouterr()

    assert db.update_from_remote(force=True)
    fake.assert_not_called()
    out = capsys.readouterr().out
    assert "GitHub license ranking data  : cache" in out
    assert "SPDX License List data       : cache" in out


def _attack_tarball(kind: str, outside: Path) -> bytes:
    """A tarball containing exactly one kind of unsafe member; *outside* is a
    directory that must stay untouched."""
    if kind == "parent_dir":
        return _tarball({"../evil.txt": b"pwned"})
    if kind == "absolute_path":
        return _tarball({str(outside / "evil.txt"): b"pwned"})
    if kind == "symlink_absolute":
        return _tarball({}, {"root/link": "/etc"})
    if kind == "symlink_parent":
        return _tarball({}, {"root/link": "../../outside"})
    raise ValueError(kind)


@pytest.mark.parametrize("has_filter", [True, False], ids=["data_filter", "manual"])
@pytest.mark.parametrize(
    "kind", ["parent_dir", "absolute_path", "symlink_absolute", "symlink_parent"]
)
def test_extract_tarball_refuses_each_unsafe_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    has_filter: bool,
) -> None:
    """CWE-22: path traversal and links leaving the destination must be
    refused, and absolute names made relative (each on its own, so one check
    cannot mask another), identically with the tarfile 'data' filter and
    with the manual fallback."""
    if not has_filter:
        monkeypatch.setattr(spdx_source, "_HAS_EXTRACTION_FILTER", False)
    tar_path = tmp_path / "evil.tar.gz"
    outside = tmp_path / "outside"
    outside.mkdir()
    tar_path.write_bytes(_attack_tarball(kind, outside))
    dest = tmp_path / "out"
    dest.mkdir()
    if kind == "absolute_path":
        # Absolute names are made relative instead of failing, identically
        # with and without the filter; nothing may land outside dest.
        spdx_source.extract_tarball(tar_path, dest)
        relative = (outside / "evil.txt").relative_to(outside.anchor)
        assert (dest / relative).exists()
    else:
        with pytest.raises(tarfile.TarError):
            spdx_source.extract_tarball(tar_path, dest)
    assert not (tmp_path / "evil.txt").exists()
    assert not list(outside.iterdir())


@pytest.mark.parametrize("has_filter", [True, False], ids=["data_filter", "manual"])
@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_extract_tarball_keeps_links_inside_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_type: bytes,
    has_filter: bool,
) -> None:
    """Both extraction paths accept a link that stays inside the destination
    (consistent behaviour across Python versions)."""
    if not has_filter:
        monkeypatch.setattr(spdx_source, "_HAS_EXTRACTION_FILTER", False)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"content"
        info = tarfile.TarInfo("root/target.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("root/link.txt")
        link.type = link_type
        link.linkname = (
            "target.txt" if link_type == tarfile.SYMTYPE else "root/target.txt"
        )
        tar.addfile(link)
    tar_path = tmp_path / "ok.tar.gz"
    tar_path.write_bytes(buf.getvalue())
    dest = tmp_path / "out"
    dest.mkdir()
    spdx_source.extract_tarball(tar_path, dest)
    assert (dest / "root" / "link.txt").read_bytes() == b"content"


def test_extract_tarball_manual_check_refuses_hardlink_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(spdx_source, "_HAS_EXTRACTION_FILTER", False)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("root/hard")
        info.type = tarfile.LNKTYPE
        info.linkname = "../../outside"
        tar.addfile(info)
    tar_path = tmp_path / "evil.tar.gz"
    tar_path.write_bytes(buf.getvalue())
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(tarfile.TarError, match="unsafe link"):
        spdx_source.extract_tarball(tar_path, dest)


def test_extract_tarball_fallback_extracts_safe_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(spdx_source, "_HAS_EXTRACTION_FILTER", False)
    tar_path = tmp_path / "ok.tar.gz"
    tar_path.write_bytes(_tarball({"root/json/licenses.json": b"{}"}))
    dest = tmp_path / "out"
    dest.mkdir()
    spdx_source.extract_tarball(tar_path, dest)
    assert (dest / "root" / "json" / "licenses.json").read_bytes() == b"{}"


def test_unsafe_cached_tarball_is_removed_and_reported(tmp_path: Path) -> None:
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    tar_path = tmp_path / "spdx-data-v9.99.tar.gz"
    tar_path.write_bytes(_tarball({"../evil.txt": b"pwned"}))
    with pytest.raises(RuntimeError, match="cached tarball was removed"):
        db._process_and_store(tar_path, {}, None)
    assert not tar_path.exists()


def test_cli_update_reports_success_then_no_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "licenses.db")
    _serve(monkeypatch, _release_tarball())
    runner = CliRunner()

    first = runner.invoke(cli, ["--db", db_path, "update"])
    assert first.exit_code == 0, first.output
    assert f"Database updated at {db_path}" in first.output

    second = runner.invoke(cli, ["--db", db_path, "update"])
    assert second.exit_code == 0, second.output
    assert "Database remains at version 9.99" in second.output


def test_cli_update_failure_is_a_short_error_and_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake: mock.MagicMock = mock.create_autospec(
        requests.get, side_effect=requests.ConnectionError("network down")
    )
    monkeypatch.setattr(requests, "get", fake)
    result = CliRunner().invoke(cli, ["--db", str(tmp_path / "x.db"), "update"])
    assert result.exit_code == 1
    assert "ERROR: Failed to fetch latest license list info" in result.output
    assert "network down" in result.output
    assert "Traceback" not in result.output
    assert fake.call_count == 1  # one attempt, no retry loop


def test_cli_update_rejects_unsafe_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _serve(monkeypatch, _release_tarball())
    result = CliRunner().invoke(
        cli, ["--db", str(tmp_path / "x.db"), "update", "--version", "../../evil"]
    )
    assert result.exit_code == 1
    assert "ERROR: Invalid SPDX License List version" in result.output
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
    monkeypatch.setattr(
        spdx_source, "get_tarball_path", lambda *_: (tmp_path / "x.tgz", "remote")
    )
    monkeypatch.setattr(db, "_process_and_store", mock.Mock())
    assert db.update_from_remote(force=True, use_cache=use_cache)
    assert fetch.call_args.kwargs["allow_stale"] is use_cache

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The bundle build tool: output files, ``latest.json`` rule, download."""
# pylint: disable=missing-function-docstring,protected-access

import hashlib
import io
import json
import os
import runpy
import tarfile
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from licenseid.spdxdata import SpdxData
from tools import build_bundle
from tools.build_bundle import BuildError, build, main, version_key


def make_tarball(path: Path, version: str = "3.99") -> Path:
    root = f"license-list-data-{version}"
    doc = {
        "licenseListVersion": version,
        "releaseDate": "2099-01-01T00:00:00Z",
        "licenses": [{"licenseId": "MIT", "name": "MIT"}],
    }
    members = {
        "json/licenses.json": json.dumps(doc).encode(),
        "json/exceptions.json": json.dumps({"exceptions": []}).encode(),
        "text/MIT.txt": b"mit text\n",
    }
    with tarfile.open(path, "w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return path


def tarball_of(tmp_path: Path, version: str) -> Path:
    return make_tarball(tmp_path / f"t{version}.tar.gz", version)


def args_for(tmp_path: Path, version: str = "3.99") -> list[str]:
    return [
        "--out",
        str(tmp_path / "o"),
        "--tarball",
        str(tarball_of(tmp_path, version)),
    ]


def latest_of(out: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((out / "latest.json").read_text("utf-8"))
    return result


def test_build_writes_bundle_and_latest(tmp_path: Path) -> None:
    out = tmp_path / "out"
    written = build(tarball_of(tmp_path, "3.99"), out)
    assert written == [out / "v3.99.json.gz", out / "latest.json"]
    raw = (out / "v3.99.json.gz").read_bytes()
    assert SpdxData.from_bundle(raw, "3.99").texts == {"MIT": "mit text\n"}
    assert latest_of(out) == {
        "file": "v3.99.json.gz",
        "licenseListVersion": "3.99",
        "releaseDate": "2099-01-01T00:00:00Z",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }
    text = (out / "latest.json").read_text("utf-8")
    assert text.endswith("}\n")
    assert '\n  "file"' in text


def test_a_rebuild_is_byte_identical_and_writes_nothing(tmp_path: Path) -> None:
    tar = tarball_of(tmp_path, "3.99")
    build(tar, tmp_path / "a")
    build(tar, tmp_path / "b")
    for name in ("v3.99.json.gz", "latest.json"):
        first = (tmp_path / "a" / name).read_bytes()
        assert first == (tmp_path / "b" / name).read_bytes()
    assert not build(tar, tmp_path / "a")
    assert not list((tmp_path / "a").glob("*.tmp"))


def test_a_changed_bundle_is_replaced(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "v3.99.json.gz").write_bytes(b"stale")
    assert build(tarball_of(tmp_path, "3.99"), out)[0] == out / "v3.99.json.gz"
    assert (out / "v3.99.json.gz").read_bytes() != b"stale"


def test_an_older_version_does_not_regress_latest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    build(tarball_of(tmp_path, "3.29.0"), out)
    before = (out / "latest.json").read_bytes()
    written = build(tarball_of(tmp_path, "3.9"), out)
    assert written == [out / "v3.9.json.gz"]
    assert (out / "latest.json").read_bytes() == before
    assert "keeping v3.29.0" in capsys.readouterr().err


def test_a_newer_version_moves_latest_forward(tmp_path: Path) -> None:
    out = tmp_path / "out"
    build(tarball_of(tmp_path, "3.9"), out)
    build(tarball_of(tmp_path, "3.29.0"), out)
    assert latest_of(out)["licenseListVersion"] == "3.29.0"


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("{not json", id="badjson"),
        pytest.param("[]", id="list"),
        pytest.param('{"licenseListVersion": 3}', id="notstr"),
    ],
)
def test_an_unusable_latest_is_replaced(tmp_path: Path, content: str) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "latest.json").write_text(content, "utf-8")
    build(tarball_of(tmp_path, "3.99"), out)
    assert latest_of(out)["licenseListVersion"] == "3.99"


@pytest.mark.parametrize(
    ("low", "high"), [("3.9", "3.29.0"), ("3.29", "3.29.1"), ("2.99", "10")]
)
def test_versions_compare_numerically(low: str, high: str) -> None:
    assert version_key(low) < version_key(high)


def test_a_non_numeric_version_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="not numeric"):
        version_key("3.29-rc1")
    assert main(args_for(tmp_path, "3.1b")) == 1
    assert not (tmp_path / "o").exists()


def test_main_prints_one_wrote_line_per_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = args_for(tmp_path)
    out = tmp_path / "o"
    assert main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [f"WROTE {out / 'v3.99.json.gz'}", f"WROTE {out / 'latest.json'}"]
    assert main(argv) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param([], id="neither"),
        pytest.param(["--tarball", "a", "--version", "3.1"], id="both"),
        pytest.param(["--version", "../x"], id="badversion"),
        pytest.param(["--version", ""], id="emptyversion"),
        pytest.param(["--bogus"], id="unknown"),
    ],
)
def test_a_usage_error_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a URL was opened")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert main(["--out", str(tmp_path), *extra]) == 2


def test_help_exits_0() -> None:
    assert main(["--help"]) == 0


def test_a_missing_out_exits_2(tmp_path: Path) -> None:
    assert main(["--tarball", str(tarball_of(tmp_path, "3.99"))]) == 2


def test_a_corrupt_tarball_is_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a tarball")
    assert main(["--out", str(tmp_path / "o"), "--tarball", str(bad)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("ERROR: build failed: ")
    assert len(err.splitlines()) == 1


def test_a_missing_tarball_exits_1(tmp_path: Path) -> None:
    argv = ["--out", str(tmp_path), "--tarball", str(tmp_path / "none.tar.gz")]
    assert main(argv) == 1


class FakeResponse:
    """Just enough of a urlopen result."""

    def __init__(self, content: bytes) -> None:
        self._stream = io.BytesIO(content)

    def __enter__(self) -> "FakeResponse":  # noqa: PYI034
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self._stream.read(size)


def fake_urlopen(
    monkeypatch: pytest.MonkeyPatch, content: bytes
) -> list[tuple[str, float]]:
    calls: list[tuple[str, float]] = []

    def urlopen(url: str, timeout: float) -> FakeResponse:
        calls.append((url, timeout))
        return FakeResponse(content)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def test_version_downloads_then_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_urlopen(monkeypatch, tarball_of(tmp_path, "3.99").read_bytes())
    out = tmp_path / "out"
    assert main(["--out", str(out), "--version", "3.99"]) == 0
    url = "https://github.com/spdx/license-list-data/archive/refs/tags/v3.99.tar.gz"
    assert calls == [(url, build_bundle.TIMEOUT)]
    assert (out / "v3.99.json.gz").is_file()


def test_a_download_over_the_cap_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(build_bundle, "MAX_DOWNLOAD", 10)
    monkeypatch.setattr(build_bundle, "CHUNK", 4)
    fake_urlopen(monkeypatch, b"x" * 11)
    assert main(["--out", str(tmp_path / "o"), "--version", "3.99"]) == 1
    assert "larger than 10 bytes" in capsys.readouterr().err


def test_a_download_at_the_cap_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_bundle, "MAX_DOWNLOAD", 10)
    fake_urlopen(monkeypatch, b"x" * 10)
    target = tmp_path / "t"
    build_bundle.download("3.99", target)
    assert target.read_bytes() == b"x" * 10


def test_a_network_error_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def urlopen(url: str, timeout: float) -> FakeResponse:
        raise OSError(f"offline {url} {timeout}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert main(["--out", str(tmp_path / "o"), "--version", "3.99"]) == 1
    assert "ERROR: build failed: OSError: offline" in capsys.readouterr().err


def test_download_refuses_an_invalid_version(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="invalid"):
        build_bundle.download("../x", tmp_path / "t")


def test_run_needs_a_source(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="missing"):
        build_bundle.run(None, None, tmp_path)


def test_a_failed_verification_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real = SpdxData.from_bundle

    def other(raw: bytes, expected: str | None) -> SpdxData:
        back = real(raw, expected)
        return SpdxData(back.version, back.release_date, (), (), {})

    monkeypatch.setattr(SpdxData, "from_bundle", staticmethod(other))
    assert main(args_for(tmp_path)) == 1
    assert "verification failed: data differs" in capsys.readouterr().err
    assert not list(tmp_path.rglob("*.json*"))  # nothing is published


def test_an_unreadable_bundle_fails_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(build_bundle, "to_bundle", lambda _data: b"not gzip")
    assert main(args_for(tmp_path)) == 1
    assert "v3.99.json.gz: verification failed" in capsys.readouterr().err
    assert not list(tmp_path.rglob("*.json*"))


def test_write_atomic_cleans_up_when_the_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_src: str, _dst: Path) -> None:
        raise OSError("no")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="no"):
        build_bundle.write_atomic(tmp_path / "f", b"x")
    assert not list(tmp_path.iterdir())


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_running_the_module_exits_with_the_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["build_bundle", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("tools.build_bundle", run_name="__main__")
    assert excinfo.value.code == 0

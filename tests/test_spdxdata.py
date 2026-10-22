# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The SPDX data model: bundle round trip and validation, tarball reading."""
# pylint: disable=missing-function-docstring,protected-access

import gzip
import importlib.resources
import io
import json
import tarfile
from pathlib import Path
from typing import Any

import pytest

from licenseid import spdxdata
from licenseid.spdxdata import BundleError, SpdxData, packaged_bundle, to_bundle

MIT_TEXT = "Permission is hereby granted\nfree of charge\n"


def sample() -> SpdxData:
    return SpdxData(
        version="3.99",
        release_date="2099-01-01T00:00:00Z",
        licenses=(
            {"licenseId": "MIT", "name": "MIT License", "isOsiApproved": True},
            {"licenseId": "Old-1.0", "isDeprecatedLicenseId": True},
        ),
        exceptions=({"licenseExceptionId": "Ex-1.0", "name": "Ex é"},),
        texts={"MIT": MIT_TEXT},
    )


def bundle_of(doc: object) -> bytes:
    return gzip.compress(json.dumps(doc).encode("utf-8"), mtime=0)


def good_doc() -> dict[str, Any]:
    return {
        "format": 1,
        "licenseListVersion": "3.99",
        "releaseDate": "2099-01-01T00:00:00Z",
        "licenses": [{"licenseId": "MIT", "text": "t"}],
        "exceptions": [],
    }


def test_round_trip() -> None:
    data = sample()
    assert SpdxData.from_bundle(to_bundle(data), "3.99") == data


def test_a_text_less_license_is_absent_from_texts() -> None:
    back = SpdxData.from_bundle(to_bundle(sample()), None)
    assert "Old-1.0" not in back.texts
    assert [lic["licenseId"] for lic in back.licenses] == ["MIT", "Old-1.0"]


def test_the_same_data_gives_the_same_bytes() -> None:
    assert to_bundle(sample()) == to_bundle(sample())
    assert to_bundle(sample())[4:8] == b"\x00\x00\x00\x00"  # gzip mtime 0


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"not gzip at all", id="corrupt"),
        pytest.param(to_bundle(sample())[:-12], id="truncated"),
        pytest.param(gzip.compress(b"{not json"), id="badjson"),
        pytest.param(gzip.compress(b"[]"), id="notobject"),
        pytest.param(b"", id="empty"),
        pytest.param(gzip.compress(b"[" * 100_000), id="deep"),
    ],
)
def test_an_unusable_bundle_raises_one_line_detail(raw: bytes) -> None:
    with pytest.raises(BundleError) as excinfo:
        SpdxData.from_bundle(raw, None)
    detail = str(excinfo.value)
    assert detail
    assert ";" not in detail
    assert "\n" not in detail


def test_a_flipped_crc_is_caught() -> None:
    raw = bytearray(to_bundle(sample()))
    raw[-8] ^= 0xFF  # the CRC32 in the trailer
    with pytest.raises(BundleError, match="CRC"):
        SpdxData.from_bundle(bytes(raw), None)


def test_an_oversize_bundle_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = to_bundle(sample())
    monkeypatch.setattr(spdxdata, "MAX_UNZIPPED", 50)
    with pytest.raises(BundleError, match="larger than 50"):
        SpdxData.from_bundle(raw, None)


@pytest.mark.parametrize("fmt", [2, 0, "1", None, True])
def test_a_wrong_format_is_refused(fmt: object) -> None:
    doc = good_doc()
    doc["format"] = fmt
    with pytest.raises(BundleError, match="format"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_the_expected_version_must_match() -> None:
    raw = bundle_of(good_doc())
    assert SpdxData.from_bundle(raw, "3.99").version == "3.99"
    with pytest.raises(BundleError, match="expected 3.98"):
        SpdxData.from_bundle(raw, "3.98")


@pytest.mark.parametrize("version", ["../x", "", "a/b", 3, None, "-1"])
def test_a_bad_version_is_refused(version: object) -> None:
    doc = good_doc()
    doc["licenseListVersion"] = version
    with pytest.raises(BundleError, match="licenseListVersion"):
        SpdxData.from_bundle(bundle_of(doc), None)


@pytest.mark.parametrize("ident", ["", "-x", "a b", "a/b", "x" * 101, 5, None])
def test_a_bad_id_is_refused(ident: object) -> None:
    doc = good_doc()
    doc["licenses"] = [{"licenseId": ident}]
    with pytest.raises(BundleError, match="invalid licenseId"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_a_bad_exception_id_is_refused() -> None:
    doc = good_doc()
    doc["exceptions"] = [{"licenseExceptionId": "a/b"}]
    with pytest.raises(BundleError, match="invalid licenseExceptionId"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_a_duplicate_id_is_refused() -> None:
    doc = good_doc()
    doc["licenses"] = [{"licenseId": "MIT"}, {"licenseId": "MIT"}]
    with pytest.raises(BundleError, match="duplicate"):
        SpdxData.from_bundle(bundle_of(doc), None)


@pytest.mark.parametrize("key", ["licenses", "exceptions"])
@pytest.mark.parametrize("value", [{}, "x", None, 3])
def test_a_non_list_is_refused(key: str, value: object) -> None:
    doc = good_doc()
    doc[key] = value
    with pytest.raises(BundleError, match="not a list"):
        SpdxData.from_bundle(bundle_of(doc), None)


@pytest.mark.parametrize("entry", ["MIT", 3, None, ["MIT"]])
def test_an_entry_that_is_not_an_object_is_refused(entry: object) -> None:
    doc = good_doc()
    doc["licenses"] = [entry]
    with pytest.raises(BundleError, match="not an object"):
        SpdxData.from_bundle(bundle_of(doc), None)


@pytest.mark.parametrize("text", [3, ["x"], {}])
def test_a_text_that_is_not_a_string_is_refused(text: object) -> None:
    doc = good_doc()
    doc["licenses"] = [{"licenseId": "MIT", "text": text}]
    with pytest.raises(BundleError, match="text"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_a_null_text_is_no_text() -> None:
    doc = good_doc()
    doc["licenses"] = [{"licenseId": "MIT", "text": None}]
    assert SpdxData.from_bundle(bundle_of(doc), None).texts == {}


def make_tarball(
    path: Path,
    members: dict[str, bytes],
    root: str = "license-list-data-3.99",
) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(
                name if name.startswith(("/", "..")) else f"{root}/{name}"
            )
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return path


def licenses_json(*ids: str) -> bytes:
    doc = {
        "licenseListVersion": "3.99",
        "releaseDate": "2099-01-01T00:00:00Z",
        "licenses": [{"licenseId": i, "name": i} for i in ids],
    }
    return json.dumps(doc).encode("utf-8")


def test_a_tarball_with_exceptions(tmp_path: Path) -> None:
    exceptions = {"exceptions": [{"licenseExceptionId": "Ex-1.0"}]}
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {
            "json/licenses.json": licenses_json("MIT", "NoText"),
            "json/exceptions.json": json.dumps(exceptions).encode(),
            "text/MIT.txt": b"mit text\n",
        },
    )
    data = SpdxData.from_tarball(tar)
    assert data.version == "3.99"
    assert data.release_date == "2099-01-01T00:00:00Z"
    assert [lic["licenseId"] for lic in data.licenses] == ["MIT", "NoText"]
    assert data.exceptions == ({"licenseExceptionId": "Ex-1.0"},)
    assert data.texts == {"MIT": "mit text\n"}


def test_a_tarball_of_another_version_is_refused(tmp_path: Path) -> None:
    tar = make_tarball(
        tmp_path / "t.tar.gz", {"json/licenses.json": licenses_json("MIT")}
    )
    assert SpdxData.from_tarball(tar, "3.99").version == "3.99"
    assert SpdxData.from_tarball(tar, None).version == "3.99"
    with pytest.raises(tarfile.ReadError, match="version 3.99 is not the expected 1.0"):
        SpdxData.from_tarball(tar, "1.0")


def test_a_tarball_without_exceptions_json(tmp_path: Path) -> None:
    tar = make_tarball(
        tmp_path / "t.tar.gz", {"json/licenses.json": licenses_json("MIT")}
    )
    data = SpdxData.from_tarball(tar)
    assert not data.exceptions
    assert data.texts == {}


def test_a_tarball_without_licenses_json_is_refused(tmp_path: Path) -> None:
    tar = make_tarball(tmp_path / "t.tar.gz", {"text/MIT.txt": b"x"})
    with pytest.raises(tarfile.TarError):
        SpdxData.from_tarball(tar)


@pytest.mark.parametrize("version", [None, 3.99], ids=["missing", "number"])
def test_a_tarball_without_a_string_version_is_refused(
    tmp_path: Path, version: object
) -> None:
    doc = {"licenses": [{"licenseId": "MIT"}], "licenseListVersion": version}
    if version is None:
        del doc["licenseListVersion"]
    tar = make_tarball(
        tmp_path / "t.tar.gz", {"json/licenses.json": json.dumps(doc).encode()}
    )
    with pytest.raises(
        tarfile.ReadError, match="licenseListVersion is missing or invalid"
    ):
        SpdxData.from_tarball(tar)


@pytest.mark.parametrize(
    ("file", "key", "entries"),
    [
        pytest.param("licenses", "licenseId", [{"name": "No ID"}], id="noid"),
        pytest.param("licenses", "licenseId", [{"licenseId": "a b"}], id="badid"),
        pytest.param("licenses", "licenseId", [{"licenseId": 7}], id="intid"),
        pytest.param(
            "licenses", "licenseId", [{"licenseId": "A"}, {"licenseId": "A"}], id="dup"
        ),
        pytest.param("exceptions", "licenseExceptionId", [{"name": "x"}], id="noexc"),
    ],
)
def test_a_tarball_entry_without_a_valid_unique_id_is_refused(
    tmp_path: Path, file: str, key: str, entries: list[dict[str, object]]
) -> None:
    doc = json.loads(licenses_json("MIT"))
    members = {"json/licenses.json": json.dumps(doc).encode()}
    if file == "licenses":
        doc["licenses"] = entries
        members["json/licenses.json"] = json.dumps(doc).encode()
    else:
        members["json/exceptions.json"] = json.dumps({"exceptions": entries}).encode()
    tar = make_tarball(tmp_path / "t.tar.gz", members)
    with pytest.raises(tarfile.ReadError, match=key):
        SpdxData.from_tarball(tar)


def test_a_tarball_release_date_that_is_not_a_string_is_refused(
    tmp_path: Path,
) -> None:
    doc = json.loads(licenses_json("MIT"))
    doc["releaseDate"] = 20990101
    tar = make_tarball(
        tmp_path / "t.tar.gz", {"json/licenses.json": json.dumps(doc).encode()}
    )
    with pytest.raises(tarfile.ReadError, match="releaseDate"):
        SpdxData.from_tarball(tar)


def test_unsafe_member_names_are_never_read(tmp_path: Path) -> None:
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {
            "json/licenses.json": licenses_json("MIT"),
            "/etc/text/MIT.txt": b"absolute",
            "../text/MIT.txt": b"parent",
        },
    )
    assert SpdxData.from_tarball(tar).texts == {}


def test_a_corrupt_tarball_propagates(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a tarball")
    with pytest.raises(tarfile.TarError):
        SpdxData.from_tarball(bad)


@pytest.mark.parametrize(
    "raw",
    [b"a\r\nb\r\n", b"a\rb\r", b"\xef\xbb\xbfa\r\nb", b"x\n\r\ny\r\r\n"],
    ids=["crlf", "cr", "bom", "mixed"],
)
def test_tarball_text_equals_text_mode_open(tmp_path: Path, raw: bytes) -> None:
    """Trap 4: a tarball DB and an extracted one must hold identical text."""
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {"json/licenses.json": licenses_json("MIT"), "text/MIT.txt": raw},
    )
    plain = tmp_path / "MIT.txt"
    plain.write_bytes(raw)
    with open(plain, "r", encoding="utf-8") as handle:
        expected = handle.read()
    assert SpdxData.from_tarball(tar).texts["MIT"] == expected


def test_packaged_bundle_is_none_when_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(importlib.resources, "files", lambda _name: tmp_path)
    assert packaged_bundle() is None


def test_packaged_bundle_reads_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / spdxdata.PACKAGED_NAME).write_bytes(b"snapshot")
    monkeypatch.setattr(importlib.resources, "files", lambda _name: tmp_path)
    assert packaged_bundle() == b"snapshot"


def test_a_release_date_that_is_not_a_string_is_refused() -> None:
    doc = good_doc()
    doc["releaseDate"] = 20990101
    with pytest.raises(BundleError, match="releaseDate"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_an_exceptions_json_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {"json/licenses.json": licenses_json("MIT"), "json/exceptions.json": b"[]"},
    )
    with pytest.raises(tarfile.ReadError, match="not a JSON object"):
        SpdxData.from_tarball(tar)


def test_a_tarball_is_read_forward_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The text members come in the reverse of the order licenses.json lists
    # them, and before it: a lookup by name would jump back in the stream.
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {
            "text/B-1.txt": b"b",
            "text/A-1.txt": b"a",
            "json/licenses.json": licenses_json("A-1", "B-1"),
        },
    )
    offsets: list[int] = []
    real = tarfile.TarFile.extractfile

    def spy(self: tarfile.TarFile, member: str | tarfile.TarInfo) -> Any:
        assert isinstance(member, tarfile.TarInfo)
        offsets.append(member.offset_data)
        return real(self, member)

    monkeypatch.setattr(tarfile.TarFile, "extractfile", spy)
    data = SpdxData.from_tarball(tar)
    assert dict(data.texts) == {"A-1": "a", "B-1": "b"}
    assert offsets == sorted(offsets)


def test_texts_of_another_root_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "t.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, content in {
            "a-root/json/licenses.json": licenses_json("A-1"),
            "a-root/text/A-1.txt": b"mine",
            "z-root/json/licenses.json": licenses_json("A-1"),
            "z-root/text/A-1.txt": b"theirs",
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    assert dict(SpdxData.from_tarball(path).texts) == {"A-1": "mine"}

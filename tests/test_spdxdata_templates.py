# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Templates in the bundle: the licence templates reach ``SpdxData`` from every
source, and a bundle where no licence has a ``template`` key (one built before
templates) is refused, never read as a release without them. No test touches
the network."""
# pylint: disable=missing-function-docstring

import gzip
import io
import json
import tarfile
from pathlib import Path
from typing import Any

import pytest
from release_fakes import (
    BUNDLE,
    MIT_TEMPLATE,
    MIT_TEXT,
    TARBALL,
    bundle_url,
    data_line,
    listing,
    online,
    open_db,
    release_bundle,
    release_data,
    release_tarball,
    serve,
    ship,
    tarball,
    tarball_url,
    urls,
    warnings_of,
)

from licenseid import listindex, spdx_source
from licenseid.errors import LicenseIdError
from licenseid.spdxdata import BundleError, SpdxData, to_bundle
from licenseid.types import SpdxLicenseEntry

pytestmark = pytest.mark.usefixtures("printed")

TEMPLATE = (
    "<<beginOptional>>MIT License<<endOptional>>\n<<var;name=x;original=c;match=.+>>"
)


def document(raw: bytes) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(gzip.decompress(raw))
    return doc


def bundle_of(doc: object) -> bytes:
    return gzip.compress(json.dumps(doc).encode("utf-8"), mtime=0)


def good_doc() -> dict[str, Any]:
    return {
        "format": 1,
        "licenseListVersion": "3.99",
        "licenses": [{"licenseId": "MIT", "name": "MIT", "text": "t", "template": "t"}],
        "exceptions": [],
    }


def licenses_json(*ids: str) -> bytes:
    doc = {
        "licenseListVersion": "3.99",
        "licenses": [{"licenseId": i, "name": i} for i in ids],
    }
    return json.dumps(doc).encode("utf-8")


def make_tarball(path: Path, members: dict[str, bytes]) -> Path:
    """A tarball of *members* under one root; ``../`` names stay as written."""
    with tarfile.open(path, "w:gz") as tar:
        for name, content in members.items():
            full = name if name.startswith("..") else f"license-list-data-3.99/{name}"
            info = tarfile.TarInfo(full)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return path


def pre_templates(raw: bytes) -> bytes:
    """*raw* as 0.9.1 wrote it: format 1, no ``template`` key."""
    doc = document(raw)
    for lic in doc["licenses"]:
        del lic["template"]
    return bundle_of(doc)


# --- the bundle ---


def test_templates_survive_a_round_trip() -> None:
    data = release_data()
    back = SpdxData.from_bundle(to_bundle(data), None)
    assert back.templates == {"MIT": MIT_TEMPLATE}
    assert back == data


def test_every_licence_entry_has_a_template_key_and_the_format_is_1() -> None:
    licences: tuple[SpdxLicenseEntry, ...] = (
        {"licenseId": "MIT", "name": "MIT"},
        {"licenseId": "Old-1.0", "name": "Old", "isDeprecatedLicenseId": True},
    )
    data = SpdxData("3.99", None, licences, (), {"MIT": "t"}, {"MIT": TEMPLATE})
    doc = document(to_bundle(data))
    assert doc["format"] == 1
    assert [lic["template"] for lic in doc["licenses"]] == [TEMPLATE, None]


def test_a_bundle_with_no_template_key_is_refused() -> None:
    with pytest.raises(BundleError, match="^no templates$"):
        SpdxData.from_bundle(pre_templates(release_bundle()), None)


def test_a_bundle_of_null_templates_is_read() -> None:
    """A null is a licence with no template, not a bundle without templates."""
    doc = good_doc()
    doc["licenses"][0]["template"] = None
    data = SpdxData.from_bundle(bundle_of(doc), None)
    assert (data.templates, data.texts) == ({}, {"MIT": "t"})
    assert "template" not in data.licenses[0]


def test_one_template_key_is_enough_for_the_others_to_have_none() -> None:
    doc = good_doc()
    doc["licenses"].append({"licenseId": "ISC", "name": "ISC", "text": "i"})
    data = SpdxData.from_bundle(bundle_of(doc), None)
    assert data.templates == {"MIT": "t"}
    assert data.texts == {"MIT": "t", "ISC": "i"}


def test_a_bundle_of_no_licences_is_not_a_bundle_without_templates() -> None:
    doc = good_doc()
    doc["licenses"] = []
    assert not SpdxData.from_bundle(bundle_of(doc), None).licenses


@pytest.mark.parametrize("template", [3, ["x"], {}, True])
def test_a_template_that_is_not_a_string_is_refused(template: object) -> None:
    doc = good_doc()
    doc["licenses"][0]["template"] = template
    with pytest.raises(BundleError, match="^licenses has a template that is not"):
        SpdxData.from_bundle(bundle_of(doc), None)


def test_an_exception_needs_no_template_and_keeps_none() -> None:
    doc = good_doc()
    doc["exceptions"] = [
        {"licenseExceptionId": "A-exception", "name": "A"},
        {"licenseExceptionId": "B-exception", "name": "B", "template": "x"},
    ]
    data = SpdxData.from_bundle(bundle_of(doc), None)
    assert data.templates == {"MIT": "t"}
    assert all("template" not in exc for exc in data.exceptions)


# --- the tarball ---


def test_a_tarball_gives_the_templates_of_its_licences(tmp_path: Path) -> None:
    exceptions = {"exceptions": [{"licenseExceptionId": "Ex-1.0", "name": "Ex"}]}
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {
            "json/licenses.json": licenses_json("MIT", "NoTemplate"),
            "json/exceptions.json": json.dumps(exceptions).encode(),
            "text/MIT.txt": b"mit text\n",
            "text/NoTemplate.txt": b"text\n",
            "template/MIT.template.txt": TEMPLATE.encode(),
            "template/Ex-1.0.template.txt": b"exception template",
            "template/NoTemplate.txt": b"no suffix: not a template",
            "text/MIT.template.txt": b"a text folder holds no template",
        },
    )
    data = SpdxData.from_tarball(tar)
    assert data.templates == {"MIT": TEMPLATE}
    assert data.texts == {"MIT": "mit text\n", "NoTemplate": "text\n"}
    assert SpdxData.from_bundle(to_bundle(data), "3.99") == data


def test_a_template_under_another_root_is_not_read(tmp_path: Path) -> None:
    tar = make_tarball(
        tmp_path / "t.tar.gz",
        {
            "json/licenses.json": licenses_json("MIT"),
            "../template/MIT.template.txt": b"parent",
        },
    )
    assert not SpdxData.from_tarball(tar).templates


def test_tarball_and_compact_bundle_give_the_same_data(tmp_path: Path) -> None:
    path = tmp_path / TARBALL
    path.write_bytes(release_tarball())
    assert SpdxData.from_tarball(path, "9.99") == release_data()
    assert SpdxData.from_bundle(release_bundle(), "9.99") == release_data()


# --- the sources of update ---


def test_a_pre_templates_download_is_unusable_and_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {bundle_url(): pre_templates(release_bundle())})
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert str(info.value) == f"{BUNDLE}: download unusable: no templates"
    assert not list(tmp_path.iterdir())


def test_a_pre_templates_cache_is_removed_and_downloaded_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cache file of 0.9.1 has the same name: it is not read."""
    cached = tmp_path / BUNDLE
    cached.write_bytes(pre_templates(release_bundle()))
    fake = serve(monkeypatch, {bundle_url(): release_bundle()})
    data, origin = spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert (data.templates, origin) == ({"MIT": MIT_TEMPLATE}, "remote")
    assert urls(fake) == [bundle_url()]
    assert cached.read_bytes() == release_bundle()
    assert warnings_of(capsys.readouterr().err) == [
        f"WARNING: {BUNDLE}: cache unusable: no templates; downloading"
    ]


def test_auto_falls_back_to_upstream_from_a_pre_templates_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    routes = online()
    routes[bundle_url()] = pre_templates(release_bundle())
    fake = serve(monkeypatch, routes)
    assert db.update_from_remote()
    err = capsys.readouterr().err
    assert warnings_of(err) == [
        f"WARNING: {BUNDLE}: download unusable: no templates; downloading " + TARBALL
    ]
    assert data_line(err).endswith(": upstream (remote)")
    assert urls(fake)[1:3] == [bundle_url(), tarball_url()]


def test_compact_alone_fails_on_a_pre_templates_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    routes = online()
    routes[bundle_url()] = pre_templates(release_bundle())
    serve(monkeypatch, routes)
    with pytest.raises(LicenseIdError, match="download unusable: no templates"):
        db.update_from_remote(source="compact")


def test_a_pre_templates_snapshot_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    ship(monkeypatch, pre_templates(release_bundle()))
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote(source="packaged")
    assert str(info.value) == "spdx-bundle.json.gz: invalid: no templates"


def test_the_packaged_list_reads_a_bundle_with_no_templates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``resolve()`` reads no templates: only a database build needs them."""
    ship(monkeypatch, pre_templates(release_bundle()))
    index = listindex.packaged_index()
    assert index is not None
    assert listindex.packaged_problem() == ""


def test_a_bundle_with_no_templates_is_read_when_they_are_not_required() -> None:
    raw = pre_templates(release_bundle())
    data = SpdxData.from_bundle(raw, None, require_templates=False)
    assert not data.templates
    assert data.texts == release_data().texts


def _no_template_tarball() -> bytes:
    """The upstream tarball of the release without its ``template/`` folder."""
    root = "license-list-data-9.99"
    return tarball(
        {
            f"{root}/json/licenses.json": json.dumps(listing("9.99")).encode(),
            f"{root}/json/exceptions.json": json.dumps({"exceptions": []}).encode(),
            f"{root}/text/MIT.txt": MIT_TEXT.encode(),
        }
    )


def test_an_upstream_tarball_with_no_templates_is_unusable_and_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = open_db(tmp_path)
    routes = online()
    routes[tarball_url()] = _no_template_tarball()
    serve(monkeypatch, routes)
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote(source="upstream")
    assert str(info.value) == f"{TARBALL}: download unusable: no templates"
    assert not list(tmp_path.rglob(TARBALL))


def test_a_cached_upstream_tarball_with_no_templates_is_downloaded_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = open_db(tmp_path)
    cache = tmp_path
    (cache / TARBALL).write_bytes(_no_template_tarball())
    serve(monkeypatch, online())
    assert db.update_from_remote(source="upstream")
    assert f"WARNING: {TARBALL}: cache unusable: no templates; downloading" in (
        warnings_of(capsys.readouterr().err)
    )


def test_auto_ends_on_the_packaged_data_when_no_download_has_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Compact has none (built before 0.9.2), the upstream tarball has no
    ``template/`` folder: each is unusable, and ``auto`` goes on to the
    packaged data, which holds them."""
    db = open_db(tmp_path)
    ship(monkeypatch, release_bundle())
    routes = online()
    routes[bundle_url()] = pre_templates(release_bundle())
    routes[tarball_url()] = _no_template_tarball()
    serve(monkeypatch, routes)
    assert db.update_from_remote()
    err = capsys.readouterr().err
    assert warnings_of(err) == [
        f"WARNING: {BUNDLE}: download unusable: no templates; downloading " + TARBALL,
        f"WARNING: {TARBALL}: download unusable: no templates; "
        + "using packaged data v9.99",
    ]
    assert data_line(err).endswith(": packaged")
    assert not list(tmp_path.rglob(TARBALL))


def test_auto_fails_when_no_source_has_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no packaged data to go on to, the last failure is the error."""
    db = open_db(tmp_path)
    routes = online()
    routes[bundle_url()] = pre_templates(release_bundle())
    routes[tarball_url()] = _no_template_tarball()
    serve(monkeypatch, routes)
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote()
    assert str(info.value) == f"{TARBALL}: download unusable: no templates"
    assert warnings_of(capsys.readouterr().err) == [
        f"WARNING: {BUNDLE}: download unusable: no templates; downloading " + TARBALL
    ]

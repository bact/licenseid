# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A small synthetic SPDX release in every shape ``update`` reads (version
files, tarball, bundle), and a fake ``requests.get`` that serves them by
URL and answers anything else with a 404."""

import io
import json
import tarfile
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import cast
from unittest import mock

import pytest
import requests

from licenseid import releasesource, spdx_source, spdxdata
from licenseid.database import LicenseDatabase
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.types import SpdxLicenseEntry

VERSION = "9.99"
RELEASE_DATE = "2030-01-01"
MIT_TEXT = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software and associated documentation files."
)
POPULARITY_CSV = "spdx_license,num_pushers\nMIT,1000\n"
# The real ones: conftest's autouse fixture replaces them before each test.
_PACKAGED_BUNDLE = spdxdata.packaged_bundle
_GET = requests.get

# What a route serves: JSON (a dict), text (a str), a streamed body (bytes),
# or an exception that requests.get raises.
Route = dict[str, object] | str | bytes | Exception


def listing(version: str = VERSION) -> dict[str, object]:
    """licenses.json of a one-license release."""
    return {
        "licenseListVersion": version,
        "releaseDate": RELEASE_DATE,
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


def version_json(version: str = VERSION) -> dict[str, object]:
    """A version file (latest.json, licenses.json) naming *version*."""
    return {"licenseListVersion": version, "releaseDate": RELEASE_DATE}


def tarball(
    members: Mapping[str, bytes], links: Mapping[str, str] | None = None
) -> bytes:
    """A gzipped tar of *members* (name: bytes) and symbolic *links*."""
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


def release_tarball(version: str = VERSION) -> bytes:
    """The one-license release as SPDX publishes it."""
    root = f"license-list-data-{version}"
    return tarball(
        {
            f"{root}/json/licenses.json": json.dumps(listing(version)).encode(),
            f"{root}/json/exceptions.json": json.dumps({"exceptions": []}).encode(),
            f"{root}/text/MIT.txt": MIT_TEXT.encode(),
        }
    )


def release_data(version: str = VERSION) -> SpdxData:
    """The one-license release as data."""
    licenses = cast(list[SpdxLicenseEntry], listing(version)["licenses"])
    return SpdxData(
        version=version,
        release_date=RELEASE_DATE,
        licenses=tuple(licenses),
        exceptions=(),
        texts=MappingProxyType({"MIT": MIT_TEXT}),
    )


def release_bundle(version: str = VERSION) -> bytes:
    """The one-license release as our bundle."""
    return to_bundle(release_data(version))


def bundle_url(version: str = VERSION) -> str:
    """Where our bundle of *version* is published."""
    return spdx_source.BUNDLE_URL_TEMPLATE.format(version=version)


def tarball_url(version: str = VERSION) -> str:
    """Where SPDX publishes the tarball of *version*."""
    return spdx_source.TARBALL_URL_TEMPLATE.format(version=version)


def online(version: str = VERSION) -> dict[str, Route]:
    """Every source of *version* up: both version files, the bundle, the
    tarball and the popularity data."""
    return {
        spdx_source.LATEST_JSON_URL: version_json(version),
        spdx_source.LICENSES_JSON_URL: version_json(version),
        bundle_url(version): release_bundle(version),
        tarball_url(version): release_tarball(version),
        spdx_source.POPULARITY_DATA_URL: POPULARITY_CSV,
    }


def serve(
    monkeypatch: pytest.MonkeyPatch, routes: Mapping[str, Route]
) -> mock.MagicMock:
    """Replace requests.get with an autospec'd fake serving *routes* by URL;
    any other URL is a 404, as a missing file on raw.githubusercontent.com."""

    def fake_get(url: str, **_: object) -> mock.MagicMock:
        response = mock.create_autospec(requests.Response, instance=True)
        route = routes.get(url)
        if isinstance(route, Exception):
            raise route
        if isinstance(route, dict):
            response.json.return_value = route
        elif isinstance(route, str):
            response.text = route
        elif isinstance(route, bytes):
            response.iter_content.return_value = [route]
        else:
            response.raise_for_status.side_effect = requests.HTTPError(
                f"404 Client Error: Not Found for url: {url}"
            )
        return response  # type: ignore[no-any-return]

    fake: mock.MagicMock = mock.create_autospec(_GET, side_effect=fake_get)
    monkeypatch.setattr(requests, "get", fake)
    return fake


def urls(fake: mock.MagicMock) -> list[str]:
    """The URLs *fake* was asked for, in order."""
    return [call.args[0] for call in fake.call_args_list]


def ship(monkeypatch: pytest.MonkeyPatch, raw: bytes | None) -> None:
    """Make *raw* the snapshot shipped in the wheel (None: none)."""
    monkeypatch.setattr(
        spdxdata,
        "packaged_bundle",
        mock.create_autospec(_PACKAGED_BUNDLE, return_value=raw),
    )


def stub_chain(monkeypatch: pytest.MonkeyPatch, db: LicenseDatabase) -> None:
    """Make *db*'s update load the one-license release from no source and
    store nothing, for a test of what update passes on its way."""
    monkeypatch.setattr(
        releasesource.ReleaseChain,
        "load",
        mock.create_autospec(
            releasesource.ReleaseChain.load, return_value=(release_data(), "x")
        ),
    )
    monkeypatch.setattr(db, "_store", mock.Mock())


# --- shared by the update tests (test_update_sources, test_update_fallbacks) ---

LATEST = spdx_source.LATEST_JSON_URL
SPDX_ORG = spdx_source.LICENSES_JSON_URL
POPULARITY = spdx_source.POPULARITY_DATA_URL
BUNDLE = "spdx-bundle-v9.99.json.gz"
TARBALL = "spdx-data-v9.99.tar.gz"
DOWN = requests.ConnectionError("down")


def open_db(tmp_path: Path) -> LicenseDatabase:
    """The database ``licenses.db`` in *tmp_path*, its cache beside it."""
    return LicenseDatabase(str(tmp_path / "licenses.db"))


def db_version(db: LicenseDatabase) -> str | None:
    """The license list version *db* holds."""
    return db.get_metadata().get("license_list_version")


def warnings_of(err: str) -> list[str]:
    """The WARNING lines of *err*."""
    return [line for line in err.splitlines() if line.startswith("WARNING")]


def without(routes: dict[str, Route], *gone: str) -> dict[str, Route]:
    """*routes* with the URLs *gone* answered by a 404."""
    return {url: route for url, route in routes.items() if url not in gone}


def data_line(err: str) -> str:
    """The ``SPDX License List data`` line of the Data sources report."""
    return next(line for line in err.splitlines() if "License List data" in line)

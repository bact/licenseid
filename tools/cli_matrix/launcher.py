# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Run the real licenseid CLI with ``requests.get`` replaced by a fake.

``update`` is the one subcommand that would otherwise reach the network, so
every ``update`` cell goes through this launcher instead. The fake serves a
tiny but well-formed SPDX release, and ``FAKE_NET`` chooses how it fails:

==============  =========================================================
``ok``          everything served (the default)
``down``        ``requests.ConnectionError`` for every URL
``http503``     ``raise_for_status`` raises for every URL
``garbage_json``  the licences URL returns HTML
``bad_version``   the licences URL reports version ``../x``
``pop_down``      the popularity CSV fails, the rest is served
``pop_garbage``   the popularity CSV is HTML
``tar_down``      the tarball URL fails, the rest is served
``tar_corrupt``   the tarball bytes are not gzip
``tar_truncated`` the tarball is cut in half
``slow``          every request sleeps 30 s, for the signal cells
==============  =========================================================

``FAKE_VER`` sets the served ``licenseListVersion`` (default ``9.99``).

This module is run as a *script*, by an interpreter that need not have the
repository on its path, so it imports nothing from its own package.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import time
from collections.abc import Iterator
from typing import Any

import requests

from licenseid import cli

VER = os.environ.get("FAKE_VER", "9.99")
MODE = os.environ.get("FAKE_NET", "ok")

MIT = (
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy of this software and associated documentation files."
)
APACHE = b"Apache License Version 2.0 January 2004 http://www.apache.org/licenses/"
LICENSES: dict[str, Any] = {
    "licenseListVersion": VER,
    "releaseDate": "2030-01-01",
    "licenses": [
        {
            "licenseId": "MIT",
            "name": "MIT License",
            "isOsiApproved": True,
            "isFsfLibre": True,
            "isDeprecatedLicenseId": False,
        },
        {
            "licenseId": "Apache-2.0",
            "name": "Apache License 2.0",
            "isOsiApproved": True,
            "isFsfLibre": True,
            "isDeprecatedLicenseId": False,
        },
    ],
}


def tarball() -> bytes:
    """A gzipped SPDX ``license-list-data`` release, built in memory."""
    root = f"license-list-data-{VER}"
    members = {
        f"{root}/json/licenses.json": json.dumps(LICENSES).encode(),
        f"{root}/json/exceptions.json": json.dumps({"exceptions": []}).encode(),
        f"{root}/text/MIT.txt": MIT.encode(),
        f"{root}/text/Apache-2.0.txt": APACHE,
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Resp:
    """The part of ``requests.Response`` that licenseid actually uses."""

    def __init__(self, text: str = "", data: bytes = b"", fail: str = "") -> None:
        self.text = text
        self._data = data
        self._fail = fail

    def raise_for_status(self) -> None:
        """Raise when this response was scripted to be an HTTP error."""
        if self._fail:
            raise requests.HTTPError(self._fail)

    def json(self) -> Any:
        """Decode the body as JSON, failing the way requests would."""
        return json.loads(self.text)

    def iter_content(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Yield the body in *chunk_size* pieces, as a streamed download."""
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start : start + chunk_size]


def fake_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    stream: bool = False,
) -> Resp:
    """Serve *url* from the scripted release, or fail as ``FAKE_NET`` says."""
    del headers, timeout, stream
    if MODE == "slow":
        time.sleep(30)
    if MODE == "down":
        raise requests.ConnectionError("fake: connection refused")
    if MODE == "http503":
        return Resp(fail="503 Service Unavailable")
    if url.endswith("licenses.json") and "spdx.org" in url:
        if MODE == "garbage_json":
            return Resp(text="<html>oops</html>")
        if MODE == "bad_version":
            return Resp(text=json.dumps({**LICENSES, "licenseListVersion": "../x"}))
        return Resp(text=json.dumps(LICENSES))
    if url.endswith(".tar.gz"):
        if MODE == "tar_down":
            raise requests.ConnectionError("fake: tarball connection refused")
        data = tarball()
        if MODE == "tar_corrupt":
            data = b"this is not a gzip file" * 10
        if MODE == "tar_truncated":
            data = data[: len(data) // 2]
        return Resp(data=data)
    if url.endswith("licenses.csv"):
        if MODE == "pop_down":
            raise requests.ConnectionError("fake: popularity connection refused")
        if MODE == "pop_garbage":
            return Resp(text="<html>oops</html>")
        return Resp(text="spdx_license,num_pushers\nMIT,100\nApache-2.0,50\n")
    raise RuntimeError(f"unexpected URL {url}")


def main() -> None:
    """Install the fake and hand over to the real CLI."""
    # Deliberately duck-typed: Resp carries only what licenseid reads, so a
    # whole requests.Response would add nothing but ways to reach the net.
    requests.get = fake_get  # type: ignore[assignment]
    sys.argv[0] = "licenseid"
    cli.main()


if __name__ == "__main__":
    main()

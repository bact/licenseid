# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Licence URLs: which values are one, and which SPDX licences the List
gives that URL to in ``seeAlso`` (a licence has several: its steward's
page, the OSI's, SPDX's own), so the sample shows what a URL reader built
on the List would read and what it would miss. The key rules are the
package's (``licenseid.urlkey``); the tool keeps SPDX's per-ID pages in its
table, so its counts stay those of the reader."""

import json
from collections.abc import Iterable
from pathlib import Path

from licenseid.resolveurl import list_url_key
from licenseid.spdxdata import SpdxData
from licenseid.urlkey import is_url, url_key

__all__ = ["host_of", "is_url", "see_also", "url_key"]


def host_of(url: str) -> str:
    """The host of *url*, as :func:`url_key` writes it ("" for no URL)."""
    return (url_key(url) or "").split("/", 1)[0]


def see_also(path: Path) -> dict[str, set[str]]:
    """``{url_key: {licence IDs}}`` of the List in *path*: an SPDX
    ``license-list-data`` tarball or its ``licenses.json``. The List's own
    page of each ID (``spdx.org/licenses/<ID>``) is added too, as
    the reader derives it from the ID, so the report counts it as listed.
    A URL with a fragment is skipped (:func:`list_url_key`)."""
    if path.name.endswith(".json"):
        entries: Iterable[dict[str, object]] = json.loads(path.read_text("utf-8"))[
            "licenses"
        ]
    else:
        entries = SpdxData.from_tarball(path).licenses  # type: ignore[assignment]
    table: dict[str, set[str]] = {}
    for entry in entries:
        ident = str(entry["licenseId"])
        urls = entry.get("seeAlso") or []
        urls = (
            [*urls, f"https://spdx.org/licenses/{ident}"]
            if isinstance(urls, list)
            else []
        )
        for url in urls:
            if isinstance(url, str):
                key = list_url_key(url)
                if key is not None:
                    table.setdefault(key, set()).add(ident)
    return table

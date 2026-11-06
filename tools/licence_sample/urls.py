# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Licence URLs: which values are one, and which SPDX licences the List
gives that URL to in ``seeAlso`` (a licence has several: its steward's
page, the OSI's, SPDX's own), so the sample shows what a URL reader built
on the List would read and what it would miss."""

import json
import re
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from licenseid.spdxdata import SpdxData

_RE_URL: Final = re.compile(r"(?:https?://|www\.)\S+\Z", re.IGNORECASE)
#: Pages a server gives for a folder: ``/LICENSE-2.0/`` is
#: ``/LICENSE-2.0/index.html``.
_INDEX: Final = re.compile(r"/(?:index\.(?:html?|php))?\Z", re.IGNORECASE)


def is_url(value: str) -> bool:
    """Whether the whole of *value* is one URL (``www.`` with no scheme too)."""
    return bool(_RE_URL.fullmatch(value.strip().strip("<>")))


def url_key(url: str) -> str:
    """*url* without what does not name another page: the scheme, ``www.``,
    letter case, a fragment, a query, a trailing ``/`` or index page."""
    text = url.strip().strip("<>")
    if not re.match(r"https?://", text, re.IGNORECASE):
        text = "http://" + text
    parts = urllib.parse.urlsplit(text)
    host = parts.netloc.lower().removeprefix("www.").split(":")[0]
    return host + _INDEX.sub("", parts.path).lower()


def host_of(url: str) -> str:
    """The host of *url*, as :func:`url_key` writes it."""
    return url_key(url).split("/", 1)[0]


def see_also(path: Path) -> dict[str, set[str]]:
    """``{url_key: {licence IDs}}`` of the List in *path*: an SPDX
    ``license-list-data`` tarball or its ``licenses.json``. The List's own
    page of each ID (``spdx.org/licenses/<ID>``, ``.html``) is added too."""
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
        urls.append(f"https://spdx.org/licenses/{ident}.html")
        for url in urls:
            if isinstance(url, str):
                table.setdefault(url_key(url), set()).add(ident)
    return table

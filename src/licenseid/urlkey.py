# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""One key for each spelling of a licence URL.

A licence page is written many ways: ``https://www.apache.org/licenses/
LICENSE-2.0.txt`` and ``http://apache.org/licenses/LICENSE-2.0`` are one page.
:func:`url_key` writes each as ``apache.org/licenses/license-2.0``, the same
for a URL the SPDX License List gives in ``seeAlso`` and for a declared value,
so the two compare as strings. The key keeps a non-empty query: the List
tells some pages apart by it alone.

The steps, in this order (each works on the text the one before left):

1. Refuse a value over :data:`MAX_URL_CHARS`, one with a character that is
   not ASCII (a look-alike host, a lone surrogate) or not one RFC 3986
   allows, or a ``%`` that is not followed by two hexadecimal digits.
2. Fold ASCII case (``licenseid.listlookup.fold_case``).
3. ``spdx:<ID>`` is ``spdx.org/licenses/<ID>``.
4. Drop ``https://`` or ``http://``; without either, the value must start
   with a host and a ``/`` (:data:`SCHEMELESS_HOST`). Any other scheme,
   ``//host`` or a doubled scheme is refused.
5. Drop a ``#fragment``; keep a non-empty ``?query``. Nothing is
   percent-decoded: ``%2F`` stays as written.
6. Host: refuse user information (``@``) and an IP literal (``[``); drop a
   port (0 to 65535; another is refused) and one trailing ``.``; the host
   is at least two labels, the last of letters; drop one leading ``www.``.
7. Path: drop one trailing ``/``; refuse an empty, ``.`` or ``..``
   segment; drop a last ``index.html``, ``index.htm`` or ``index.php``;
   drop one ``.html``, ``.htm``, ``.txt`` or ``.php`` from the last segment.
8. Host rules, the same for a List URL and a declared one: the OSI's two
   page forms (``licenses/Apache-2.0`` and ``license/apache-2-0``), GNU's
   ``-standalone`` pages, Creative Commons' ``legalcode`` and ``deed.*``
   pages, and the List's own ``.json`` page.
9. Refuse a value whose key would key again to another key (``x.txt.html``,
   ``www.www.host``): a key is a fixed point.

Every step reads the text once, so the key costs linear time. Standard
library and ``licenseid.listlookup`` only.
"""

import re
from typing import Final

from licenseid.listlookup import fold_case

MAX_URL_CHARS: Final = 2048

# A host name before the first "/": a URL written without its scheme
# ("www.apache.org/licenses/LICENSE-2.0"), not a directory.
SCHEMELESS_HOST: Final = re.compile(r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?/")

# The unreserved, reserved and percent characters of RFC 3986, nothing else
# (so no character that is not ASCII): white space, quote marks and angle
# brackets end a URL in prose.
_URL_CHARS: Final = re.compile(r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
# A "%" that does not start a percent-encoded octet.
_BAD_PERCENT: Final = re.compile(r"%(?![0-9A-Fa-f]{2})")
# A host after its port and one trailing "." are dropped, as SCHEMELESS_HOST
# reads one: two labels or more, the last of letters (no IP address).
_HOST: Final = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")
_PORT: Final = re.compile(r"[0-9]{1,5}")
_MAX_PORT: Final = 65535  # RFC 6335 section 6: ports are 0 to 65535
_SCHEMES: Final = ("https://", "http://")
_SPDX_PREFIX: Final = "spdx:"
_SPDX_PAGE: Final = "spdx.org/licenses/"
_NOT_IN_SPDX_ID: Final = frozenset("/:?#")
_INDEX_PAGES: Final = frozenset({"index.html", "index.htm", "index.php"})
_PAGE_SUFFIXES: Final = (".html", ".htm", ".txt", ".php")
_OSI_FOLDERS: Final = frozenset({"license", "licenses"})


def url_key(text: str) -> str | None:
    """The key of *text* if the whole of it is one http(s) URL, a host and
    path with no scheme, or ``spdx:<ID>``; else None. A host with no path
    and no scheme (``www.apache.org``) is no URL: it could be a word."""
    if len(text) > MAX_URL_CHARS:
        return None
    return _key(text)


def is_url(text: str) -> bool:
    """Whether :func:`url_key` reads *text* as a URL."""
    return url_key(text) is not None


def _key(text: str) -> str | None:
    """:func:`url_key` with no length limit (tests time it on long text)."""
    key = _key_once(text)
    if key is None or _key_once(key) != key:
        return None
    return key


def _key_once(text: str) -> str | None:
    """Steps 1 to 8 of the module docstring."""
    if not _URL_CHARS.fullmatch(text) or _BAD_PERCENT.search(text):
        return None
    rest = _without_scheme(_spdx_page(fold_case(text)))
    if rest is None:
        return None
    rest, _, query = rest.partition("#")[0].partition("?")
    authority, _, path = rest.partition("/")
    host = _host(authority)
    segments = _segments(path)
    if host is None or segments is None:
        return None
    _apply_host_rule(host, segments)
    return f"{host}/{'/'.join(segments)}" + (f"?{query}" if query else "")


def _spdx_page(text: str) -> str:
    """``spdx:<ID>`` as the List's page of that ID; any other *text* as it
    is. An ID holds no ``/``, ``:``, ``?`` or ``#``."""
    ident = text.removeprefix(_SPDX_PREFIX)
    if ident == text or not ident or _NOT_IN_SPDX_ID & set(ident):
        return text
    return _SPDX_PAGE + ident


def _without_scheme(text: str) -> str | None:
    """*text* after ``https://`` or ``http://``; *text* itself when it starts
    with a host and a ``/``; else None (another scheme, ``//host``)."""
    for scheme in _SCHEMES:
        if text.startswith(scheme):
            return text[len(scheme) :]
    return text if SCHEMELESS_HOST.match(text) else None


def _host(authority: str) -> str | None:
    """The host of *authority* as a key writes it, or None for user
    information, an IP literal, a port that is no number from 0 to 65535 or
    a host that is not two labels or more. ``_HOST`` and ``_PORT`` take no
    ``@`` and no ``[``, so they refuse user information and an IP literal."""
    host, colon, port = authority.partition(":")
    if colon and not (_PORT.fullmatch(port) and int(port) <= _MAX_PORT):
        return None
    host = host.removesuffix(".")
    if not _HOST.fullmatch(host):
        return None
    if host.startswith("www.") and host.count(".") > 1:
        host = host[len("www.") :]
    return host


def _segments(path: str) -> list[str] | None:
    """The segments of *path* (the text after the host's ``/``) without an
    index page or a page suffix, or None for an empty, ``.`` or ``..``
    segment."""
    path = path.removesuffix("/")
    segments = path.split("/") if path else []
    if any(segment in ("", ".", "..") for segment in segments):
        return None
    if segments and segments[-1] in _INDEX_PAGES:
        segments.pop()
    if segments:
        segments[-1] = _without_suffix(segments[-1], _PAGE_SUFFIXES)
    return segments


def _without_suffix(segment: str, suffixes: tuple[str, ...]) -> str:
    """*segment* without the first of *suffixes* it ends in, unless nothing
    would be left."""
    for suffix in suffixes:
        if segment.endswith(suffix) and len(segment) > len(suffix):
            return segment[: -len(suffix)]
    return segment


def _apply_host_rule(host: str, segments: list[str]) -> None:
    """Write the page of *host* that has two spellings one way, in place."""
    if not segments:
        return
    last = segments[-1]
    if host == "opensource.org":
        # The OSI's old pages are "licenses/Apache-2.0", the new ones
        # "license/apache-2-0": a "." of the ID is a "-".
        if len(segments) == 2 and segments[0] in _OSI_FOLDERS:
            segments[:] = ["license", last.replace(".", "-")]
    elif host == "gnu.org":
        # "gpl-3.0-standalone.html" is "gpl-3.0.html" without the site menu.
        segments[-1] = _without_suffix(last, ("-standalone",))
    elif host == "creativecommons.org":
        # The deed and the legal code of a licence are pages of one folder.
        if last == "legalcode" or last.startswith(("legalcode.", "deed.")):
            segments.pop()
    elif host == "spdx.org":
        # The List's page of an ID in JSON: "spdx.org/licenses/MIT.json".
        segments[-1] = _without_suffix(last, (".json",))

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``urlkey.url_key`` writes each spelling of a licence URL as one key, and
refuses a value that is not one URL (issue #14)."""
# pylint: disable=missing-function-docstring

import time
from pathlib import Path

import pytest
from resolver_corpus import SEE_ALSO_LIST, list_rows

import licenseid
from licenseid import textinput, urlkey
from licenseid.urlkey import MAX_URL_CHARS, SCHEMELESS_HOST, is_url, url_key

_LONG = "https://x.org/" + "a" * (MAX_URL_CHARS - len("https://x.org/"))

#: Value, key.
KEYS = [
    ("https://www.apache.org/licenses/LICENSE-2.0", "apache.org/licenses/license-2.0"),
    ("http://apache.org/licenses/LICENSE-2.0.txt", "apache.org/licenses/license-2.0"),
    ("HTTPS://WWW.Apache.ORG/licenses/LICENSE-2.0/", "apache.org/licenses/license-2.0"),
    ("www.apache.org/licenses/LICENSE-2.0.html", "apache.org/licenses/license-2.0"),
    ("apache.org:8080/licenses/LICENSE-2.0", "apache.org/licenses/license-2.0"),
    ("https://apache.org.:443/licenses/LICENSE-2.0", "apache.org/licenses/license-2.0"),
    ("https://apache.org/licenses/LICENSE-2.0#txt", "apache.org/licenses/license-2.0"),
    ("https://apache.org/licenses/LICENSE-2.0?", "apache.org/licenses/license-2.0"),
    ("https://apache.org/licenses/LICENSE-2.0?#x", "apache.org/licenses/license-2.0"),
    ("https://x.org/a/index.html", "x.org/a"),
    ("https://x.org/a/index.htm/", "x.org/a"),
    ("https://x.org/a/index.php?p=1", "x.org/a?p=1"),
    ("https://x.org/a/b.htm", "x.org/a/b"),
    ("https://x.org/a/index.html/index.html", "x.org/a/index"),
    ("https://x.org/a/b.php", "x.org/a/b"),
    ("https://x.org/a/.html", "x.org/a/.html"),  # nothing left: no suffix
    ("https://x.org/a/b.pdf", "x.org/a/b.pdf"),
    ("https://unlicense.org/", "unlicense.org/"),
    ("https://unlicense.org", "unlicense.org/"),
    ("http://www.unlicense.org/index.html", "unlicense.org/"),
    ("https://www.org/a", "www.org/a"),  # a host of two labels keeps "www."
    ("https://w-3.ex-1.org/a", "w-3.ex-1.org/a"),
    ("https://x.org:65535/a", "x.org/a"),
    ("https://x.org:0/a", "x.org/a"),
    ("https://x.org:00080/a", "x.org/a"),
    # The query tells pages apart; nothing is percent-decoded.
    (
        "https://scripts.sil.org/cms/scripts/page.php?item_id=OFL_web",
        "scripts.sil.org/cms/scripts/page?item_id=ofl_web",
    ),
    ("https://x.org/a?b=c?d/e#f?g", "x.org/a?b=c?d/e"),
    ("https://x.org?q=1", "x.org/?q=1"),
    ("https://x.org/lzma%20SDK", "x.org/lzma%20sdk"),
    ("https://x.org/a%2Fb", "x.org/a%2fb"),
    # nugetpath decodes the path of licenses.nuget.org; the key does not
    (
        "https://licenses.nuget.org/(MIT)%20OR%20ISC",
        "licenses.nuget.org/(mit)%20or%20isc",
    ),
    ("https://x.org/a@b/(c)!$&'*+,;=~_", "x.org/a@b/(c)!$&'*+,;=~_"),
    # spdx:<ID> and the List's own pages.
    ("spdx:MIT", "spdx.org/licenses/mit"),
    ("SPDX:GPL-2.0+", "spdx.org/licenses/gpl-2.0+"),
    ("https://spdx.org/licenses/MIT.html", "spdx.org/licenses/mit"),
    ("https://spdx.org/licenses/MIT.json", "spdx.org/licenses/mit"),
    ("spdx.org/licenses/MIT", "spdx.org/licenses/mit"),
    ("https://x.org/MIT.json", "x.org/mit.json"),  # ".json" only on spdx.org
    # The OSI's old and new pages.
    ("https://opensource.org/licenses/Apache-2.0", "opensource.org/license/apache-2-0"),
    ("https://opensource.org/license/apache-2-0/", "opensource.org/license/apache-2-0"),
    (
        "http://www.opensource.org/licenses/mit-license.php",
        "opensource.org/license/mit-license",
    ),
    ("https://opensource.org/a/licenses/MIT", "opensource.org/a/licenses/mit"),
    ("https://opensource.org/licenses", "opensource.org/licenses"),
    ("https://x.org/licenses/Apache-2.0", "x.org/licenses/apache-2.0"),
    # GNU's standalone pages.
    (
        "https://www.gnu.org/licenses/gpl-3.0-standalone.html",
        "gnu.org/licenses/gpl-3.0",
    ),
    ("https://www.gnu.org/licenses/gpl-3.0.html", "gnu.org/licenses/gpl-3.0"),
    ("https://www.gnu.org/licenses/-standalone", "gnu.org/licenses/-standalone"),
    ("https://x.org/gpl-3.0-standalone", "x.org/gpl-3.0-standalone"),
    ("https://gnu.org/licenses/gpl-standalone.txt", "gnu.org/licenses/gpl"),
    # Creative Commons' deed and legal code.
    (
        "https://creativecommons.org/licenses/by/4.0/legalcode",
        "creativecommons.org/licenses/by/4.0",
    ),
    (
        "https://creativecommons.org/licenses/by/4.0/legalcode.en",
        "creativecommons.org/licenses/by/4.0",
    ),
    (
        "https://creativecommons.org/licenses/by/4.0/legalcode.txt",
        "creativecommons.org/licenses/by/4.0",
    ),
    (
        "https://creativecommons.org/licenses/by/4.0/deed.en",
        "creativecommons.org/licenses/by/4.0",
    ),
    (
        "https://creativecommons.org/licenses/by/4.0/",
        "creativecommons.org/licenses/by/4.0",
    ),
    (
        "https://creativecommons.org/licenses/by/4.0/deed",
        "creativecommons.org/licenses/by/4.0/deed",
    ),
    ("https://x.org/by/4.0/legalcode", "x.org/by/4.0/legalcode"),
    (_LONG, _LONG.removeprefix("https://")),
]

#: Values that are no URL, or one a key could be fooled by.
NOT_URLS = [
    "",
    "MIT",
    "MIT/Apache-2.0",
    "www.apache.org",  # a bare host could be a word
    "apache.org",
    "https://",
    "http:///x.org/a",
    "//x.org/a",
    "ftp://x.org/a",
    "file:///etc/passwd",
    "mailto:a@x.org",
    "javascript:alert(1)",
    "https:/x.org/a",
    "https://https://x.org/a",
    "http://http//x.org/a",
    "https://user@evil.com/x.org/a",
    "https://x.org@evil.com/a",
    "https://user:pass@x.org/a",
    "https://[::1]/a",
    "https://[::1]:80/a",
    "https://127.0.0.1/a",
    "https://localhost/a",
    "https://x.org:/a",
    "https://x.org:123456/a",
    "https://x.org:65536/a",  # above the last port (RFC 6335)
    "https://x.org:99999/a",
    "x.org:65536/a",
    "https://x.org:8o/a",
    "https://x..org/a",
    "https://.x.org/a",
    "https://x.org../a",
    "x.org./a",
    "https://x_y.org/a",
    "https://x.org/a//b",
    "https://x.org//a",
    "https://x.org/a//",
    "https://x.org/a/../b",
    "https://x.org/..",
    "https://x.org/./a",
    "https://x.org/a/.",
    "https://web.archive.org/web/1/http://x.org/a",
    "https://x.org/a%zz",
    "https://x.org/a%2",
    "https://x.org/a%",
    "https://\u0430pache.org/licenses/LICENSE-2.0",  # Cyrillic a
    "https://apache.org/licenses/LICENSE-2.0\u200b",
    "https://x.org/\u017f",  # long s
    "https://x.org/\udcff",
    "https://x.org/a b",
    "https://x.org/a\tb",
    " https://x.org/a",
    "https://x.org/a\n",
    '"https://x.org/a"',
    "<https://x.org/a>",
    "https://x.org/a\\b",
    "https://x.org/{a}",
    "https://x.org/a|b",
    "https://x.org/a^b",
    "https://x.org/`a`",
    "spdx:",
    "spdx:a/b",
    "spdx:a?b",
    "spdx:a#b",
    "spdx:a:b",
    "spdx:..",
    "spdx:.",
    "spdx:MIT.txt.html",
    "https://x.org/a.txt.html",  # a key would key again
    "https://www.www.x.org/a",
    "https://www.gnu.org/licenses/gpl-standalone-standalone",
    "https://spdx.org/licenses/MIT.html.json",
    "https://creativecommons.org/licenses/by/legalcode/legalcode",
    _LONG + "a",
]


def _short_id(value: str) -> str:
    """A test ID for *value*, short enough for ``conftest.MAX_TEST_ID``."""
    return value if len(value) < 80 else f"{value[:40]}...({len(value)})"


@pytest.mark.parametrize(("value", "key"), KEYS, ids=[_short_id(v) for v, _ in KEYS])
def test_a_spelling_of_a_page_gives_its_key(value: str, key: str) -> None:
    assert url_key(value) == key
    assert is_url(value) is True


@pytest.mark.parametrize("key", sorted({k for _, k in KEYS}), ids=_short_id)
def test_a_key_is_its_own_key(key: str) -> None:
    assert url_key(key) == key


@pytest.mark.parametrize("value", NOT_URLS, ids=_short_id)
def test_a_value_that_is_no_url_has_no_key(value: str) -> None:
    assert url_key(value) is None
    assert is_url(value) is False


@pytest.mark.parametrize(
    "value",
    [
        "https://user@evil.com/x.org/a",
        "https://x.org@evil.com/a",
        "https://[::1]/a",
        "https://x.org:/a",
        "https://x.org/a/../b",
        "https://x.org/a%zz",
    ],
)
def test_a_host_or_path_check_refuses_without_the_fixed_point(value: str) -> None:
    """Steps 1 to 8 refuse these on their own: the fixed-point step, which a
    key with no scheme passes through ``SCHEMELESS_HOST`` again, is a second
    guard, not the only one."""
    assert urlkey._key_once(value) is None  # pylint: disable=protected-access


def test_the_schemeless_host_is_one_shared_regex() -> None:
    """``textinput.looks_like_path`` and the key read a host with no scheme
    by one pattern, written in one module."""
    assert vars(textinput)["SCHEMELESS_HOST"] is SCHEMELESS_HOST
    assert not hasattr(textinput, "_RE_HOST")
    source = Path(str(licenseid.__path__[0]))
    holders = [
        path.name
        for path in sorted(source.glob("*.py"))
        if SCHEMELESS_HOST.pattern in path.read_text(encoding="utf-8")
    ]
    assert holders == ["urlkey.py"]


@pytest.mark.parametrize(
    ("value", "is_path"),
    [
        ("www.apache.org/licenses/LICENSE-2.0", False),
        ("x.org:8080/a", False),
        ("docs/LICENSE", True),
        ("x.org./a", True),
    ],
)
def test_a_path_is_told_from_a_host_as_before(value: str, is_path: bool) -> None:
    assert textinput.looks_like_path(value) is is_path


#: Keys of the List's URLs that do not key again with a scheme in front, each
#: with the reason. None: every key of 3.29.0 is a fixed point.
NOT_FIXED_POINTS: dict[str, str] = {}


def test_the_key_of_every_url_of_the_list_is_a_fixed_point() -> None:
    """A key is what ``resolveurl`` looks up and what the List's own URLs are
    indexed by, so it must key to itself, as ``http://`` + key and as the
    scheme-less key (a URL is written with and without its scheme)."""
    keys = {url_key(str(url)) for _, _, url in list_rows(SEE_ALSO_LIST, "urls")}
    keys.discard(None)
    assert len(keys) > 900
    moved = {
        key: (url_key("http://" + key), url_key(key))
        for key in sorted(str(k) for k in keys)
        if (url_key("http://" + key), url_key(key)) != (key, key)
    }
    assert set(moved) == set(NOT_FIXED_POINTS), moved


# --- time ---


def test_the_key_is_linear_on_a_small_input() -> None:
    _time_the_key(2_000)


@pytest.mark.benchmark
def test_the_key_is_linear_on_a_large_input() -> None:
    _time_the_key(200_000)


def _time_the_key(size: int) -> None:
    """The key on the shapes that can backtrack, called past its length
    limit (``url_key`` refuses a value over ``MAX_URL_CHARS`` first)."""
    payloads = [
        "x" + " " * size,
        "https://x.org/" + " " * size,
        "a." * size,
        "a." * size + "/",
        "aa." * size + "a/",
        "a-" * size + ".org/",
        "https://" + "a." * size + "1/",
        "www." * size + "x.org/",
        "https://x.org/" + "a/" * size,
        "https://x.org/" + "a" * size + "/",
        "https://x.org/a" + "?" * size,
        "https://x.org/a" + "%" * size,
        "https://x.org/a" + "%41" * size,
        "https://x.org/a" + ".html" * size,
        "https://www.gnu.org/a" + "-standalone" * size,
        "https://opensource.org/licenses/" + "." * size,
        "https://creativecommons.org/a/" + "deed." * size,
        "spdx:" + "a" * size,
        "spdx:" + "." * size,
        "https://x.org:" + "1" * size + "/",
    ]
    start = time.monotonic()
    for payload in payloads:
        urlkey._key(payload)  # pylint: disable=protected-access
        SCHEMELESS_HOST.match(payload)
    assert time.monotonic() - start < max(2.0, size / 20_000)

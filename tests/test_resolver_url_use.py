# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where ``resolveurl`` is used: a synthetic list (an alias never beats a key
of the List, a page of exceptions only is refused, a family needs a split
base), the helpers of the SPDX tag reader, ``detect()``, the CLI and time.
The tables of what a URL reads as are in ``test_resolver_url.py``."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import contextlib
import json
import time
from collections.abc import Callable, Generator

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from timing import slack

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.resolvefirst import unread_url
from licenseid.resolveleaf import Found
from licenseid.resolver import MAX_EXPRESSION_CHARS
from licenseid.resolveurl import (
    URL_ALIASES,
    UrlAlias,
    read_url,
    url_license_id,
)
from licenseid.result import json_line
from licenseid.urlkey import _key  # no length limit, to time

APACHE_URL = "https://www.apache.org/licenses/LICENSE-2.0"


def _exception(*ids: str) -> str:
    return f"url names an exception: {', '.join(ids)}"


def _several(*ids: str) -> str:
    return f"url names several licences: {', '.join(ids)}"


def _with(*ids: str) -> str:
    return f"url names a licence with an exception: {', '.join(ids)}"


# --- a synthetic list ---

_CLASSES = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
)
_FAMILY = (
    Lic("Foo-1.0", "Foo", is_deprecated=True),
    Lic("Foo-1.0-only", "Foo only"),
    Lic("Foo-1.0-or-later", "Foo or later"),
)
PAGE_URL = "https://example.org/page"


@contextlib.contextmanager
def _list(
    rows: tuple[Lic, ...],
    pages: tuple[tuple[str, bool], ...],
    exceptions: tuple[str, ...] = (),
) -> Generator[LicenseDatabase, None, None]:
    """A database of *rows* and *exceptions*, each of *pages* on PAGE_URL
    (``(owner ID, is_exception)``)."""
    urls = [(owner, exception, PAGE_URL) for owner, exception in pages]
    for path in seeded_db("url_synthetic", rows, exceptions, urls):
        yield LicenseDatabase(path, create=False)


def _answer(
    rows: tuple[Lic, ...],
    pages: tuple[tuple[str, bool], ...],
    exceptions: tuple[str, ...] = (),
) -> tuple[str | None, str | None, str | None]:
    """The expression, step detail (or None) and reason of PAGE_URL."""
    with _list(rows, pages, exceptions) as db:
        got = resolve(PAGE_URL, db)
    steps = got["steps"]
    return got["expression"], steps[0]["detail"] if steps else None, got["reason"]


@pytest.mark.parametrize(
    ("pages", "target", "expected"),
    [
        # the List gives the page to one licence: the alias is not read
        ((("MIT", False),), "Apache-2.0", ("MIT", "see also", None)),
        # ... to the licence and its variants: the alias picks the base
        (
            (("MIT", False), ("Apache-2.0", False)),
            "Apache-2.0",
            ("Apache-2.0", "alias", None),
        ),
        # ... to nothing: the alias is the only reading
        ((), "Apache-2.0", ("Apache-2.0", "alias", None)),
        # an alias to an ID the list lacks names nothing
        ((), "Nope-1.0", (None, None, f"not found: {PAGE_URL}")),
    ],
    ids=["unique-list-key", "list-names-target", "no-list-key", "target-lacks"],
)
def test_an_alias_never_beats_a_unique_key_of_another_licence(
    monkeypatch: pytest.MonkeyPatch,
    pages: tuple[tuple[str, bool], ...],
    target: str,
    expected: tuple[str | None, str | None, str | None],
) -> None:
    monkeypatch.setitem(URL_ALIASES, "example.org/page", UrlAlias(target, "source"))
    assert _answer(_CLASSES, pages) == expected


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        ((("X-1.0", True),), (None, None, _exception("X-1.0"))),
        (
            (("Y-1.0", True), ("X-1.0", True)),
            (None, None, _exception("X-1.0", "Y-1.0")),
        ),
        # a licence beside an exception is refused, in either order, unless
        # it is one of the List's old IDs of both (test_resolver_url_smoke)
        ((("MIT", False), ("X-1.0", True)), (None, None, _with("MIT", "X-1.0"))),
        ((("X-1.0", True), ("MIT", False)), (None, None, _with("MIT", "X-1.0"))),
    ],
    ids=["exception", "two-exceptions", "licence-first", "exception-first"],
)
def test_a_page_of_exceptions_only_is_refused(
    pages: tuple[tuple[str, bool], ...],
    expected: tuple[str | None, str | None, str | None],
) -> None:
    assert _answer(_CLASSES, pages, ("X-1.0", "Y-1.0")) == expected


def test_a_page_of_x_only_and_x_or_later_is_the_split_bare_id() -> None:
    pages = (("Foo-1.0-only", False), ("Foo-1.0-or-later", False))
    assert _answer(_FAMILY, pages) == ("Foo-1.0", "see also", None)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        # the bare ID is not on the list, not deprecated, or has a successor
        (_FAMILY[1:], _several("Foo-1.0-only", "Foo-1.0-or-later")),
        (
            (Lic("Foo-1.0", "Foo"), *_FAMILY[1:]),
            _several("Foo-1.0", "Foo-1.0-only", "Foo-1.0-or-later"),
        ),
        (
            (Lic("Foo-1.0", "Foo", is_deprecated=True, superseded_by="Foo-1.0-only"),)
            + _FAMILY[1:],
            _several("Foo-1.0", "Foo-1.0-only", "Foo-1.0-or-later"),
        ),
        # two licences of no one family
        (_CLASSES, _several("Apache-2.0", "MIT")),
    ],
    ids=["no-base", "base-in-use", "base-renamed", "unrelated"],
)
def test_several_licences_are_a_family_only_when_the_base_is_split(
    rows: tuple[Lic, ...], reason: str
) -> None:
    pages = tuple((row.license_id, False) for row in rows)
    assert _answer(rows, pages) == (None, None, reason)


def test_a_renamed_licence_and_its_successor_are_one() -> None:
    rows = (
        Lic("Old-1.0", "Old", is_deprecated=True, superseded_by="New-1.0"),
        Lic("New-1.0", "New"),
    )
    pages = (("Old-1.0", False), ("New-1.0", False))
    assert _answer(rows, pages) == ("New-1.0", "see also", None)


# --- the helpers of the markers ---


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        ("https://spdx.org/licenses/MIT", "MIT"),
        ("https://spdx.org/licenses/MIT.", "MIT"),  # one end mark
        ("https://spdx.org/licenses/GPL-2.0+.html", "GPL-2.0-or-later"),
        ("https://spdx.org/licenses/Classpath-exception-2.0", None),
        ("https://www.example.com/a/b", None),
        ("MIT", None),
        ("", None),
    ],
)
def test_the_expression_a_url_names(
    corpus_db: LicenseDatabase, text: str, expression: str | None
) -> None:
    with corpus_db.reading():
        assert url_license_id(corpus_db, text) == expression


def test_a_refusal_clears_what_was_found_before(corpus_db: LicenseDatabase) -> None:
    found = Found(expression="MIT", category="exact", candidates=["x"])
    with corpus_db.reading():
        assert read_url(corpus_db, "spdx:Classpath-exception-2.0", found)
    assert (found.expression, found.category) == (None, "unresolved")
    assert (found.steps, found.expansions, found.candidates) == ([], [], [])
    assert found.reason == _exception("Classpath-exception-2.0")


# --- detect() ---


def _detect(db: LicenseDatabase, text: str) -> list[dict[str, object]]:
    return [dict(m) for m in LicenseDetector(db.location).detect(text)]


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        (APACHE_URL, "Apache-2.0"),
        ("www.apache.org/licenses/LICENSE-2.0.txt", "Apache-2.0"),
        ("https://spdx.org/licenses/MIT OR " + APACHE_URL, "Apache-2.0 OR MIT"),
        ("spdx:MIT", "MIT"),
        ("https://opensource.org/license/GPL-3.0-only", "GPL-3.0-only"),
        ("https://licenses.nuget.org/MS-PL%20OR%20Apache-2.0", "Apache-2.0 OR MS-PL"),
    ],
)
def test_detect_answers_a_url_by_name_without_a_warning(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str, expression: str
) -> None:
    (found,) = _detect(corpus_db, text)
    assert (found["expression"], found["method"], found["exact"]) == (
        expression,
        "name",
        True,
    )
    assert found["score"] == 1.0
    assert given.lines() == ""


def test_a_gnu_url_is_detected_as_the_bare_id_is(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    url = "https://www.gnu.org/licenses/gpl-3.0.html"
    (by_url,) = _detect(corpus_db, url)
    warned = given.lines()
    (by_id,) = _detect(corpus_db, "GPL-3.0")
    assert (by_url["expression"], by_url["exact"]) == ("GPL-3.0-only", False)
    assert {k: v for k, v in by_url.items() if k != "method"} == {
        k: v for k, v in by_id.items() if k != "method"
    }
    assert warned == (
        f"WARNING: input: variant not stated: {url}; using GPL-3.0-only\n"
    )
    assert (
        given.lines()
        == "WARNING: input: variant not stated: GPL-3.0; using GPL-3.0-only\n"
    )


# Each was a wrong guess of Tier 0 or the text tiers, which read "/", "." and
# "-" as spaces between words, before a URL was kept from them.
OVERRIDDEN = [
    "https://www.gnu.org/licenses/old-licenses/fdl-1.2.html",  # Parity-7.0.0
    "https://scancode-licensedb.aboutcode.org/classpath-exception-2.0.html",
    "https://opensource.org/license/Artistic-1.0",  # Artistic-1.0, by name
    "http://www.libpng.org/pub/png/src/libpng-LICENSE.txt",  # Libpng
    "https://www.gnu.org/licenses/gpl-3.0.en.html",  # AGPL-3.0-only
    "https://www.apache.org/licenses/LICENSE-2.0?x=1",  # Apache-1.0
    "https://licenses.nuget.org/MS-PL%20or%20Apache-2.0",  # ECL-2.0
    "<https://www.gnu.org/licenses/gpl-3.0.en.html>",
    "  https://www.apache.org/licenses/LICENSE-2.0?x=1\n",
]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("https://www.example.com/a/b", "not found: https://www.example.com/a/b"),
        (
            "https://www.unicode.org/license.txt",
            _several("Unicode-3.0", "Unicode-DFS-2016"),
        ),
        ("spdx:Classpath-exception-2.0", _exception("Classpath-exception-2.0")),
        (OVERRIDDEN[0], "url names several licences: GFDL-1.2, GFDL-1.2-invari"),
        (OVERRIDDEN[1], _exception("Classpath-exception-2.0")),
        (OVERRIDDEN[2], _several("Artistic-1.0", "Artistic-1.0-cl8")),
        (OVERRIDDEN[3], _several("Libpng", "libpng-1.6.35", "libpng-2.0")),
        *((text, "not found: ") for text in OVERRIDDEN[4:]),
    ],
)
def test_a_url_that_is_not_read_keeps_the_short_text_warning(
    corpus_db: LicenseDatabase, given: GivenWarnings, text: str, reason: str
) -> None:
    """No tier guesses a page resolve() did not read: the warning gives its
    reason, whole."""
    full = resolve(text, corpus_db)["reason"] or ""
    assert full.startswith(reason)
    assert _detect(corpus_db, text) == []
    assert given.lines() == f"WARNING: input: too few words for text: {full}\n"


@pytest.mark.parametrize(
    ("value", "unread"),
    [
        (APACHE_URL, False),  # read: an answer, no warning
        ("https://www.example.com/a/b", True),
        ("Apache 2", False),  # no URL
    ],
)
def test_unread_url_is_only_a_url_resolve_gave_nothing(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str, unread: bool
) -> None:
    resolution = resolve(value, corpus_db)
    assert unread_url(resolution, value) is unread
    assert bool(given.lines()) is unread


@pytest.mark.parametrize("text", OVERRIDDEN[:7])
def test_the_cli_detects_no_licence_for_a_url_not_read(
    corpus_db: LicenseDatabase, text: str
) -> None:
    code, out, err = _cli(corpus_db, "detect", text)
    assert (code, out) == (
        1,
        "EXPRESSION=\tMETHOD=\tEXACT=\tSCORE=\tSIMILARITY=\tCOVERAGE=\n",
    )
    reason = resolve(text, corpus_db)["reason"]
    assert err == f"WARNING: input: too few words for text: {reason}\n"


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        # Not a URL as a whole: the tiers read it as before.
        ("See https://www.apache.org/licenses/LICENSE-2.0 for the terms", "Apache-2.0"),
        ("Apache License 2.0", "Apache-2.0"),
    ],
)
def test_an_input_that_is_more_than_a_url_reaches_the_tiers(
    corpus_db: LicenseDatabase, text: str, expression: str
) -> None:
    assert _detect(corpus_db, text)[0]["expression"] == expression


# --- the CLI ---


def _cli(db: LicenseDatabase, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["--db", db.location, *args])
    return result.exit_code, result.stdout, result.stderr


def test_resolve_prints_the_licence_a_url_names(corpus_db: LicenseDatabase) -> None:
    assert _cli(corpus_db, "resolve", APACHE_URL) == (
        0,
        (
            "EXPRESSION=Apache-2.0\tCATEGORY=license_url\tTRUST=resolver_rule\n"
            f"STEP=license_url\tFROM={APACHE_URL}\tTO=Apache-2.0\n"
        ),
        "",
    )
    code, out, _ = _cli(
        corpus_db, "resolve", "https://www.gnu.org/licenses/gpl-3.0.html"
    )
    assert (code, out.splitlines()[0]) == (
        0,
        "EXPRESSION=GPL-3.0\tCATEGORY=assumed_only\tTRUST=none",
    )
    assert _cli(corpus_db, "resolve", "spdx:Classpath-exception-2.0") == (
        1,
        (
            "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none\n"
            f"REASON={_exception('Classpath-exception-2.0')}\n"
        ),
        "",
    )


@pytest.mark.parametrize("value", [APACHE_URL, "spdx:Classpath-exception-2.0"])
def test_resolve_json_is_the_resolution(corpus_db: LicenseDatabase, value: str) -> None:
    code, out, _ = _cli(corpus_db, "resolve", "--json", value)
    assert out == json_line(resolve(value, corpus_db)) + "\n"
    assert code == (0 if json.loads(out)["expression"] else 1)


def test_detect_and_the_flags_read_a_url(corpus_db: LicenseDatabase) -> None:
    code, out, err = _cli(corpus_db, "detect", APACHE_URL)
    assert (code, err) == (0, "")
    assert out == (
        "EXPRESSION=Apache-2.0\tMETHOD=name\tEXACT=true\tSCORE=1.0000\t"
        "SIMILARITY=\tCOVERAGE=\n"
    )
    code, out, _ = _cli(corpus_db, "detect", "--json", APACHE_URL)
    assert (code, json.loads(out)["method"]) == (0, "name")
    assert _cli(corpus_db, "is-osi", APACHE_URL) == _cli(
        corpus_db, "is-osi", "Apache-2.0"
    )
    code, out, err = _cli(corpus_db, "detect", "https://www.example.com/a/b")
    assert (code, out) == (
        1,
        "EXPRESSION=\tMETHOD=\tEXACT=\tSCORE=\tSIMILARITY=\tCOVERAGE=\n",
    )
    assert err == (
        "WARNING: input: too few words for text: "
        "not found: https://www.example.com/a/b\n"
    )


def test_id_declares_one_licence_not_a_url(corpus_db: LicenseDatabase) -> None:
    code, out, err = _cli(corpus_db, "detect", "--id", APACHE_URL)
    assert (code, out) == (2, "")
    assert err.startswith("ERROR: option: invalid: --id: https://www.apache.org")
    code, out, _ = _cli(corpus_db, "detect", "--id", "spdx:MIT")
    assert (code, out.startswith("EXPRESSION=MIT\tMETHOD=id")) == (0, True)


# --- time ---

_PAGE = "https://spdx.org/licenses/MIT"
_NUGET = "https://licenses.nuget.org/"

# Each shape that can backtrack, as a function of its number of repeats.
_SHAPES: tuple[Callable[[int], str], ...] = (
    lambda n: "https://x.org/" + "a" * n,
    lambda n: "https://x.org/" + "a/" * n,
    lambda n: "https://spdx.org/licenses/" + "M" * n,
    lambda n: "https://x.org/a?" + "&a=b" * n,
    lambda n: "https://x.org/a" + "%41" * n,
    lambda n: "https://" + "a." * n + "org/",
    lambda n: "<" * n + _PAGE + ">" * n,
    lambda n: _PAGE + "." * n,
    lambda n: _PAGE + " " * n + "x",
    lambda n: "x" + " " * n,
    lambda n: (_PAGE + " OR ") * n + _PAGE,
    lambda n: (_PAGE + "; ") * n + _PAGE,
    lambda n: _NUGET + "%20" * n,
    lambda n: _NUGET + "(" * n,
    lambda n: _NUGET + "(" * n + "MIT" + ")" * n,
    lambda n: _NUGET + "MIT%20OR%20" * n + "ISC",
    lambda n: _NUGET + "(MIT%20OR%20" * n + "ISC" + ")" * n,
    lambda n: _NUGET + "MIT" + "%00" * n,
    lambda n: _NUGET + "%41" * n,
)


def _payloads(size: int) -> list[str]:
    """Each shape repeated as often as fits in *size* characters."""
    found = []
    for shape in _SHAPES:
        base = len(shape(0))
        found.append(shape((size - base) // (len(shape(1)) - base)))
    return found


def test_the_reader_is_linear_on_a_small_input(corpus_db: LicenseDatabase) -> None:
    _time_the_reader(corpus_db, 2_000)


@pytest.mark.benchmark
def test_the_reader_is_linear_on_a_large_input(corpus_db: LicenseDatabase) -> None:
    _time_the_reader(corpus_db, 200_000)


def _time_the_reader(db: LicenseDatabase, size: int) -> None:
    """The reader and the key on URLs of about *size* characters (the key
    refuses one over 2,048, its reader times the rest)."""
    start = time.monotonic()
    for payload in _payloads(size):
        read_url(db, payload, Found())
        _key(payload)
    assert time.monotonic() - start < slack(max(2.0, size / 20_000))


def test_resolve_and_a_tag_are_fast_just_under_the_gate(
    corpus_db: LicenseDatabase,
) -> None:
    """``resolve()`` refuses a value over 2,000 characters before any reader:
    one of 1,999 reaches them all, as a tag's value reaches each word's."""
    payloads = _payloads(MAX_EXPRESSION_CHARS - 1)
    assert {len(p) <= MAX_EXPRESSION_CHARS - 1 for p in payloads} == {True}
    assert min(len(p) for p in payloads) > MAX_EXPRESSION_CHARS - 40
    markers = LicenseDetector(corpus_db.location).markers
    start = time.monotonic()
    with corpus_db.reading():
        for payload in payloads:
            resolve(payload, corpus_db)
            markers.resolve_license_value(payload, 1.0)
    assert time.monotonic() - start < slack(2.0)

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads a licence URL as its licence (``licenseid.resolveurl``,
issue #14): a smoke test, on the database and on the packaged list alike,
and the rules no page of the 3.29.0 List shows, on a list of a few rows.
The full tables are in ``test_resolver_url.py`` and
``test_resolver_url_data.py``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, resolve

APACHE = (
    "https://opensource.org/license/Apache-2.0",
    "https://opensource.org/license/apache-2.0",
    "https://www.apache.org/licenses/LICENSE-2.0",
    "https://spdx.org/licenses/Apache-2.0",
    "https://spdx.org/licenses/Apache-2.0.html",
    "https://scancode-licensedb.aboutcode.org/apache-2.0.html",
    "spdx:Apache-2.0",
)

#: ``{value: (expression, category, candidates, reason)}``
CASES = {
    **{url: ("Apache-2.0", "license_url", [], None) for url in APACHE},
    "https://www.gnu.org/licenses/gpl-3.0.html": (
        "GPL-3.0",
        "assumed_only",
        ["GPL-3.0-only", "GPL-3.0-or-later"],
        None,
    ),
    "https://spdx.org/licenses/Classpath-exception-2.0.html": (
        None,
        "unresolved",
        [],
        "url names an exception: Classpath-exception-2.0",
    ),
    "https://www.unicode.org/license.txt": (
        None,
        "unresolved",
        [],
        "url names several licences: Unicode-3.0, Unicode-DFS-2016",
    ),
    "https://www.example.com/a/b": (
        None,
        "unresolved",
        [],
        "not found: https://www.example.com/a/b",
    ),
    "spdx:MIT+": ("MIT+", "license_url", [], None),
    "https://fedoraproject.org/wiki/Licensing/MIT#enna": (
        None,
        "unresolved",
        [],
        "url names several licences: Adobe-Glyph, MIT-enna, MIT-feh, mpich2",
    ),
    "https://opensource.org/license/wxWindows": (
        None,
        "unresolved",
        [],
        "url names a licence with an exception: wxWindows, WxWindows-exception-3.1",
    ),
    # a "/" of a URL with no scheme is no operator
    "www.example.com/a/b": (None, "unresolved", [], "not found: www.example.com/a/b"),
}


def _summary(value: str, db: LicenseDatabase | None) -> tuple[object, ...]:
    got = resolve(value, db) if db is not None else resolve(value, source="packaged")
    return got["expression"], got["category"], got["candidates"], got["reason"]


@pytest.mark.parametrize(("value", "expected"), CASES.items(), ids=list(CASES))
def test_a_url_reads_as_its_licence(
    monkeypatch: pytest.MonkeyPatch,
    corpus_db: LicenseDatabase,
    value: str,
    expected: tuple[object, ...],
) -> None:
    assert _summary(value, corpus_db) == expected
    ship(monkeypatch, fixture_bundle())
    assert _summary(value, None) == expected


# --- the rules no page of the List shows, on a list of a few rows ---

PAGE = "https://example.org/page"
_FEW = (
    Lic("MIT", "MIT License"),
    Lic("Foo-with-bar", "Foo with Bar", is_deprecated=True),
    Lic("Baz-with-bar", "Baz with Bar", is_deprecated=True),
    Lic("Foo", "Foo"),
    Lic("Old-with-bar", "Old with Bar", is_deprecated=True, superseded_by="Foo"),
    Lic("New-with-bar", "New with Bar"),
)


def _page(urls: list[tuple[str, bool, str]], value: str = PAGE) -> tuple[object, ...]:
    """The expression and reason of *value* on a list of :data:`_FEW` and
    the exception ``Bar``, whose pages are *urls*."""
    for path in seeded_db("url_rules", _FEW, ("Bar",), urls):
        got = resolve(value, LicenseDatabase(path, create=False))
        return got["expression"], got["reason"]
    raise AssertionError("no database")


def _with(*ids: str) -> tuple[None, str]:
    return None, f"url names a licence with an exception: {', '.join(ids)}"


@pytest.mark.parametrize(
    ("licences", "expected"),
    [
        (("Foo-with-bar",), ("Foo-with-bar", None)),
        (
            ("Foo-with-bar", "Baz-with-bar"),
            (None, "url names several licences: Baz-with-bar, Foo-with-bar"),
        ),
        (("Foo-with-bar", "MIT"), _with("Foo-with-bar", "MIT", "Bar")),
        (("MIT", "Foo-with-bar"), _with("Foo-with-bar", "MIT", "Bar")),
        (("MIT",), _with("MIT", "Bar")),
        (("Old-with-bar",), _with("Old-with-bar", "Bar")),  # it has a successor
        (("New-with-bar",), _with("New-with-bar", "Bar")),  # not deprecated
    ],
    ids=["old", "two-old", "and-another", "another-first", "plain", "renamed", "new"],
)
def test_a_licence_beside_an_exception_is_read_only_as_an_old_id_of_both(
    licences: tuple[str, ...], expected: tuple[object, ...]
) -> None:
    urls = [(i, False, PAGE) for i in licences] + [("Bar", True, PAGE)]
    assert _page(urls) == expected


@pytest.mark.parametrize(
    ("urls", "expected"),
    [
        # a place on the page of its own owner: the owner
        ([("MIT", False, PAGE), ("MIT", False, PAGE + "#a")], ("MIT", None)),
        ([("MIT", False, PAGE + "#a"), ("MIT", False, PAGE)], ("MIT", None)),
        # of another licence: both, as the page names
        (
            [("MIT", False, PAGE), ("Foo", False, PAGE + "#a")],
            (None, "url names several licences: Foo, MIT"),
        ),
        ([("MIT", False, PAGE), ("Bar", True, PAGE + "#a")], _with("MIT", "Bar")),
        # only a place: the page names nothing; an empty fragment is none
        ([("MIT", False, PAGE + "#a")], (None, f"not found: {PAGE}")),
        ([("MIT", False, PAGE + "#")], ("MIT", None)),
    ],
    ids=["same", "same-place-first", "another", "exception", "place-only", "empty"],
)
def test_a_place_on_a_page_adds_its_owner_to_the_page(
    urls: list[tuple[str, bool, str]], expected: tuple[object, ...]
) -> None:
    assert _page(urls) == expected
    declared = PAGE + "#b"  # a declared URL with a fragment reads as its page
    reason = None if expected[1] is None else str(expected[1]).replace(PAGE, declared)
    assert _page(urls, declared) == (expected[0], reason)

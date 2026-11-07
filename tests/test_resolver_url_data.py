# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The pages of the 3.29.0 List (``fixtures/license-list/spdx-see-also.json``,
the ``seeAlso`` of every licence and exception) and ``resolve()``: each page
reads as its owner, the successor of its owner, the bare ID of a GNU family,
an alias target, or is refused, and never reads as another ID; so does each
URL with a ``#fragment``, as the List writes it.

The pins (``AMBIGUOUS``, ``FAMILIES``, ``MIXED`` and the counts) are the
current result: a refresh of the List that moves one fails here, to be read
and pinned again, as ``tests/fixtures/README.md`` says. The alias, host,
choice and ScanCode tables of ``licenseid.resolveurl`` are held to the List
here too.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections import Counter
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from packaged_list import fixture_data
from resolver_corpus import SEE_ALSO_LIST, list_rows

from licenseid.errors import reason_detail
from licenseid.listindex import ListIndex
from licenseid.resolver import resolve_with
from licenseid.resolvertypes import Resolution
from licenseid.resolveurl import (
    DUAL_PAGES,
    ID_PAGES,
    SCANCODE_NOT_SPDX,
    URL_ALIASES,
)
from licenseid.urlkey import url_key

#: Pages the List gives two or more licences that are no family, with a
#: fragment or without (the first three keys of ``fedoraproject.org`` and
#: ``docs.python.org``), and the pages of ``DUAL_PAGES``: refused.
AMBIGUOUS = frozenset(
    {
        "7-zip.org/sdk",
        "antlr2.org/license",
        "bzip.org/1.0.5/bzip2-manual-1.0.5",
        "cryptographicautonomylicense.com/license-text",
        "docs.python.org/3/license",
        "fedoraproject.org/wiki/licensing/fsf_unlimited_license",
        "fedoraproject.org/wiki/licensing/henry_spencer_reg-ex_library_license",
        "fedoraproject.org/wiki/licensing/mit",
        "forge.gouv.qc.ca/licence/liliq-p",
        "freebsd.org/copyright/freebsd-license",
        "ftp.gnu.org/gnu/aspell/dict/en/aspell6-en-2020.12.07-0.tar.bz2",
        "gnu.org/licenses/fdl-1.3",
        "gnu.org/licenses/old-licenses/fdl-1.1",
        "gnu.org/licenses/old-licenses/fdl-1.2",
        "glassfish.java.net/public/cddl+gpl_1_1",
        "javaee.github.io/glassfish/license",
        "libpng.org/pub/png/src/libpng-license",
        "microsoft.com/opensource/licenses.mspx",
        "ohwr.org/project/cernohl/wikis/documents/cern-ohl-version-2",
        "opensource.org/license/artistic-1-0",
        "opensource.org/license/cal-1-0",
        "saxproject.org/copying",
        "scripts.sil.org/cms/scripts/page?item_id=ofl10_web",
        "sourceforge.net/projects/sevenzip/files/lzma%20sdk",
        "unicode.org/copyright",
        "unicode.org/license",
        "web.mit.edu/kerberos/krb5-1.21/doc/mitk5license",
    }
)

#: Pages of X, X+, X-only and X-or-later (some of them): the bare ID X.
FAMILIES = {
    "affero.org/oagpl": "AGPL-1.0",
    "github.com/openjdk/jdk/blob/6162e2c5213c5dd7c1127fd9616b543efa898962/license": (
        "GPL-2.0"
    ),
    "gnu.org/licenses/agpl": "AGPL-3.0",
    "gnu.org/licenses/gpl-3.0": "GPL-3.0",
    "gnu.org/licenses/lgpl+gpl-3.0": "LGPL-3.0",
    "gnu.org/licenses/lgpl-3.0": "LGPL-3.0",
    "gnu.org/licenses/old-licenses/gpl-1.0": "GPL-1.0",
    "gnu.org/licenses/old-licenses/gpl-2.0": "GPL-2.0",
    "gnu.org/licenses/old-licenses/lgpl-2.0": "LGPL-2.0",
    "gnu.org/licenses/old-licenses/lgpl-2.1": "LGPL-2.1",
    "opensource.org/license/agpl-3-0": "AGPL-3.0",
    "opensource.org/license/gpl-2-0": "GPL-2.0",
    "opensource.org/license/gpl-3-0": "GPL-3.0",
    "opensource.org/license/lgpl-2-1": "LGPL-2.1",
    "opensource.org/license/lgpl-3-0": "LGPL-3.0",
}

#: Pages of a licence and an exception: the licence where it is one of the
#: List's old IDs of both (``GPL-3.0-with-GCC-exception``), else refused
#: (None), ``wxWindows`` too: it is no ``-with-`` ID.
MIXED = {
    "ac-archive.sourceforge.net/doc/copyright": "GPL-2.0-with-autoconf-exception",
    "github.com/maranget/hevea/blob/master/license": None,
    "gnu.org/licenses/autoconf-exception-3.0": "GPL-3.0-with-autoconf-exception",
    "gnu.org/licenses/gcc-exception-3.1": "GPL-3.0-with-GCC-exception",
    "gnu.org/software/classpath/license": "GPL-2.0-with-classpath-exception",
    "opensource.org/license/wxwindows": None,
}

#: Read as a licence that the List renames (``StandardML-NJ`` to ``SMLNJ``).
RENAMED = frozenset({"smlnj.org/license"})

#: Pages of the aliases of MPL-2.0 and OFL-1.1: the List gives each the
#: licence and its variants.
OVERRIDDEN = frozenset(
    {
        "mozilla.org/mpl/2.0",
        "opensource.org/license/mpl-2-0",
        "opensource.org/license/ofl-1-1",
        "scripts.sil.org/cms/scripts/page?item_id=ofl_web",
    }
)

#: The pages by what ``resolve()`` makes of each (the exceptions: 78 pages of
#: exceptions only; ``with exception``: a licence and an exception).
KINDS = {
    "owner": 702,
    "rename": 1,
    "family": 15,
    "alias": 4,
    "several": 27,
    "exception": 78,
    "with exception": 2,
}

#: The pages with no key (``licenseid.urlkey``), by host: archive pages with
#: a URL inside, a path with ``//``, an ``ftp:`` URL.
UNKEYABLE = {
    "web.archive.org": 19,
    "wayback.archive.org": 4,
    "metadata.ftp-master.debian.org": 3,
    "ftp.tin.org": 1,
}

#: The pages with a ``#fragment`` (a place on a page,
#: ``resolveurl.fragment_page_key``), and the keys only they give.
FRAGMENTED = 172
FRAGMENT_ONLY = 142

#: The List's page of each licence ID with a "+": (read, not found). Not
#: found: an ID that ends in ``-only``, ``-or-later`` or a "+" already.
PLUS_PAGES = (700, 40)

#: The URLs with a fragment, as the List writes them, by what they read as:
#: a page only a fragment gives names nothing, and the five others are of a
#: page of several licences.
FRAGMENT_READINGS = {"not found": 167, "several": 5}


class Pages:
    """The pages of the List fixture: the first URL of each key, the owners
    of each (``(ID, is_exception)``), the owners of a place on it (a URL
    with a fragment), and the pages left out of those."""

    def __init__(self) -> None:
        self.first: dict[str, str] = {}
        self.owners: dict[str, list[tuple[str, bool]]] = {}
        self.places: dict[str, list[tuple[str, bool]]] = {}
        self.fragmented: list[str] = []
        self.unkeyable: list[str] = []
        for owner, exception, url in list_rows(SEE_ALSO_LIST, "urls"):
            text, key = str(url), url_key(str(url))
            listed = (str(owner), bool(exception))
            if "#" in text:
                self.fragmented.append(text)
                if key is not None:
                    self.places.setdefault(key, []).append(listed)
            elif key is None:
                self.unkeyable.append(text)
            else:
                self.first.setdefault(key, text)
                self.owners.setdefault(key, []).append(listed)
        self.fragment_only = {k for k in self.places if k not in self.first}

    def licences(self, key: str) -> list[str]:
        """The licences (no exception) that give the page *key*, or a place
        on it."""
        owners = [*self.owners.get(key, ()), *self.places.get(key, ())]
        return sorted({o for o, exception in owners if not exception})


PAGES = Pages()


@pytest.fixture(scope="module")
def index() -> ListIndex:
    return ListIndex(fixture_data())


_REFUSALS = {
    "url names several licences": "several",
    "url names an exception": "exception",
    "url names a licence with an exception": "with exception",
    "not found": "not found",
}


def _kind(got: Resolution, licences: list[str]) -> str:
    """What the reading *got* of a page of *licences* is, in the words of
    :data:`KINDS`."""
    if got["expression"] is None:
        return _REFUSALS[(got["reason"] or "").split(":")[0]]
    if got["steps"][0]["detail"] == "alias":
        return "alias"
    if len(licences) == 1:
        return "owner"
    return "family" if got["category"] == "assumed_only" else "rename"


def _allowed(index: ListIndex, licences: list[str], key: str) -> set[str]:
    """The expressions a page of *licences* may read as: each licence, what
    it is renamed to, its bare ID (``X`` of ``X-only``, where the List split
    ``X`` with no successor), the alias target."""
    allowed = set(licences)
    for license_id in licences:
        for qualifier in ("-only", "-or-later"):
            bare = index.get_license_details(license_id.removesuffix(qualifier))
            if bare and bare.get("is_deprecated") and not bare.get("superseded_by"):
                allowed.add(bare["license_id"])
        details = index.get_license_details(license_id)
        while details and details.get("superseded_by"):
            allowed.add(details["superseded_by"])
            details = index.get_license_details(details["superseded_by"])
    if key in URL_ALIASES:
        allowed.add(URL_ALIASES[key].license_id)
    return allowed


def _readings(index: ListIndex) -> Iterator[tuple[str, list[str], Resolution]]:
    for key, url in PAGES.first.items():
        yield key, PAGES.licences(key), resolve_with(index, url)


def test_every_page_of_the_list_reads_as_its_licence_or_is_refused(
    index: ListIndex,
) -> None:
    kinds: Counter[str] = Counter()
    for key, licences, got in _readings(index):
        kinds[_kind(got, licences)] += 1
        if got["expression"] is None:
            assert (got["category"], got["steps"]) == ("unresolved", []), key
            assert (got["reason"] or "").startswith("url names "), key
        else:
            assert got["category"] != "unresolved", key
            assert got["expression"] in _allowed(index, licences, key), key
            assert got["steps"][0]["kind"] == "license_url", key
    assert dict(kinds) == KINDS
    assert sum(KINDS.values()) == len(PAGES.first)


def test_the_pages_of_the_list_by_kind_are_the_pinned_ones(index: ListIndex) -> None:
    by_kind: dict[str, dict[str, str | None]] = {}
    for key, licences, got in _readings(index):
        kind = _kind(got, licences)
        by_kind.setdefault(kind, {})[key] = got["expression"]
    assert frozenset(by_kind["several"]) == AMBIGUOUS
    assert by_kind["family"] == FAMILIES
    assert frozenset(by_kind["rename"]) == RENAMED
    assert (
        frozenset(by_kind["alias"]) == OVERRIDDEN == (OVERRIDDEN & PAGES.first.keys())
    )
    mixed = {
        key
        for key, owners in PAGES.owners.items()
        if {exception for _, exception in owners} == {True, False}
    }
    assert mixed == set(MIXED)
    read = {k: e for k, e in by_kind["owner"].items() if k in MIXED}
    assert read == {k: e for k, e in MIXED.items() if e is not None}
    refused = {k for k, e in MIXED.items() if e is None}
    assert frozenset(by_kind["with exception"]) == refused


def test_a_page_of_exceptions_only_is_refused_with_the_sorted_exceptions(
    index: ListIndex,
) -> None:
    for key, licences, got in _readings(index):
        if licences:
            continue
        exceptions = sorted({o for o, _ in PAGES.owners[key]})
        detail = reason_detail(", ".join(exceptions))
        assert got["reason"] == f"url names an exception: {detail}", key


def test_the_pages_left_out_are_the_pinned_ones() -> None:
    hosts = Counter(urlsplit(url).hostname for url in PAGES.unkeyable)
    assert dict(hosts) == UNKEYABLE
    assert len(PAGES.fragmented) == FRAGMENTED
    assert len(PAGES.fragment_only) == FRAGMENT_ONLY
    assert all(url_key(url) is None for url in PAGES.unkeyable)


def test_a_page_only_a_fragment_gives_reads_as_nothing(index: ListIndex) -> None:
    """``gpl-faq.html#FontException`` is a place on a page: the page is no
    licence."""
    assert not PAGES.fragment_only & URL_ALIASES.keys()  # no alias is lost
    for key in PAGES.fragment_only:
        got = resolve_with(index, f"https://{key}")
        assert got["expression"] is None, key
        assert (got["reason"] or "").startswith("not found: "), key


def test_a_url_with_a_fragment_never_reads_as_another_licence(
    index: ListIndex,
) -> None:
    """Each URL of the List with a fragment, as written: the licence of its
    page (one alone), refused, or nothing; never an ID the page is not
    given to (``Licensing/MIT#enna`` was ``mpich2``, the bare page's)."""
    kinds: Counter[str] = Counter()
    for url in PAGES.fragmented:
        key = url_key(url) or ""  # "": a URL with no key
        got = resolve_with(index, url)
        kinds[_kind(got, PAGES.licences(key))] += 1
        if got["expression"] is not None:
            assert got["expression"] in _allowed(index, PAGES.licences(key), key)
        elif not key or key in PAGES.fragment_only:
            assert got["reason"] == f"not found: {reason_detail(url)}", url
        else:
            assert (got["reason"] or "").startswith("url names "), url
    assert dict(kinds) == FRAGMENT_READINGS
    assert sum(FRAGMENT_READINGS.values()) == FRAGMENTED


# --- the IDs ---

FORMS = (
    "https://spdx.org/licenses/{id}",
    "https://spdx.org/licenses/{id}.html",
    "https://spdx.org/licenses/{id}.json",
    "spdx:{id}",
    "https://spdx.org/licenses/{lower}",
    "http://spdx.org/licenses/{id}/",
)


def test_every_id_has_six_urls_that_read_as_it_does(index: ListIndex) -> None:
    data = fixture_data()
    licences = [entry["licenseId"] for entry in data.licenses]
    exceptions = [entry["licenseExceptionId"] for entry in data.exceptions]
    wrong: list[tuple[str, str]] = []
    for license_id in licences:
        alone = resolve_with(index, license_id)
        for form in FORMS:
            url = form.format(id=license_id, lower=license_id.lower())
            got = resolve_with(index, url)
            if (got["expression"], got["candidates"]) != (
                alone["expression"],
                alone["candidates"],
            ):
                wrong.append((url, str(got["expression"])))
    for exception_id in exceptions:
        for form in FORMS:
            url = form.format(id=exception_id, lower=exception_id.lower())
            got = resolve_with(index, url)
            if got["reason"] != f"url names an exception: {exception_id}":
                wrong.append((url, str(got["reason"])))
    assert not wrong
    assert len(licences) > 700 and len(exceptions) > 50


@pytest.mark.parametrize("form", ["https://spdx.org/licenses/{id}+", "spdx:{id}+"])
def test_every_id_with_a_plus_on_the_list_page_reads_as_the_id_with_it(
    index: ListIndex, form: str
) -> None:
    """``spdx.org/licenses/MIT+`` is ``MIT+``, as a tag read it; a "+" the
    ID cannot take (``GPL-2.0-only+``, ``GPL-2.0++``) names nothing."""
    read, unread = 0, 0
    for entry in fixture_data().licenses:
        license_id = entry["licenseId"]
        alone = resolve_with(index, f"{license_id}+")
        got = resolve_with(index, form.format(id=license_id))
        assert (got["expression"], got["candidates"]) == (
            alone["expression"],
            alone["candidates"],
        ), license_id
        if got["expression"] is None:
            assert (got["reason"] or "").startswith("not found: "), license_id
            unread += 1
        else:
            assert got["steps"][0]["to"] == f"{license_id}+", license_id
            read += 1
    assert (read, unread) == PLUS_PAGES


# --- the tables of resolveurl ---


@pytest.mark.parametrize("key", URL_ALIASES)
def test_an_alias_is_a_reviewed_page_of_one_licence(index: ListIndex, key: str) -> None:
    alias = URL_ALIASES[key]
    assert url_key(f"https://{key}") == key  # the form the reader looks up
    assert index.get_license_details(alias.license_id) is not None
    assert url_key(alias.source) is not None
    assert alias.source.startswith("https://")
    # not a family or an unversioned page: not the bare ID a family reads as
    assert key not in FAMILIES
    assert alias.license_id not in set(FAMILIES.values())
    if key.startswith("gnu.org/"):
        assert any(c.isdigit() for c in key.rsplit("/", 1)[-1])


def test_the_list_pages_of_an_alias_name_it_among_their_ids() -> None:
    """An alias is read where the List gives the page no licence, or its
    licence among others (the overrides)."""
    for key, alias in URL_ALIASES.items():
        owners = PAGES.owners.get(key)
        assert owners is None or alias.license_id in PAGES.licences(key), key
        assert (owners is not None) == (key in OVERRIDDEN)


def test_the_hosts_that_name_an_id_end_in_a_slash() -> None:
    for prefix in ID_PAGES:
        assert prefix.endswith("/")
        assert prefix == prefix.lower()
        assert url_key(f"https://{prefix}x") == f"{prefix}x"


@pytest.mark.parametrize("key", sorted(SCANCODE_NOT_SPDX))
def test_a_scancode_key_of_another_licence_is_not_read_as_its_spdx_id(
    index: ListIndex, key: str
) -> None:
    """Each is, folded, an ID of the List (so its entry has an effect), and
    its ScanCode page names no licence of the SPDX List."""
    assert key == key.lower()
    page = resolve_with(index, f"https://scancode-licensedb.aboutcode.org/{key}")
    assert page["expression"] is None
    assert (page["reason"] or "").startswith("not found: ")
    spdx = resolve_with(index, f"https://spdx.org/licenses/{key}")
    assert spdx["expression"] is not None or (spdx["reason"] or "").startswith(
        "url names an exception: "
    )


@pytest.mark.parametrize("key", DUAL_PAGES)
def test_a_page_of_a_choice_is_a_page_of_the_list_and_is_refused(
    index: ListIndex, key: str
) -> None:
    offered = DUAL_PAGES[key]
    assert url_key(PAGES.first[key]) == key  # as written on the List
    assert all(index.get_license_details(i) is not None for i in offered)
    assert set(PAGES.licences(key)) < set(offered)
    got = resolve_with(index, PAGES.first[key])
    detail = reason_detail(", ".join(sorted(offered)))
    assert got["reason"] == f"url names several licences: {detail}"
    assert (got["expression"], got["steps"]) == (None, [])

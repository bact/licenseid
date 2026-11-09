# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.listindex``: the SPDX License List in memory answers each
read of ``ListLookup`` as the database built from the same release does,
and the packaged one is loaded once per process."""
# pylint: disable=missing-function-docstring

import dataclasses
import gzip
import threading
import time
from pathlib import Path
from unittest import mock

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from list_entries import exc_entry, lic_entry
from packaged_list import database_of, fixture_data, synthetic_bundle
from release_fakes import ship
from timing import slack

from licenseid import listindex, spdxdata
from licenseid.listindex import ListIndex, packaged_index, packaged_problem
from licenseid.listlookup import ListedUrl, ListLookup
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.versionkey import version_key

# Two IDs that fold to one (the first wins), a deprecated rename with its
# successor, a split ID, one in use with no text (not kept), and a
# deprecated one with no text (kept); exceptions with a rename, and one whose
# ID is also a deprecated licence's (the exception wins the mapping).
# Their pages (seeAlso): one listed twice, one two licences share by key, the
# page of a GNU family, one of a licence that is not kept, one a licence and an
# exception share, one the key reads as no key, one that is not a list, and
# items that are no string.
OSI_MIT = "https://opensource.org/license/mit/"
GNU_GPL2 = "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html"
GONE = "https://example.org/gone"
LICENSES = (
    lic_entry("MIT", "MIT License", see_also=[OSI_MIT, OSI_MIT]),
    lic_entry("mit", "Lower MIT", see_also=[OSI_MIT.upper()]),
    lic_entry(
        "SMLNJ",
        "Standard ML of New Jersey License",
        see_also="https://www.smlnj.org/license.html",
    ),
    lic_entry("StandardML-NJ", "Standard ML of New Jersey License", deprecated=True),
    lic_entry(
        "GPL-2.0-only", "GNU General Public License v2.0 only", see_also=[GNU_GPL2]
    ),
    lic_entry(
        "GPL-2.0-or-later",
        "GNU General Public License v2.0 or later",
        see_also=[GNU_GPL2],
    ),
    lic_entry(
        "GPL-2.0",
        "GNU General Public License v2.0 only",
        deprecated=True,
        see_also=[GNU_GPL2],
    ),
    lic_entry(
        "GPL-2.0+",
        "GNU General Public License v2.0 or later",
        deprecated=True,
        see_also=[GNU_GPL2],
    ),
    lic_entry("NoText-1.0", "No Text License", see_also=["https://example.org/nt"]),
    lic_entry("Gone-1.0", "Gone License", deprecated=True, see_also=[GONE]),
    lic_entry("Clash-1.0", "Clash License", deprecated=True),
    lic_entry("Clash-2.0", "Clash License"),
    lic_entry(
        "Plain", "Plain License", deprecated=None, see_also=["https://skip.example/"]
    ),
    lic_entry("K-1.0", "K License", see_also=[7, None, ["x"], "https://k.example/"]),
)
TEXTS = {
    lic["licenseId"]: f"Text of {lic['licenseId']}."
    for lic in LICENSES
    if lic["licenseId"] not in ("NoText-1.0", "Gone-1.0")
}
CLASSPATH = "https://www.gnu.org/software/classpath/license.html"
EXCEPTIONS = (
    exc_entry(
        "Classpath-exception-2.0", "Classpath exception 2.0", see_also=[CLASSPATH]
    ),
    exc_entry("Old-exception", "Classpath exception 2.0", deprecated=True),
    exc_entry("Clash-1.0", "Clash exception", deprecated=True),
    exc_entry("Clash-exception", "Clash exception", see_also=[GONE]),
    exc_entry(
        "Lone-exception",
        "Lone exception",
        deprecated=True,
        see_also=["https://example.org/lone"],
    ),
    exc_entry("K-exception", "K exception", see_also={"url": "https://k.example/"}),
)
RAW = synthetic_bundle(LICENSES, TEXTS, EXCEPTIONS)
# The real one, to spec a fake on: conftest's autouse fixture replaces it
# with a mock before each test, and Python 3.14 will not spec a mock.
_REAL_BUNDLE = spdxdata.packaged_bundle


@pytest.fixture(name="index")
def _index() -> ListIndex:
    return ListIndex(SpdxData.from_bundle(RAW, None))


@pytest.fixture(name="db")
def _db(tmp_path: Path) -> ListLookup:
    return database_of(RAW, tmp_path / "licenses.db")


PROBES = [
    "MIT",
    "mit",
    "  MiT\t",
    "MIT\u212a",
    "\u212aMIT",
    "\u212a-1.0",  # the KELVIN SIGN is no K: str.lower would make it one
    "k-1.0",
    "smlnj",
    "StandardML-NJ",
    "GPL-2.0",
    "gpl-2.0+",
    "NoText-1.0",
    "Gone-1.0",
    "Clash-1.0",
    "Plain",
    "",
    " ",
    "Nope",
]


@pytest.mark.parametrize("probe", PROBES)
def test_a_licence_is_found_as_in_the_database(
    index: ListIndex, db: ListLookup, probe: str
) -> None:
    def fields(row: object) -> object:
        if not isinstance(row, dict):
            return row
        return (
            row["license_id"],
            row["is_deprecated"],
            row.get("superseded_by") or None,
        )

    assert fields(index.get_license_details(probe)) == fields(
        db.get_license_details(probe)
    )


@pytest.mark.parametrize(
    "probe",
    [
        "Classpath-exception-2.0",
        "classpath-EXCEPTION-2.0 ",
        "Old-exception",
        "clash-1.0",
        "Lone-exception",
        "Classpath-exception-2.\u212a",
        "\u212a-exception",
        "k-EXCEPTION",
        "MIT",
        "",
    ],
)
def test_an_exception_is_found_as_in_the_database(
    index: ListIndex, db: ListLookup, probe: str
) -> None:
    def fields(row: object) -> object:
        if not isinstance(row, dict):
            return row
        return (
            row["exception_id"],
            row["is_deprecated"],
            row.get("superseded_by") or None,
        )

    assert fields(index.get_exception_details(probe)) == fields(
        db.get_exception_details(probe)
    )


def test_the_whole_tables_are_the_databases(index: ListIndex, db: ListLookup) -> None:
    """In the same order too: the deprecated mappings put the licences
    first, then the exceptions, which win a clash."""
    assert list(index.get_deprecated_mappings().items()) == list(
        db.get_deprecated_mappings().items()
    )
    assert index.get_deprecated_mappings() == {
        "StandardML-NJ": "SMLNJ",
        "GPL-2.0+": "GPL-2.0-or-later",
        "Clash-1.0": "Clash-exception",
        "Old-exception": "Classpath-exception-2.0",
    }
    assert index.get_active_ids_by_name() == db.get_active_ids_by_name()
    keyed = {
        key: [(row["license_id"], row["is_deprecated"]) for row in rows]
        for key, rows in db.get_names_by_key(version_key).items()
    }
    assert {
        key: [(row["license_id"], row["is_deprecated"]) for row in rows]
        for key, rows in index.get_names_by_key(version_key).items()
    } == keyed
    assert list(index.get_names_by_key(version_key)) == list(keyed)


def test_an_id_with_no_text_is_not_kept(index: ListIndex) -> None:
    """Not kept, unless deprecated (listrules.kept); not in the names in use
    either (review gap G8)."""
    assert index.get_license_details("NoText-1.0") is None
    assert "no text license" not in index.get_active_ids_by_name()
    assert index.get_license_details("Gone-1.0") == {
        "license_id": "Gone-1.0",
        "is_deprecated": True,
    }
    assert all(
        row["license_id"] != "NoText-1.0"
        for rows in index.get_names_by_key(version_key).values()
        for row in rows
    )


def test_the_names_by_key_follow_the_key(index: ListIndex) -> None:
    first = index.get_names_by_key(version_key)
    assert index.get_names_by_key(version_key) is first  # built once

    def upper(text: str) -> str:
        return text.upper()

    assert set(index.get_names_by_key(upper)) >= {"MIT", "SMLNJ"}
    assert index.get_names_by_key(version_key) is not first  # one key kept


def url_key(url: str) -> str | None:
    """A key of a URL for these tests: no key for the ``skip.`` host."""
    return None if "//skip." in url else url.lower()


def lic_url(owner: str) -> ListedUrl:
    return {"id": owner, "is_exception": False}


def exc_url(owner: str) -> ListedUrl:
    return {"id": owner, "is_exception": True}


# The kept licences' pages in list order, then the exceptions': each owner once
# per key, a page a licence and an exception share under both.
BY_URL = {
    OSI_MIT: [lic_url("MIT"), lic_url("mit")],
    GNU_GPL2.lower(): [
        lic_url("GPL-2.0-only"),
        lic_url("GPL-2.0-or-later"),
        lic_url("GPL-2.0"),
        lic_url("GPL-2.0+"),
    ],
    GONE: [lic_url("Gone-1.0"), exc_url("Clash-exception")],
    "https://k.example/": [lic_url("K-1.0")],
    CLASSPATH: [exc_url("Classpath-exception-2.0")],
    "https://example.org/lone": [exc_url("Lone-exception")],
}


def test_the_pages_are_the_databases(index: ListIndex, db: ListLookup) -> None:
    """Licences first, then exceptions, in list order, each owner once per
    key; no page of a licence that is not kept, of a ``seeAlso`` that is not
    a list, or that the key reads as no key."""
    from_db = db.get_ids_by_url(url_key)
    assert index.get_ids_by_url(url_key) == from_db == BY_URL
    assert list(index.get_ids_by_url(url_key)) == list(from_db) == list(BY_URL)


def test_the_pages_by_key_follow_the_key(index: ListIndex) -> None:
    first = index.get_ids_by_url(url_key)
    assert index.get_ids_by_url(url_key) is first  # built once

    def host(url: str) -> str | None:
        return url.split("/")[2].lower()

    assert index.get_ids_by_url(host)["opensource.org"] == [
        lic_url("MIT"),
        lic_url("mit"),
    ]
    assert index.get_ids_by_url(url_key) is not first  # one key kept
    assert index.get_ids_by_url(url_key) == first


def test_a_returned_row_is_a_copy(index: ListIndex) -> None:
    row = index.get_license_details("MIT")
    assert row is not None
    row["license_id"] = "changed"
    assert index.get_license_details("MIT") == {
        "license_id": "MIT",
        "is_deprecated": False,
    }


@pytest.mark.parametrize(
    ("release_date", "expected"), [("2030-01-01", "2030-01-01"), (None, "")]
)
def test_the_metadata(release_date: str | None, expected: str) -> None:
    data = SpdxData("9.99", release_date, LICENSES, EXCEPTIONS, TEXTS)
    index = ListIndex(data)
    assert index.get_metadata() == {
        "license_list_version": "9.99",
        "release_date": expected,
    }
    assert index.version == "9.99"


def test_reading_is_a_block_that_opens_nothing(index: ListIndex) -> None:
    with index.reading():
        assert index.get_license_details("MIT")
    with index.reading(), index.reading():  # nested, as a caller may
        pass


def test_the_texts_are_not_kept(index: ListIndex) -> None:
    """IDs and names only (F11): no text survives the build."""
    held = repr(vars(index))
    assert "Text of MIT." not in held


# --- packaged_index() ---


def test_no_bundle_is_no_index() -> None:
    assert packaged_index() is None
    assert packaged_problem() == "not found"


def test_the_bundle_is_loaded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = mock.create_autospec(_REAL_BUNDLE, return_value=RAW)
    monkeypatch.setattr(spdxdata, "packaged_bundle", fake)
    first = packaged_index()
    assert first is not None and first.version == "9.99"
    assert packaged_index() is first
    assert packaged_problem() == ""
    assert fake.call_count == 1


def test_a_reset_reads_the_bundle_again(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, RAW)
    first = packaged_index()
    listindex.reset_packaged_index()
    second = packaged_index()
    assert second is not first and second is not None
    ship(monkeypatch, None)  # ship resets too
    assert packaged_index() is None


@pytest.mark.parametrize(
    ("raw", "detail"),
    [
        (b"not gzip", "BadGzipFile: Not a gzipped file (b'no')"),
        (gzip.compress(b"[]"), "not a JSON object"),
        (gzip.compress(b'{"format": 2}'), "format 2 is not 1"),
    ],
    ids=["not_gzip", "not_object", "format"],
)
def test_an_unusable_bundle_warns_once_and_is_no_index(
    monkeypatch: pytest.MonkeyPatch,
    given: GivenWarnings,
    raw: bytes,
    detail: str,
) -> None:
    ship(monkeypatch, raw)
    assert packaged_index() is None
    assert packaged_index() is None
    assert packaged_problem() == f"invalid: {detail}"
    assert given.lines() == (f"WARNING: spdx-bundle.json.gz: invalid: {detail}\n")


def test_threads_load_the_bundle_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first calls race; one load wins and every thread gets its index."""
    started = threading.Barrier(8)

    def slow_bundle() -> bytes:
        time.sleep(0.05)  # widen the window a second load would need
        return RAW

    fake = mock.create_autospec(_REAL_BUNDLE, side_effect=slow_bundle)
    monkeypatch.setattr(spdxdata, "packaged_bundle", fake)
    listindex.reset_packaged_index()
    got: list[ListIndex | None] = []

    def load() -> None:
        started.wait()
        got.append(packaged_index())

    threads = [threading.Thread(target=load) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert fake.call_count == 1
    assert len(got) == 8 and got[0] is not None
    assert all(index is got[0] for index in got)


_WORDS = [
    "permission",
    "is",
    "hereby",
    "granted",
    "free",
    "of",
    "charge",
    "to",
    "any",
    "person",
    "obtaining",
    "a",
    "copy",
    "of",
    "this",
    "software",
    "and",
    "associated",
    "documentation",
    "files",
    "to",
    "deal",
    "in",
    "it",
]


def _sized_bundle() -> bytes:
    """The List of the fixtures with a text of about 6.8 kB per licence:
    about 5 MB in all, as the texts of 3.29.0 are. Generated, distinct per
    licence, so the gzip and JSON reads cost what the real ones do."""
    data = fixture_data()
    texts = {
        lic["licenseId"]: " ".join(
            f"{_WORDS[(number + i) % len(_WORDS)]}{i % 97}" for i in range(850)
        )
        for number, lic in enumerate(data.licenses)
    }
    return to_bundle(dataclasses.replace(data, texts=texts))


def test_the_first_load_is_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bundle of the size of 3.29.0's (740 licences, 86 exceptions, about
    5 MB of text): the real one loads in about 0.05 s; the budget is 0.5 s,
    ten times over for CI's Python 3.10."""
    raw = _sized_bundle()
    assert len(gzip.decompress(raw)) > 4_500_000
    ship(monkeypatch, raw)
    start = time.monotonic()
    index = packaged_index()
    elapsed = time.monotonic() - start
    assert index is not None and index.get_license_details("MIT")
    assert elapsed < slack(0.5), elapsed

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``docs/lists.md`` is generated from the lists of ``resolve()`` and must
equal what ``python -m tools.lists_page`` writes (roadmap item 55)."""
# pylint: disable=missing-function-docstring

from collections.abc import Callable
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.resolvealias import ALIASES
from licenseid.resolveslash import REFUSED_PAIRS
from licenseid.resolvetitle import TITLES
from licenseid.resolveurl import (
    DUAL_PAGES,
    SCANCODE_NOT_SPDX,
    URL_ALIASES,
    UrlAlias,
)
from licenseid.trovenames import TROVE_NAMES
from tools.lists_page import __main__ as generator
from tools.lists_page import evidence
from tools.lists_page.measure import answer_of, list_owners, project_counts
from tools.lists_page.render import render
from tools.lists_page.rules import RULES

PAGE = Path(__file__).parents[1] / "docs" / "lists.md"


@pytest.fixture(name="generated", scope="module")
def _generated(corpus_db: LicenseDatabase) -> str:
    return render(corpus_db, project_counts(corpus_db))


def test_the_page_is_what_the_generator_writes(generated: str) -> None:
    assert PAGE.read_text(encoding="utf-8") == generated, (
        "docs/lists.md is out of date: run `python -m tools.lists_page`"
    )


def test_a_changed_row_changes_the_page(
    generated: str, corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation check: the page reads the lists, it does not copy them."""
    monkeypatch.setitem(ALIASES, "new bsd", "BSD-2-Clause")
    assert render(corpus_db, project_counts(corpus_db)) != generated


def test_a_row_without_its_source_is_refused(
    corpus_db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(TITLES, "new title", "MIT")
    with pytest.raises(KeyError, match="new title"):
        render(corpus_db, project_counts(corpus_db))


def test_the_check_option_tells_a_stale_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert generator.main(["--check"]) == 0
    stale = tmp_path / "lists.md"
    stale.write_text(PAGE.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
    monkeypatch.setattr(generator, "PAGE", stale)
    assert generator.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err
    assert generator.main([]) == 0  # writes the page again
    assert generator.main(["--check"]) == 0


def test_the_evidence_covers_each_row_and_nothing_else() -> None:
    assert set(evidence.ALIAS_SOURCES) == set(ALIASES)
    assert set(evidence.TITLE_SOURCES) == set(TITLES)
    assert set(evidence.DUAL_SOURCES) == set(DUAL_PAGES)
    assert set(evidence.PAIR_NOTES) == set(REFUSED_PAIRS)
    assert set(evidence.SCANCODE_KEYS) == SCANCODE_NOT_SPDX
    assert set(evidence.URL_SOURCE_NOTES) <= set(URL_ALIASES)
    unread = {name for name, entry in TROVE_NAMES.items() if not entry.ids}
    assert set(evidence.TROVE_REFUSALS) == unread
    assert not set(evidence.TROVE_NOTES) & unread
    assert set(evidence.TROVE_NOTES) <= set(TROVE_NAMES)
    assert set(evidence.URL_PACKAGES) | evidence.LIST_PAGES == set(URL_ALIASES)
    assert not set(evidence.URL_PACKAGES) & evidence.LIST_PAGES


def test_a_row_of_a_table_that_grows_has_a_measured_count(
    corpus_db: LicenseDatabase,
) -> None:
    """The growth rule: an alias or a title is in the sample, a URL has a
    survey count (the four pages that predate the rule are checked against the
    List in the test below)."""
    counts = project_counts(corpus_db)
    assert set(counts["alias"]) == set(ALIASES)
    assert set(counts["title"]) == set(TITLES)
    assert all(count >= 1 for count in evidence.URL_PACKAGES.values())


def _name_of(db: LicenseDatabase, license_id: str) -> str | None:
    row = db.get_license_details(license_id)
    return None if row is None else row["name"]


def _is_variant(db: LicenseDatabase, licence: str, owner: str) -> bool:
    """*owner* is *licence* or a variant of it: an ID that starts with
    ``<licence>-`` and whose List name starts with the licence's name
    (``MPL-2.0-no-copyleft-exception``: ``Mozilla Public License 2.0 (no
    copyleft exception)``). An ID that only shares the prefix is no variant."""
    if owner == licence:
        return True
    name, base = _name_of(db, owner), _name_of(db, licence)
    return (
        owner.startswith(f"{licence}-")
        and name is not None
        and base is not None
        and name.startswith(base)
    )


def _unlisted(
    db: LicenseDatabase, owners_of: Callable[[LicenseDatabase, str], tuple[str, ...]]
) -> list[str]:
    """The members of ``LIST_PAGES`` the List does not give to the alias's
    licence and its variants: no owner, the alias ID not among them, or an
    owner that is no variant of it (:func:`_is_variant`)."""
    bad = []
    for key in sorted(evidence.LIST_PAGES):
        licence = URL_ALIASES[key].license_id
        owners = owners_of(db, key)
        variants = all(_is_variant(db, licence, owner) for owner in owners)
        if licence not in owners or not variants:
            bad.append(key)
    return bad


def test_a_url_alias_has_a_count_or_is_a_list_page_of_its_variants(
    corpus_db: LicenseDatabase,
) -> None:
    """A row of ``URL_ALIASES`` has a survey count, or is one of the pages the
    List gives its licence and the variants of it (MPL-2.0 and
    ``MPL-2.0-no-copyleft-exception``). A page that names unrelated licences
    is no such page: the owners are checked, not merely listed."""
    assert evidence.LIST_PAGES
    assert not _unlisted(corpus_db, list_owners)


@pytest.mark.parametrize(
    ("key", "wrong"),
    [
        ("mozilla.org/mpl/2.0", "MPL-1.1"),
        ("mozilla.org/mpl/2.0", "MIT"),
        ("opensource.org/license/ofl-1-1", "OFL-1.1-RFN"),
    ],
    ids=["no-owner", "not-an-owner", "variant-not-licence"],
)
def test_a_list_page_naming_another_licence_is_caught(
    corpus_db: LicenseDatabase,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    wrong: str,
) -> None:
    """Mutation check of the test above: an alias ID that the List does not
    give the page to, or one that is only a variant of the page's licence."""
    monkeypatch.setitem(URL_ALIASES, key, UrlAlias(wrong, "https://example.org/x"))
    assert _unlisted(corpus_db, list_owners) == [key]


def test_a_list_page_that_names_an_unrelated_licence_is_caught(
    corpus_db: LicenseDatabase,
) -> None:
    """A page the List gives to the licence and an unrelated one is no page of
    its variants: the evidence would not be the licence's."""

    def owners_of(_db: LicenseDatabase, key: str) -> tuple[str, ...]:
        return ("MPL-2.0", "MIT") if key == "mozilla.org/mpl/2.0" else ("OFL-1.1",)

    assert "mozilla.org/mpl/2.0" in _unlisted(corpus_db, owners_of)


def test_an_id_that_only_shares_the_prefix_is_no_variant(
    corpus_db: LicenseDatabase,
) -> None:
    """``MPL-2.0-evil`` has no row, and ``MPL-2.0-no-copyleft-exception`` is a
    variant by its name: the prefix alone proves nothing."""
    assert _is_variant(corpus_db, "MPL-2.0", "MPL-2.0-no-copyleft-exception")
    assert not _is_variant(corpus_db, "MPL-2.0", "MPL-2.0-evil")
    assert not _is_variant(corpus_db, "MPL-2.0", "MPL-1.1")
    assert not _is_variant(corpus_db, "MIT", "MIT-0")


def test_the_page_shows_what_the_list_gives_each_url_page(
    generated: str, corpus_db: LicenseDatabase
) -> None:
    assert "The List gives the page to" in generated
    key = "mozilla.org/mpl/2.0"
    row = next(x for x in generated.splitlines() if x.startswith(f"| `{key}`"))
    owners = list_owners(corpus_db, key)
    assert owners
    assert row.endswith("| " + ", ".join(f"`{o}`" for o in owners) + " |")


#: What the rules decide, written here apart from the page: the example, its
#: category and whether it is exact. A change fails this test, not only the page.
DECIDED = {
    "License :: OSI Approved :: MIT License": ("listed_name", True),
    "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": (
        "trove_name",
        True,
    ),
    "GNU General Public License v3 or later (GPLv3+)": ("trove_name", True),
    "MIT License (MIT)": ("listed_name", True),
    "Apache-2.0 (Apache2)": ("lexical", True),
    "Apache2 (Apache-2.0)": ("version_spelling", False),
    "BSD 3-Clause License": ("prose_form", False),
    "Apache License, Version 2.0": ("prose_form", False),
    "The MIT License": ("prose_form", False),
    "New BSD License": ("alias_name", True),
    "The New BSD License": ("alias_name", True),
}


def test_the_rules_give_what_the_maintainer_decided(
    corpus_db: LicenseDatabase,
) -> None:
    assert {rule.example for rule in RULES} == set(DECIDED)
    for rule in RULES:
        got = answer_of(corpus_db, rule.example)
        assert (got.category, got.exact) == DECIDED[rule.example], rule.example


def test_each_rule_is_linked_to_its_code_on_the_page(generated: str) -> None:
    for rule in RULES:
        assert f"`{rule.code.__module__}.{rule.code.__qualname__}`" in generated


def test_the_page_is_plain_markdown_within_80_columns() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert text.startswith("---\n# Generated from the code by")
    assert text.endswith("\n") and not text.endswith("\n\n")
    for number, line in enumerate(text.splitlines(), 1):
        assert line == line.rstrip(), number
        assert len(line) <= 80 or line.startswith("|"), number

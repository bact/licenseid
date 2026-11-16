# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``docs/lists.md`` is generated from the lists of ``resolve()`` and must
equal what ``python -m tools.lists_page`` writes (roadmap item 55)."""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.resolvealias import ALIASES
from licenseid.resolveslash import REFUSED_PAIRS
from licenseid.resolvetitle import TITLES
from licenseid.resolveurl import DUAL_PAGES, URL_ALIASES
from tools.lists_page import __main__ as generator
from tools.lists_page import evidence
from tools.lists_page.measure import answer_of, project_counts
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
    assert set(evidence.URL_PACKAGES) | evidence.UNMEASURED_URLS == set(URL_ALIASES)
    assert not set(evidence.URL_PACKAGES) & evidence.UNMEASURED_URLS


def test_a_row_of_a_table_that_grows_has_a_measured_count(
    corpus_db: LicenseDatabase,
) -> None:
    """The growth rule: an alias or a title is in the sample, a URL has a
    survey count (the four pages that predate the rule are named)."""
    counts = project_counts(corpus_db)
    assert set(counts["alias"]) == set(ALIASES)
    assert set(counts["title"]) == set(TITLES)
    assert all(count >= 1 for count in evidence.URL_PACKAGES.values())


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
    "Apache2 (Apache-2.0)": ("version_spelling", False),
    "BSD 3-Clause License": ("prose_form", False),
    "Apache License, Version 2.0": ("prose_form", False),
    "The MIT License": ("prose_form", False),
    "New BSD License": ("alias_name", True),
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

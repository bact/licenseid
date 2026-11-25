# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The user docs say nothing that goes stale unseen: a line number or a
release only on a page pinned to a release, a time-bound sentence only as
read for this version, and the version of licenseid the same everywhere
(roadmap item 57). A bump of ``__version__`` fails here until the release
preparation has reread and raised what this file lists."""
# pylint: disable=missing-function-docstring

import json
import re
from pathlib import Path

import pytest
from docs_blocks import DOCS, README, ROOT, name_of, pages, prose_lines, text_of

import licenseid

#: The pages that describe one release, as their intro says; a line number
#: or a release named on them is that release's.
PINNED = {
    "docs/expression-canonicalisation.md": "It describes release 0.9.0.",
    "docs/resolve-flow.md": "It describes release 0.9.0.",
}
#: A sentence true only for a time, and the version of licenseid it was last
#: read for: ``(page, words of its line): version``. A bump of the version
#: fails until each is reread (still true: raise its version; else reword).
TIME_BOUND = {
    # py-spdx-license 0.0.1 is the only release on PyPI (2026-11-26).
    ("docs/installation.md", "py-spdx-license/pull/5"): "0.9.2",
    ("docs/installation.md", "but no release holds it yet"): "0.9.2",
}
_LINE_NUMBER = re.compile(r"\b\w+\.py:\d+|#L\d+\b")
_PINNED_LINK = re.compile(r"/blob/[0-9a-f]{40}/[^)\s]*#L\d+")
_RELEASE = re.compile(r"(?i)\b(?:release|before|since) 0\.\d+")
_TIME = re.compile(
    r"(?i)\b(?:yet|for now|waiting|not released|temporar\w*|currently)\b"
    r"|github\.com/[^/\s]+/[^/\s]+/(?:pull|issues)/\d+"
)
#: How the docs write the version of licenseid itself (not that of a List).
_OWN_VERSION = (
    re.compile(r"pkg:pypi/licenseid@([\w.]+)"),
    re.compile(r"bact/licenseid/releases/tag/v([\w.]+)"),
    re.compile(r'"name": "licenseid",\s*"version": "([^"]+)"'),
)


def _hits(pattern: re.Pattern[str], unpinned: bool = True) -> list[str]:
    return [
        f"{name_of(page)}:{number}: {line.strip()}"
        for page in pages()
        if not (unpinned and name_of(page) in PINNED)
        for number, line in prose_lines(text_of(page))
        if pattern.search(line)
    ]


def test_a_line_number_is_only_on_a_pinned_page() -> None:
    hits = _hits(_LINE_NUMBER)
    assert not hits, f"line number outside a pinned page (link the function): {hits}"


@pytest.mark.parametrize("page", sorted(PINNED))
def test_a_pinned_page_says_its_release_and_pins_its_line_links(page: str) -> None:
    text = text_of(ROOT / page)
    assert PINNED[page] in " ".join(text.split()), f"{page}: no {PINNED[page]!r}"
    links = re.findall(r"https://github\.com/\S+#L\d+", text)
    loose = [link for link in links if not _PINNED_LINK.search(link)]
    assert links and not loose, f"{page}: a line link not at a commit: {loose}"


def test_a_release_is_named_only_on_a_pinned_page() -> None:
    hits = _hits(_RELEASE)
    assert not hits, f"a release named outside a pinned page: {hits}"


def test_each_time_bound_sentence_is_registered() -> None:
    unknown = [
        hit
        for hit in _hits(_TIME, unpinned=False)
        if not any(
            hit.startswith(f"{page}:") and words in hit for page, words in TIME_BOUND
        )
    ]
    assert not unknown, f"time-bound: add to TIME_BOUND or reword: {unknown}"


@pytest.mark.parametrize(("page", "words"), sorted(TIME_BOUND))
def test_each_time_bound_sentence_was_read_for_this_version(
    page: str, words: str
) -> None:
    assert words in text_of(ROOT / page), f"{page}: {words!r} is gone: drop the entry"
    read = TIME_BOUND[(page, words)]
    assert read == licenseid.__version__, (
        f"{page}: {words!r} last read at {read}; reread it for"
        f" {licenseid.__version__} and raise its version in TIME_BOUND"
    )


def _changelog_release() -> tuple[str, str]:
    """The version and date of the first released section of CHANGELOG.md."""
    text = text_of(ROOT / "CHANGELOG.md")
    found = re.search(r"^## \[(\d[^\]]*)\] - (\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    assert found, "CHANGELOG.md: no released section"
    return found.group(1), found.group(2)


def test_the_version_is_the_same_everywhere() -> None:
    version = licenseid.__version__
    meta = json.loads(text_of(ROOT / "codemeta.json"))
    readme = text_of(README)
    assert meta["version"] == version, f"codemeta.json {meta['version']}, {version}"
    assert f"(Version {version})" in readme, f"README.md Citation is not {version}"
    assert f"version = {{{version}}}" in readme, f"README.md BibTeX is not {version}"
    if ".dev" in version:
        return
    released, date = _changelog_release()
    assert released == version, f"CHANGELOG.md first release {released}, {version}"
    assert meta["dateModified"] == date, f"codemeta.json dateModified is not {date}"


def _own_versions(page: Path) -> list[str]:
    text = text_of(page)
    return [v for pattern in _OWN_VERSION for v in pattern.findall(text)]


@pytest.mark.parametrize(
    "page",
    [p for p in sorted(DOCS.glob("*.md")) if name_of(p) not in PINNED],
    ids=name_of,
)
def test_the_docs_show_this_version_of_licenseid(page: Path) -> None:
    stale = [v for v in _own_versions(page) if v != licenseid.__version__]
    assert not stale, (
        f"{name_of(page)}: licenseid {stale}, not {licenseid.__version__}:"
        " bump it in the release preparation"
    )


def test_the_version_reader_finds_the_versions_of_resolve_md() -> None:
    """Guard: resolve.md writes the version four times (the resolver's
    ``version``, ``url`` and ``purl`` in its JSON, the ``purl`` in its table)."""
    assert len(_own_versions(DOCS / "resolve.md")) == 4

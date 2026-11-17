# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the lists of ``resolve()`` do not record: the source of a row and
the packages that declare it.

Every key is a key of the list it sits beside; ``tests/test_lists_page.py``
fails on a key the list lacks. A row of ``ALIASES``, ``TITLES`` and
``URL_ALIASES`` is added only with a count (the growth rule). The four URL
pages of :data:`LIST_PAGES` predate it: their evidence is the List, which
the test reads (``measure.list_owners``), not a count typed here.

``*_SOURCES`` are Markdown. What can be measured is not typed here:
``measure`` counts the PyPI projects that each row of ``ALIASES``,
``TITLES`` and ``TROVE_NAMES`` reads from the committed sample of October
2026 (10,000 projects by downloads; ``tests/fixtures/pypi_values_2026-10.tsv``).
``URL_PACKAGES`` are packages of a survey of 2026-11-07 (issue #14: Maven
Central top 1,000 by dependants, NuGet, npm, PyPI and crates.io top 300 by
downloads), whose raw data is not committed: the one typed count."""

from typing import Final

_OSI = "https://opensource.org/license/"
_LIST = "https://spdx.org/licenses/"

#: ``resolvealias.ALIASES``: where the words of each name come from.
ALIAS_SOURCES: Final[dict[str, str]] = {
    "2-clause bsd": f"OSI title, [BSD-2-Clause]({_OSI}bsd-2-clause)",
    "3-clause bsd": f"OSI title, [BSD-3-Clause]({_OSI}bsd-3-clause)",
    "bsd (3 clause)": "the clause count of the ID, in brackets",
    "bsd (3-clause)": "the clause count of the ID, in brackets",
    "bsd 3": "the ID, `Clause` left out",
    "bsd-3": "the ID, `Clause` left out",
    "bsd3": "the ID, `Clause` left out",
    "modified bsd": f"OSI, [BSD-3-Clause]({_OSI}bsd-3-clause) (not the List)",
    "new bsd": f"the [List]({_LIST}BSD-3-Clause.html) and the "
    f"[OSI]({_OSI}bsd-3-clause)",
    "revised bsd": f"the [List]({_LIST}BSD-3-Clause.html)",
    "simplified bsd": f"the [List]({_LIST}BSD-2-Clause.html) and the "
    f"[OSI]({_OSI}bsd-2-clause)",
    "two-clause bsd": "OSI title, the number spelt out",
}

#: ``resolvetitle.TITLES``: the licence text that writes the title.
TITLE_SOURCES: Final[dict[str, str]] = {
    "cc0": f"text of [CC0-1.0]({_LIST}CC0-1.0.html), which calls itself "
    "`CC0` apart from its version",
    "cc0 1.0 universal": f"text of [CC0-1.0]({_LIST}CC0-1.0.html)",
    "gnu general public license version 3, 29 june 2007": (
        f"title line of the text of [GPL-3.0-only]({_LIST}GPL-3.0-only.html)"
    ),
    "mulan psl v2": (
        f"short name in the text of [MulanPSL-2.0]({_LIST}MulanPSL-2.0.html)"
    ),
}

#: Packages of the 2026-11-07 survey that declare each page of
#: ``resolveurl.URL_ALIASES`` (Maven, NuGet and the PyPI sample together).
URL_PACKAGES: Final[dict[str, int]] = {
    "aws.amazon.com/apache2.0": 5,
    "eclipse.org/org/documents/epl-2.0/epl-2.0": 5,
    "eclipse.org/org/documents/epl-v10": 5,
    "openjdk.java.net/legal/gplv2+ce": 6,
    "opensource.org/license/cpl1-0": 3,
    "opensource.org/license/mit-license": 17,
    "repository.jboss.org/licenses/apache-2.0": 9,
}

#: The pages of ``URL_ALIASES`` with no recorded count: pages the List gives
#: a licence and its variants (the alias ID and the IDs that start with
#: ``<ID>-``), kept before the growth rule. A fifth row needs a count in
#: :data:`URL_PACKAGES`: ``tests/test_lists_page.py`` checks each member
#: against the List's owners, so this set cannot name a page the List does not
#: give to the alias's licence and its variants.
LIST_PAGES: Final = frozenset(
    {
        "mozilla.org/mpl/2.0",
        "opensource.org/license/mpl-2-0",
        "opensource.org/license/ofl-1-1",
        "scripts.sil.org/cms/scripts/page?item_id=ofl_web",
    }
)

#: ``resolveurl.DUAL_PAGES``: why the page offers a choice.
DUAL_SOURCES: Final[dict[str, str]] = {
    "glassfish.java.net/public/cddl+gpl_1_1": (
        "the GlassFish licence page `CDDL+GPL_1_1`; the List gives it to CDDL-1.1"
    ),
    "javaee.github.io/glassfish/license": (
        "the GlassFish `LICENSE` on javaee.github.io; the List gives it to CDDL-1.1"
    ),
}

#: ``resolveslash.REFUSED_PAIRS``: why the two IDs are one licence.
PAIR_NOTES: Final[dict[tuple[str, str], str]] = {
    ("libpng", "zlib"): 'OSI\'s name of Zlib is "the zlib/libpng license"',
    ("mit", "x11"): "Debian's name of the one X11 licence, not two",
}

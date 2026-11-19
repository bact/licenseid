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
2026 (``tests/fixtures/pypi_values_2026-10.tsv``) and its size.
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
    ("mit", "x11"): (
        f"[X11]({_LIST}X11.html) is MIT plus a clause on the X Consortium's "
        "name: `MIT OR X11` would offer a licence the value may not mean"
    ),
}

#: ``trovenames.TROVE_NAMES``, the names read as no licence: why, as the
#: comment in the module gives it.
_NO_VERSION = "no version"
TROVE_REFUSALS: Final[dict[str, str]] = {
    "Academic Free License (AFL)": f"{_NO_VERSION}: `AFL-1.1` to `AFL-3.0`",
    "Apache Software License": f"{_NO_VERSION}: `Apache-2.0` by usage only",
    "Apple Public Source License": f"{_NO_VERSION}: `APSL-1.0` to `APSL-2.0`",
    "Artistic License": f"{_NO_VERSION}: `Artistic-1.0` and `Artistic-2.0`",
    "BSD License": "a family",
    "Common Public License": f"{_NO_VERSION}, though `CPL-1.0` is the only one",
    "DFSG approved": "a category",
    "Eiffel Forum License": f"{_NO_VERSION}: `EFL-1.0` and `EFL-2.0`",
    "Eiffel Forum License (EFL)": f"{_NO_VERSION}: `EFL-1.0` and `EFL-2.0`",
    "Free For Educational Use": "no SPDX ID",
    "Free For Home Use": "no SPDX ID",
    "Free To Use But Restricted": "no SPDX ID",
    "Free for non-commercial use": "no SPDX ID",
    "Freely Distributable": "no SPDX ID",
    "Freeware": "no SPDX ID",
    "GNU Free Documentation License (FDL)": _NO_VERSION,
    "GNU General Public License (GPL)": _NO_VERSION,
    "GNU Library or Lesser General Public License (LGPL)": (
        "reads two ways: the Library or the Lesser GPL"
    ),
    "GUST Font License 1.0": "not in the List",
    "GUST Font License 2006-09-30": "not in the List",
    "IBM Public License": f"{_NO_VERSION}, though `IPL-1.0` is the only one",
    "Jabber Open Source License": "not in the List",
    "MITRE Collaborative Virtual Workspace License (CVW)": "not in the List",
    "Netscape Public License (NPL)": f"{_NO_VERSION}: `NPL-1.0` and `NPL-1.1`",
    "OSI Approved": "a category",
    "Other/Proprietary License": "no SPDX ID",
    "Public Domain": "no SPDX ID",
    "Python License (CNRI Python License)": (
        "reads two ways: `Python-2.0` by the head, `CNRI-Python` by the brackets"
    ),
    "Python Software Foundation License": f"{_NO_VERSION}: `PSF-2.0` by usage only",
    "Qt Public License (QPL)": f"{_NO_VERSION}; the List names it Q Public",
    "Repoze Public License": "not in the List",
    "Sun Public License": f"{_NO_VERSION}, though `SPL-1.0` is the only one",
    "W3C License": f"{_NO_VERSION}: `W3C`, `W3C-19980720`, `W3C-20150513`",
    "Zope Public License": f"{_NO_VERSION}: `ZPL-1.1` to `ZPL-2.1`",
    "zlib/libpng License": "reads two ways: `Zlib` or `zlib-acknowledgement`",
}

#: ``trovenames.TROVE_NAMES``: a read name whose reading needs a word.
TROVE_NOTES: Final[dict[str, str]] = {
    "GNU Lesser General Public License v2 (LGPLv2)": (
        "no Lesser GPL v2 exists (Lesser starts at 2.1); read as written"
    ),
    "GNU Lesser General Public License v2 or later (LGPLv2+)": (
        "no Lesser GPL v2 exists (Lesser starts at 2.1); read as written"
    ),
    "Sun Industry Standards Source License (SISSL)": (
        "no version, and the List has `SISSL` and `SISSL-1.2`: read by the ID "
        "in brackets, the maintainer's exception to the rule for no version"
    ),
    "Universal Permissive License (UPL)": (
        "no version; `UPL-1.0` is the only one, the maintainer's exception to "
        "the rule that keeps `CPL`, `IPL` and `SPL` unread"
    ),
}

#: ``resolveurl.SCANCODE_NOT_SPDX``: ScanCode's own SPDX key for each key
#: (its ``index.json`` of 2026-11-08; empty for none) and how its licence
#: compares with the SPDX ID the key spells (texts compared on 2026-11-19).
SCANCODE_KEYS: Final[dict[str, tuple[str, str]]] = {
    "brian-gladman-3-clause": (
        "LicenseRef-scancode-brian-gladman-3-clause",
        "the same licence",
    ),
    "bsd-2-clause-freebsd": ("", "a key ScanCode deprecated"),
    "bsd-2-clause-netbsd": ("", "a key ScanCode deprecated"),
    "bsl-1.0": ("LicenseRef-scancode-bsl-1.0", "another licence"),
    "intel": ("LicenseRef-scancode-intel", "another licence"),
    "libtool-exception": ("", "a key ScanCode deprecated"),
    "mvt-1.1": ("LicenseRef-scancode-mvt-1.1", "the same licence"),
    "net-snmp": ("LicenseRef-scancode-net-snmp", "the same licence"),
    "nokia-qt-exception-1.1": ("", "a key ScanCode deprecated"),
    "openssl": ("OpenSSL-standalone", "another licence"),
    "opl-1.0": ("LicenseRef-scancode-opl-1.0", "another licence"),
    "tpl-1.0": ("LicenseRef-scancode-tpl-1.0", "another licence"),
    "x11": ("ICU", "another licence"),
}

#: ``resolveurl.URL_ALIASES``: a word on a source page that changed.
URL_SOURCE_NOTES: Final[dict[str, str]] = {
    "scripts.sil.org/cms/scripts/page?item_id=ofl_web": (
        "now a redirect to a landing page without the text: the row rests on "
        "the List's `seeAlso`"
    ),
}

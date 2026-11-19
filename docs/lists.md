---
# Generated from the code by `python -m tools.lists_page`: never edit by hand.
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The lists that `resolve()` reads

This page is generated from the code by `python -m tools.lists_page`. Do not
edit it by hand: `tests/test_lists_page.py` fails when the page and the code
differ. To change a row, change the list in `src/licenseid/` and run the
command again.

`resolve()` reads a declared licence value (a `License` field, a classifier,
a URL) as an SPDX expression. Besides the SPDX License List it reads the
lists on this page, which licenseid keeps. Each is decided once, as data: a
value is read only if a list holds it, never by a looser match. A table names
the object it comes from by its import path, and each row by its key in that
object.

Each list gives one `category` (see [the table of
categories](resolve.md#steps-and-categories)) and so one `EXACT` value. `EXACT`
is yes when an authoritative list defines the reading: the SPDX License List or
a list below, also through a change of case alone (`zlib` is `Zlib`, `lexical`).
These are the categories of `licenseid.resolvefirst.EXACT_CATEGORIES`:
`alias_name`, `assumed_only`, `deprecated_ambiguous`,
`deprecated_equal_successor`, `exact`, `lexical`, `license_url`, `listed_name`,
`plus_to_or_later`, `stated_qualifier`, `text_title`, `trove_name`. Any other is
no: a rewrite rule made the reading (`prose_form`, `version_spelling`, a
`separator` that re-spells, as `BSD 3 Clause`). A compound is exact when every
operand is, so IDs joined by a slash are (`MIT/Apache-2.0`, category
`separator`). A value cut to be read (`"MIT`) is not.

A row is added only with a measured count of the packages that declare it.
The counts of the PyPI tables are projects of a sample of October 2026
(`tests/fixtures/pypi_values_2026-10.tsv`), counted by the generator: the
9,353 of the 10,000 most downloaded PyPI projects that declare
one short value. The rest declare none, only a licence text or several
classifiers, so a count understates use. The counts of the URL table are
packages of a survey of 2026-11-07 (issue #14: the 1,000 Maven Central
packages with most dependants and the 300 most downloaded NuGet, npm, PyPI and
crates.io packages). A URL page with no count
is one the List gives to a licence and its variants, and that is its
evidence. A dash is no count recorded.

## The lists at a glance

| Object | Category | `EXACT` | Rows | Holds |
| --- | --- | --- | --- | --- |
| `licenseid.resolvealias.ALIASES` | `alias_name` | yes | 12 | BSD names |
| `licenseid.resolvetitle.TITLES` | `text_title` | yes | 4 | titles of licence texts |
| `licenseid.trovenames.TROVE_NAMES` | `trove_name` | yes | 89 | classifier names |
| `licenseid.resolveurl.URL_ALIASES` | `license_url`, or the ID's | see the examples | 11 | pages read as a licence |
| `licenseid.resolveurl.ID_PAGES` | `license_url`, or the ID's | see the examples | 4 | hosts with an ID in the path |
| `licenseid.resolveurl.DUAL_PAGES` | `unresolved` | — | 2 | pages refused: a choice |
| `licenseid.resolveurl.SCANCODE_NOT_SPDX` | `unresolved` | — | 13 | ScanCode keys not read |
| `licenseid.resolveslash.REFUSED_PAIRS` | `unresolved` | — | 2 | pairs refused in a slash |
| `licenseid.resolveprose.VERSIONED_NAMES` | `prose_form` | no | 2 | names with a version |

## Named rules

Some rules are named in the code and the tests: T1 to T3 read a trove
classifier or a name with its abbreviation (`licenseid.resolvetrove`), and P1
to P3 read the prose form of an ID (`licenseid.resolveprose`). Each row names
the function that is the rule. The answer, the category and `EXACT` are what
`resolve()` gives for the example.

A rule that hands a value to a list or to the SPDX List reads as that list
does, so it is exact when the list is. A rule that rewrites a value is no
list: `prose_form` and `version_spelling` are not exact. Besides the SPDX
List, P1 asks `ALIASES` only (`CC0 License` and `Mulan PSL v2 License` are
not read), so a BSD name with `License` is exact where `The MIT License` and
`BSD 3-Clause License` are not.

| Rule | Function | Reads | Example | Answer | Category | `EXACT` | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | `licenseid.trovenames.strip_trove_path` | a trove classifier in its real form, read as the name in it is read alone, with a `trove_path` step | `License :: OSI Approved :: MIT License` | `MIT` | `listed_name` | yes | the category of the name alone |
| T1 | `licenseid.trovenames.strip_trove_path` | the same, for a name only the trove table knows | `License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | `CC0-1.0` | `trove_name` | yes | a name of the trove table |
| T2 | `licenseid.resolvetrove._name` | a name of the trove table that states one licence | `GNU General Public License v3 or later (GPLv3+)` | `GPL-3.0-or-later` | `trove_name` | yes | a bare deprecated ID stays `assumed_only`, also exact |
| T3 | `licenseid.resolvetrove._trailing` | `head (inside)` where head and inside each read alone as one expression, the same | `MIT License (MIT)` | `MIT` | `listed_name` | yes | the head's; the inside need only give the same expression |
| T3 | `licenseid.resolvetrove._trailing` | the same, where only the inside needed a rewrite rule | `Apache-2.0 (Apache2)` | `Apache-2.0` | `lexical` | yes | the head's; the inside need only give the same expression |
| T3 | `licenseid.resolvetrove._trailing` | the same, where the head needed a rewrite rule | `Apache2 (Apache-2.0)` | `Apache-2.0` | `version_spelling` | no | the head's: a rewrite rule is no list |
| P1 | `licenseid.resolveprose._licence_word` | a final `license` or `licence` after a value that reads alone | `BSD 3-Clause License` | `BSD-3-Clause` | `prose_form` | no | a rewrite rule is no list |
| P2 | `licenseid.resolveprose._reductions` | `<name> License[,] (Version\|v) N` as `<name> N`, also with no `License` or with the version in brackets | `Apache License, Version 2.0` | `Apache-2.0` | `prose_form` | no | a rewrite rule is no list |
| P3 | `licenseid.resolveprose._after_article` | a leading `The`, with P1, P2 or a List name | `The MIT License` | `MIT` | `prose_form` | no | a rewrite rule is no list |
| P1 | `licenseid.resolveprose._read_reduction` | a prose form whose reduction is a name of `ALIASES`, the one table P1 asks besides the List | `New BSD License` | `BSD-3-Clause` | `alias_name` | yes | the category of `ALIASES` |
| P3 | `licenseid.resolveprose._after_article` | a leading `The` before such a prose form | `The New BSD License` | `BSD-3-Clause` | `alias_name` | yes | the category of `ALIASES` |

## BSD names

Other names of the two BSD licences. `licenseid.resolvealias.ALIASES`, category
`alias_name`, `EXACT` yes. A name is read in ASCII case folded, with a run of
white space as one space. A final `License` is read first (rule P1).

| Name (folded) | ID | Source | Projects |
| --- | --- | --- | --- |
| `2-clause bsd` | `BSD-2-Clause` | OSI title, [BSD-2-Clause](https://opensource.org/license/bsd-2-clause) | 4 |
| `3-clause bsd` | `BSD-3-Clause` | OSI title, [BSD-3-Clause](https://opensource.org/license/bsd-3-clause) | 3 |
| `bsd (3 clause)` | `BSD-3-Clause` | the clause count of the ID, in brackets | 1 |
| `bsd (3-clause)` | `BSD-3-Clause` | the clause count of the ID, in brackets | 1 |
| `bsd 3` | `BSD-3-Clause` | the ID, `Clause` left out | 3 |
| `bsd-3` | `BSD-3-Clause` | the ID, `Clause` left out | 9 |
| `bsd3` | `BSD-3-Clause` | the ID, `Clause` left out | 2 |
| `modified bsd` | `BSD-3-Clause` | OSI, [BSD-3-Clause](https://opensource.org/license/bsd-3-clause) (not the List) | 3 |
| `new bsd` | `BSD-3-Clause` | the [List](https://spdx.org/licenses/BSD-3-Clause.html) and the [OSI](https://opensource.org/license/bsd-3-clause) | 11 |
| `revised bsd` | `BSD-3-Clause` | the [List](https://spdx.org/licenses/BSD-3-Clause.html) | 1 |
| `simplified bsd` | `BSD-2-Clause` | the [List](https://spdx.org/licenses/BSD-2-Clause.html) and the [OSI](https://opensource.org/license/bsd-2-clause) | 2 |
| `two-clause bsd` | `BSD-2-Clause` | OSI title, the number spelt out | 1 |

## Titles of licence texts

The title a licence's own text gives itself. `licenseid.resolvetitle.TITLES`,
category `text_title`, `EXACT` yes. A title that writes a version but no grant
is the bare deprecated ID, `assumed_only`.

| Name (folded) | ID | Source | Projects |
| --- | --- | --- | --- |
| `cc0` | `CC0-1.0` | text of [CC0-1.0](https://spdx.org/licenses/CC0-1.0.html), which calls itself `CC0` apart from its version | 3 |
| `cc0 1.0 universal` | `CC0-1.0` | text of [CC0-1.0](https://spdx.org/licenses/CC0-1.0.html) | 8 |
| `gnu general public license version 3, 29 june 2007` | `GPL-3.0` | title line of the text of [GPL-3.0-only](https://spdx.org/licenses/GPL-3.0-only.html) | 1 |
| `mulan psl v2` | `MulanPSL-2.0` | short name in the text of [MulanPSL-2.0](https://spdx.org/licenses/MulanPSL-2.0.html) | 3 |

## Trove classifier names

The `License ::` classifiers of PyPA's `trove-classifiers`,
`licenseid.trovenames.TROVE_NAMES`, category `trove_name`, `EXACT` yes. A name
that is also an ID or a List name is read as that first, so its category is
`listed_name`; a name that states a bare deprecated ID is `assumed_only`. Rule
T1 reads the whole classifier and rule T2 the name alone. The table shows the
classifier as PyPI writes it and what `resolve()` gives for it. Projects counts
the values that are the classifier or its name alone, whatever reads them. A
classifier PyPI has deprecated is marked so.

| Classifier | Answer | Category | `EXACT` | Projects | Note |
| --- | --- | --- | --- | --- | --- |
| `License :: Aladdin Free Public License (AFPL)` | `Aladdin` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Attribution Assurance License` | `AAL` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Blue Oak Model License (BlueOak-1.0.0)` | `BlueOak-1.0.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Boost Software License 1.0 (BSL-1.0)` | `BSL-1.0` | `listed_name` | yes | 1 | |
| `License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | `CC0-1.0` | `trove_name` | yes | 3 | |
| `License :: OSI Approved :: CEA CNRS Inria Logiciel Libre License, version 2.1 (CeCILL-2.1)` | `CECILL-2.1` | `trove_name` | yes | — | |
| `License :: CeCILL-B Free Software License Agreement (CECILL-B)` | `CECILL-B` | `listed_name` | yes | — | |
| `License :: CeCILL-C Free Software License Agreement (CECILL-C)` | `CECILL-C` | `listed_name` | yes | — | |
| `License :: OSI Approved :: CMU License (MIT-CMU)` | `MIT-CMU` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Common Development and Distribution License 1.0 (CDDL-1.0)` | `CDDL-1.0` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Eclipse Public License 1.0 (EPL-1.0)` | `EPL-1.0` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)` | `EPL-2.0` | `listed_name` | yes | 1 | |
| `License :: OSI Approved :: Educational Community License, Version 2.0 (ECL-2.0)` | `ECL-2.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: European Union Public Licence 1.0 (EUPL 1.0)` | `EUPL-1.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)` | `EUPL-1.1` | `trove_name` | yes | — | |
| `License :: OSI Approved :: European Union Public Licence 1.2 (EUPL 1.2)` | `EUPL-1.2` | `trove_name` | yes | — | |
| `License :: OSI Approved :: GNU Affero General Public License v3` | `AGPL-3.0` | `assumed_only` | yes | 10 | |
| `License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)` | `AGPL-3.0-or-later` | `trove_name` | yes | 1 | |
| `License :: OSI Approved :: GNU General Public License v2 (GPLv2)` | `GPL-2.0` | `assumed_only` | yes | 5 | |
| `License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)` | `GPL-2.0-or-later` | `trove_name` | yes | 3 | |
| `License :: OSI Approved :: GNU General Public License v3 (GPLv3)` | `GPL-3.0` | `assumed_only` | yes | 20 | |
| `License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)` | `GPL-3.0-or-later` | `trove_name` | yes | 15 | |
| `License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)` | `LGPL-2.0` | `assumed_only` | yes | 1 | no Lesser GPL v2 exists (Lesser starts at 2.1); read as written |
| `License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)` | `LGPL-2.0-or-later` | `trove_name` | yes | 2 | no Lesser GPL v2 exists (Lesser starts at 2.1); read as written |
| `License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)` | `LGPL-3.0` | `assumed_only` | yes | 6 | |
| `License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)` | `LGPL-3.0-or-later` | `trove_name` | yes | 9 | |
| `License :: OSI Approved :: Historical Permission Notice and Disclaimer (HPND)` | `HPND` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Intel Open Source License` | `Intel` | `listed_name` | yes | — | deprecated by PyPI |
| `License :: OSI Approved :: ISC License (ISCL)` | `ISC` | `trove_name` | yes | 8 | |
| `License :: OSI Approved :: MirOS License (MirOS)` | `MirOS` | `trove_name` | yes | — | |
| `License :: OSI Approved :: MIT License` | `MIT` | `listed_name` | yes | 1,052 | |
| `License :: OSI Approved :: MIT No Attribution License (MIT-0)` | `MIT-0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Motosoto License` | `Motosoto` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Mozilla Public License 1.0 (MPL)` | `MPL-1.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Mozilla Public License 1.1 (MPL 1.1)` | `MPL-1.1` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)` | `MPL-2.0` | `listed_name` | yes | 19 | |
| `License :: OSI Approved :: Mulan Permissive Software License v2 (MulanPSL-2.0)` | `MulanPSL-2.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: NASA Open Source Agreement v1.3 (NASA-1.3)` | `NASA-1.3` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Nethack General Public License` | `NGPL` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Nokia Open Source License` | `Nokia` | `listed_name` | yes | — | |
| `License :: Nokia Open Source License (NOKOS)` | `Nokia` | `trove_name` | yes | — | |
| `License :: OSI Approved :: Open Group Test Suite License` | `OGTSL` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Open Software License 3.0 (OSL-3.0)` | `OSL-3.0` | `listed_name` | yes | — | |
| `License :: OSI Approved :: PostgreSQL License` | `PostgreSQL` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Ricoh Source Code Public License` | `RSCPL` | `listed_name` | yes | — | |
| `License :: OSI Approved :: SIL Open Font License 1.1 (OFL-1.1)` | `OFL-1.1` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Sleepycat License` | `Sleepycat` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Sun Industry Standards Source License (SISSL)` | `SISSL` | `trove_name` | yes | — | no version, and the List has `SISSL` and `SISSL-1.2`: read by the ID in brackets, the maintainer's exception to the rule for no version; deprecated by PyPI |
| `License :: OSI Approved :: The Unlicense (Unlicense)` | `Unlicense` | `listed_name` | yes | 5 | |
| `License :: OSI Approved :: Universal Permissive License (UPL)` | `UPL-1.0` | `trove_name` | yes | 1 | no version; `UPL-1.0` is the only one, the maintainer's exception to the rule that keeps `CPL`, `IPL` and `SPL` unread |
| `License :: OSI Approved :: University of Illinois/NCSA Open Source License` | `NCSA` | `listed_name` | yes | — | |
| `License :: OSI Approved :: Vovida Software License 1.0` | `VSL-1.0` | `trove_name` | yes | — | |
| `License :: OSI Approved :: X.Net License` | `Xnet` | `listed_name` | yes | — | deprecated by PyPI |
| `License :: OSI Approved :: Zero-Clause BSD (0BSD)` | `0BSD` | `trove_name` | yes | — | |

These names state no one licence, and no rule guesses at them:

| Classifier | Why | Projects |
| --- | --- | --- |
| `License :: OSI Approved :: Academic Free License (AFL)` | no version: `AFL-1.1` to `AFL-3.0` | — |
| `License :: OSI Approved :: Apache Software License` | no version: `Apache-2.0` by usage only | 360 |
| `License :: OSI Approved :: Apple Public Source License` | no version: `APSL-1.0` to `APSL-2.0` | — |
| `License :: OSI Approved :: Artistic License` | no version: `Artistic-1.0` and `Artistic-2.0` | 2 |
| `License :: OSI Approved :: BSD License` | a family | 271 |
| `License :: OSI Approved :: Common Public License` | no version, though `CPL-1.0` is the only one | — |
| `License :: DFSG approved` | a category | — |
| `License :: OSI Approved :: Eiffel Forum License` | no version: `EFL-1.0` and `EFL-2.0` | — |
| `License :: Eiffel Forum License (EFL)` | no version: `EFL-1.0` and `EFL-2.0` | — |
| `License :: Free For Educational Use` | no SPDX ID | — |
| `License :: Free For Home Use` | no SPDX ID | — |
| `License :: Free for non-commercial use` | no SPDX ID | — |
| `License :: Free To Use But Restricted` | no SPDX ID | 2 |
| `License :: Freely Distributable` | no SPDX ID | — |
| `License :: Freeware` | no SPDX ID | — |
| `License :: OSI Approved :: GNU Free Documentation License (FDL)` | no version | — |
| `License :: OSI Approved :: GNU General Public License (GPL)` | no version | 3 |
| `License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)` | reads two ways: the Library or the Lesser GPL | 7 |
| `License :: GUST Font License 1.0` | not in the List | — |
| `License :: GUST Font License 2006-09-30` | not in the List | — |
| `License :: OSI Approved :: IBM Public License` | no version, though `IPL-1.0` is the only one | — |
| `License :: OSI Approved :: Jabber Open Source License` | not in the List; deprecated by PyPI | — |
| `License :: OSI Approved :: MITRE Collaborative Virtual Workspace License (CVW)` | not in the List; deprecated by PyPI | — |
| `License :: Netscape Public License (NPL)` | no version: `NPL-1.0` and `NPL-1.1` | — |
| `License :: OSI Approved` | a category | — |
| `License :: Other/Proprietary License` | no SPDX ID | 22 |
| `License :: Public Domain` | no SPDX ID | 14 |
| `License :: OSI Approved :: Python License (CNRI Python License)` | reads two ways: `Python-2.0` by the head, `CNRI-Python` by the brackets | — |
| `License :: OSI Approved :: Python Software Foundation License` | no version: `PSF-2.0` by usage only | 21 |
| `License :: OSI Approved :: Qt Public License (QPL)` | no version; the List names it Q Public | — |
| `License :: Repoze Public License` | not in the List | — |
| `License :: OSI Approved :: Sun Public License` | no version, though `SPL-1.0` is the only one | — |
| `License :: OSI Approved :: W3C License` | no version: `W3C`, `W3C-19980720`, `W3C-20150513` | 1 |
| `License :: OSI Approved :: zlib/libpng License` | reads two ways: `Zlib` or `zlib-acknowledgement` | 1 |
| `License :: OSI Approved :: Zope Public License` | no version: `ZPL-1.1` to `ZPL-2.1` | — |

## Licence URLs

A URL is read as the licence it names through the step `license_url`. Its
category is `license_url`, or that of a deprecated ID it reads, as for the ID
alone (`assumed_only`, `deprecated_ambiguous`). It is compared by its key
(`licenseid.urlkey.url_key`): ASCII case is folded, and the scheme, `www.`, a
fragment, a trailing `/` and one page suffix such as `.html` are dropped. A
key can so name a page that does not exist (`licenses.nuget.org/mit`). The
reader tries four things in this order; a refusal claims the value, so no
later reader guesses at it. `EXACT` is `detect()`'s: a variant the value as
written does not state is not exact, and `%2B` is no "+" as written.

| URL | Answer | Category | Detail | `EXACT` |
| --- | --- | --- | --- | --- |
| `https://spdx.org/licenses/MIT.html` | `MIT` | `license_url` | `list page` | yes |
| `https://spdx.org/licenses/GPL-2.0.html` | `GPL-2.0` | `assumed_only` | `list page` | yes |
| `https://spdx.org/licenses/MIT+` | `MIT+` | `license_url` | `list page` | yes |
| `https://spdx.org/licenses/preview/MIT` | none | `unresolved` | — | — |
| `https://licenses.nuget.org/mit` | `MIT` | `license_url` | `id in path` | yes |
| `https://licenses.nuget.org/MS-PL%20OR%20Apache-2.0` | `Apache-2.0 OR MS-PL` | `license_url` | `expression in path` | yes |
| `https://licenses.nuget.org/GPL-2.0%2B` | `GPL-2.0-or-later` | `license_url` | `expression in path` | no |
| `https://openjdk.java.net/legal/gplv2+ce` | `GPL-2.0-with-classpath-exception` | `deprecated_ambiguous` | `alias` | yes |

### Pages whose path holds an ID

`licenseid.resolveurl.ID_PAGES`. The rest of the key after one of these must
be one segment (no `/` or `?`), read as an ID. On the List's own pages `<ID>+`
is read too; on NuGet's the segment may be a whole expression, URL-encoded,
with the detail `expression in path`. A page of an exception is refused, and a
ScanCode key listed below is not read.

| Key starts with | Detail of the step |
| --- | --- |
| `spdx.org/licenses/` | `list page` |
| `licenses.nuget.org/` | `id in path` |
| `choosealicense.com/licenses/` | `id in path` |
| `scancode-licensedb.aboutcode.org/` | `id in path` |

### Pages refused, for a choice of licences

`licenseid.resolveurl.DUAL_PAGES`. The List gives each page one licence, but the
page offers a choice: the value is refused with `url names several licences`.

| Key | Offers | Source |
| --- | --- | --- |
| `glassfish.java.net/public/cddl+gpl_1_1` | `CDDL-1.1, GPL-2.0-with-classpath-exception` | the GlassFish licence page `CDDL+GPL_1_1`; the List gives it to CDDL-1.1 |
| `javaee.github.io/glassfish/license` | `CDDL-1.1, GPL-2.0-with-classpath-exception` | the GlassFish `LICENSE` on javaee.github.io; the List gives it to CDDL-1.1 |

### ScanCode keys not read as the ID they spell

`licenseid.resolveurl.SCANCODE_NOT_SPDX`. Each key folds to an SPDX ID, but
ScanCode's own SPDX key for it differs: it names another licence, gives the
same licence only a `LicenseRef-scancode-` key, or is deprecated with none.
The page does not state the ID its key spells, so it is not read. No package
of the survey declares a ScanCode URL, so the rule rests on the format.

| Key | ScanCode's SPDX key | Group |
| --- | --- | --- |
| `brian-gladman-3-clause` | `LicenseRef-scancode-brian-gladman-3-clause` | the same licence |
| `bsd-2-clause-freebsd` | none | a key ScanCode deprecated |
| `bsd-2-clause-netbsd` | none | a key ScanCode deprecated |
| `bsl-1.0` | `LicenseRef-scancode-bsl-1.0` | another licence |
| `intel` | `LicenseRef-scancode-intel` | another licence |
| `libtool-exception` | none | a key ScanCode deprecated |
| `mvt-1.1` | `LicenseRef-scancode-mvt-1.1` | the same licence |
| `net-snmp` | `LicenseRef-scancode-net-snmp` | the same licence |
| `nokia-qt-exception-1.1` | none | a key ScanCode deprecated |
| `openssl` | `OpenSSL-standalone` | another licence |
| `opl-1.0` | `LicenseRef-scancode-opl-1.0` | another licence |
| `tpl-1.0` | `LicenseRef-scancode-tpl-1.0` | another licence |
| `x11` | `ICU` | another licence |

### Pages read as one licence

`licenseid.resolveurl.URL_ALIASES`, detail `alias`. A page the List lacks, or
gives a licence and its variants, reviewed by hand. The source is the page that
shows the licence. A page the List gives to the licence and its variants is read
as the licence, and its evidence is the List: the column of the List names the
IDs it gives the page to. Any other row needs a count of packages.

| Key | ID | Source | Packages | The List gives the page to |
| --- | --- | --- | --- | --- |
| `aws.amazon.com/apache2.0` | `Apache-2.0` | <https://aws.amazon.com/apache-2-0/> | 5 | none |
| `eclipse.org/org/documents/epl-2.0/epl-2.0` | `EPL-2.0` | <https://www.eclipse.org/org/documents/epl-2.0/EPL-2.0.txt> | 5 | none |
| `eclipse.org/org/documents/epl-v10` | `EPL-1.0` | <https://www.eclipse.org/org/documents/epl-1.0/> | 5 | none |
| `mozilla.org/mpl/2.0` | `MPL-2.0` | <https://www.mozilla.org/MPL/2.0/> | — | `MPL-2.0`, `MPL-2.0-no-copyleft-exception` |
| `openjdk.java.net/legal/gplv2+ce` | `GPL-2.0-with-classpath-exception` | <https://openjdk.org/legal/gplv2+ce.html> | 6 | none |
| `opensource.org/license/cpl1-0` | `CPL-1.0` | <https://opensource.org/license/cpl-1-0> | 3 | none |
| `opensource.org/license/mit-license` | `MIT` | <https://opensource.org/license/mit> | 17 | none |
| `opensource.org/license/mpl-2-0` | `MPL-2.0` | <https://opensource.org/license/MPL-2.0> | — | `MPL-2.0`, `MPL-2.0-no-copyleft-exception` |
| `opensource.org/license/ofl-1-1` | `OFL-1.1` | <https://opensource.org/license/OFL-1.1> | — | `OFL-1.1`, `OFL-1.1-no-RFN`, `OFL-1.1-RFN` |
| `repository.jboss.org/licenses/apache-2.0` | `Apache-2.0` | <https://repository.jboss.org/licenses/apache-2.0.txt> | 9 | none |
| `scripts.sil.org/cms/scripts/page?item_id=ofl_web` | `OFL-1.1` | <https://scripts.sil.org/cms/scripts/page.php?item_id=OFL_web>; now a redirect to a landing page without the text: the row rests on the List's `seeAlso` | — | `OFL-1.1`, `OFL-1.1-no-RFN`, `OFL-1.1-RFN` |

## IDs joined by a slash

`licenseid.resolveslash.REFUSED_PAIRS`. A value with both IDs of a pair, in any
order and place, is refused: the pair is one licence under a name with a slash.
Another pair needs a measured count.

| Pair | Why |
| --- | --- |
| `libpng`, `zlib` | OSI's name of Zlib is "the zlib/libpng license" |
| `mit`, `x11` | [X11](https://spdx.org/licenses/X11.html) is MIT plus a clause on the X Consortium's name: `MIT OR X11` would offer a licence the value may not mean |

## Names with a version in prose

`licenseid.resolveprose.VERSIONED_NAMES`, read by rule P2. A name that states no
version is read with the version after it, as the ID of its prefix; the ID must
be listed.

| Name (folded) | ID prefix |
| --- | --- |
| `academic free` | `AFL` |
| `apache software` | `Apache` |

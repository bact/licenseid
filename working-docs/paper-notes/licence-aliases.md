---
Created: 2026-11-06
Last-Modified: 2026-11-08
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The other names of licences `resolve()` reads, and their sources

`resolve()` reads a declared value as an SPDX ID, a List name, a loose
spelling of an ID (rules, not a list: `looseid.py`), or a name from one of
three tables written by hand (a fourth, the URL aliases, is in
[licence-urls.md](licence-urls.md)). This note lists the three tables, each entry
with its source and the PyPI projects that declare it, so that each can be
cited. Nothing in them is generated from the SPDX data.

| Table | Category, step | File | Entries | Since |
| --- | --- | --- | --- | --- |
| BSD aliases | `alias_name` | `src/licenseid/resolvealias.py` (`ALIASES`) | 10 | PR #170 |
| Titles of a licence text | `text_title` | `src/licenseid/resolvetitle.py` (`TITLES`) | 4 | PRs #163, #165 |
| Trove classifier names | `trove_name` | `src/licenseid/trovenames.py` (`TROVE_NAMES`) | 89 (54 read) | 0.7.0 |
| Licence URLs (aliases) | `license_url`, detail `alias` | `src/licenseid/resolveurl.py` (`URL_ALIASES`) | 11 | issue #14 |

The SPDX License List has no field for other names: `licenses.json` gives
one `name` per ID. The table of deprecated IDs (`deprecatedids.py`) maps
IDs, not names, and is not here.

Projects and downloads are those of the PyPI sample (`[S]`, the top 10,000
projects by downloads, latest release each), summed over the values whose
reading took that table's step; downloads are the ranking list's 30-day
counts. A name the List also holds reads as a List name first
(`listed_name`) and is counted there, not here.

## 1. BSD aliases (`alias_name`)

### Rule

A spelling is in the table only if both hold:

1. a project of the PyPI sample declares it (with or without a final
   `License`); and
2. each word that is not `BSD` comes from the SPDX License List's name of
   the licence, from the Open Source Initiative (OSI), or is the clause
   count that the SPDX ID itself writes.

The List supplies only the words its two names quote.

### The aliases

Every value came from the `License` field. The table matches case in
ASCII only and spacing exactly; a final `License` or `licence` is the
prose rule P1.

| Alias | SPDX ID | Source of the words | Values in the sample | Projects | Downloads |
| --- | --- | --- | --- | --- | --- |
| `new bsd` | BSD-3-Clause | SPDX name (`[L]`), OSI (`[O3]`) | `New BSD` (8), `New BSD License` (1), `New BSD license` (1), `new BSD` (1) | 11 | 56,459,076 |
| `revised bsd` | BSD-3-Clause | SPDX name (`[L]`) | `Revised BSD License` (1) | 1 | 1,933,155 |
| `modified bsd` | BSD-3-Clause | OSI only (`[O3]`) | `Modified BSD License` (2), `modified BSD` (1) | 3 | 129,566,853 |
| `3-clause bsd` | BSD-3-Clause | OSI title (`[O3]`) | `3-clause BSD` (2), `3-Clause BSD License` (1) | 3 | 620,110,097 |
| `bsd-3` | BSD-3-Clause | the ID, `Clause` left out (`[L]`) | `BSD-3` (9) | 9 | 3,465,995 |
| `bsd 3` | BSD-3-Clause | the ID, `Clause` left out (`[L]`) | `BSD 3` (3) | 3 | 1,947,361 |
| `bsd3` | BSD-3-Clause | the ID, `Clause` left out (`[L]`) | `BSD3` (2) | 2 | 3,326,855 |
| `simplified bsd` | BSD-2-Clause | SPDX name (`[L]`), OSI (`[O2]`) | `Simplified BSD` (1), `Simplified BSD license` (1) | 2 | 7,601,458 |
| `2-clause bsd` | BSD-2-Clause | OSI title (`[O2]`) | `2-clause BSD` (3), `2-clause BSD License` (1) | 4 | 35,797,751 |
| `two-clause bsd` | BSD-2-Clause | the sample: the OSI's number spelt out (`[O2]`, `[S]`) | `Two-clause BSD license` (1) | 1 | 976,405 |
| **Total** | | | 17 values | 39 | 861,185,006 |

What each source says:

- `[L]`: BSD-3-Clause is named `BSD 3-Clause "New" or "Revised" License`,
  BSD-2-Clause `BSD 2-Clause "Simplified" License`. The quoted words
  `New`, `Revised` and `Simplified` are the List's own; each is quoted in
  one List name only (`tests/test_resolver_alias.py`).
- `[O3]`: the OSI titles BSD-3-Clause "The 3-Clause BSD License" and notes
  that it "has also been called the “New BSD License” or “Modified BSD
  License”".
- `[O2]`: the OSI titles BSD-2-Clause "The 2-Clause BSD License" and notes
  that it has also been called the Simplified BSD License and the FreeBSD
  License.
- The clause count: an SPDX BSD ID writes the number of its clauses
  (`BSD-2-Clause`, `BSD-3-Clause`, `BSD-4-Clause`). `BSD-3` is that ID less
  `-Clause`. This is a reading of the naming scheme, not a statement of
  either source.

### Not read, and why

| Value | Why not |
| --- | --- |
| `BSD`, `BSD License`, `BSD license`, `'BSD'` | no clause count: several licences; the trove table reads `BSD License` as no licence (Q3 of `resolver-0-7-plan.md`, deferred to 0.8) |
| `FreeBSD`, `FreeBSD License` | the OSI's name for BSD-2-Clause (`[O2]`), but the List has `FreeBSD-DOC` and the deprecated `BSD-2-Clause-FreeBSD` |
| `BSD 2`, `BSD-2`, `BSD 4`, `BSD-4` | no project of the sample declares them |
| `BSD License v3`, `BSD License, Version 3` | a version, not a clause count (prose rule P2) |
| `New BSD 4-clause`, `Simplified`, `New`, `Revised` | not a name of the table |
| `Modified BSD` near `BSD 3-Clause Modification` | not read as that: `BSD-3-Clause-Modification` and `BSD-Mark-Modifications` are other licences; no List name holds the word `modified` |

## 2. Titles of a licence text (`text_title`)

The title a licence's own text gives itself is as certain as a List name:
the licence writes it. A title is in the table only if a project of the
sample declares it and the licence's text writes it
(`tests/test_resolver_title.py` checks each against the text fixture,
`tests/fixtures/license-text-long/`, from `[T]`).

| Title (folded) | SPDX ID | Source | Values in the sample | Projects | Downloads |
| --- | --- | --- | --- | --- | --- |
| `cc0 1.0 universal` | CC0-1.0 | the CC0 text (`[T]`) | `CC0 1.0 Universal` (8) | 8 | 3,619,656 |
| `cc0` | CC0-1.0 | the CC0 text, which calls itself `CC0` apart from its version (`[T]`); the maintainer, 2026-11-05 | `CC0` (3) | 3 | 842,015 |
| `mulan psl v2` | MulanPSL-2.0 | the short name the Mulan PSL v2 text defines (`[T]`) | `Mulan PSL v2` (3) | 3 | 1,025,207 |
| `gnu general public license version 3, 29 june 2007` | GPL-3.0 (bare, `assumed_only`) | the title line of the GPL v3 text (`[T]`): a version and no grant (decision P49) | `GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007` (1) | 1 | 315,997 |
| **Total** | | | 4 values | 15 | 5,802,875 |

`CC0` is an exception to decision P47 (a name with no version names
nothing): CC0-1.0 is the only CC0. A title followed by `License` (`CC0
License`) and the GPL v3 title on two lines are not read.

## 3. Trove classifier names (`trove_name`)

The `License ::` classifiers of PyPA's `trove-classifiers` (`[C]`), each
decided once by what it writes: `stated` (one licence, with its version
and grant), `assumed` (a bare deprecated ID, read as written, with its
`-only` and `-or-later` candidates) or `none` (no single licence: a
category, a family, a name with no version where the List holds several,
or no SPDX ID). `tests/test_trovenames.py` checks every classifier of the
release against the table. A path `License :: OSI Approved :: X` reads as
`X` does (step `trove_path`).

The 54 names that read as a licence. Projects counts the sample values
read through the table's step; `-` is a name the sample does not declare,
or one read first as a List name.

| Classifier name | SPDX ID | Reading | Under | Projects |
| --- | --- | --- | --- | --- |
| `Aladdin Free Public License (AFPL)` | Aladdin | `stated` | top level | - |
| `Attribution Assurance License` | AAL | `stated` | OSI Approved | - |
| `Blue Oak Model License (BlueOak-1.0.0)` | BlueOak-1.0.0 | `stated` | OSI Approved | - |
| `Boost Software License 1.0 (BSL-1.0)` | BSL-1.0 | `stated` | OSI Approved | - |
| `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | CC0-1.0 | `stated` | top level | 3 |
| `CEA CNRS Inria Logiciel Libre License, version 2.1 (CeCILL-2.1)` | CECILL-2.1 | `stated` | OSI Approved | - |
| `CeCILL-B Free Software License Agreement (CECILL-B)` | CECILL-B | `stated` | top level | - |
| `CeCILL-C Free Software License Agreement (CECILL-C)` | CECILL-C | `stated` | top level | - |
| `CMU License (MIT-CMU)` | MIT-CMU | `stated` | OSI Approved | - |
| `Common Development and Distribution License 1.0 (CDDL-1.0)` | CDDL-1.0 | `stated` | OSI Approved | - |
| `Eclipse Public License 1.0 (EPL-1.0)` | EPL-1.0 | `stated` | OSI Approved | - |
| `Eclipse Public License 2.0 (EPL-2.0)` | EPL-2.0 | `stated` | OSI Approved | - |
| `Educational Community License, Version 2.0 (ECL-2.0)` | ECL-2.0 | `stated` | OSI Approved | - |
| `European Union Public Licence 1.0 (EUPL 1.0)` | EUPL-1.0 | `stated` | OSI Approved | - |
| `European Union Public Licence 1.1 (EUPL 1.1)` | EUPL-1.1 | `stated` | OSI Approved | - |
| `European Union Public Licence 1.2 (EUPL 1.2)` | EUPL-1.2 | `stated` | OSI Approved | - |
| `GNU Affero General Public License v3` | AGPL-3.0 | `assumed` | OSI Approved | 10 |
| `GNU Affero General Public License v3 or later (AGPLv3+)` | AGPL-3.0-or-later | `stated` | OSI Approved | 1 |
| `GNU General Public License v2 (GPLv2)` | GPL-2.0 | `assumed` | OSI Approved | 5 |
| `GNU General Public License v2 or later (GPLv2+)` | GPL-2.0-or-later | `stated` | OSI Approved | 3 |
| `GNU General Public License v3 (GPLv3)` | GPL-3.0 | `assumed` | OSI Approved | 20 |
| `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later | `stated` | OSI Approved | 15 |
| `GNU Lesser General Public License v2 (LGPLv2)` | LGPL-2.0 | `assumed` | OSI Approved | 1 |
| `GNU Lesser General Public License v2 or later (LGPLv2+)` | LGPL-2.0-or-later | `stated` | OSI Approved | 2 |
| `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 | `assumed` | OSI Approved | 6 |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later | `stated` | OSI Approved | 9 |
| `Historical Permission Notice and Disclaimer (HPND)` | HPND | `stated` | OSI Approved | - |
| `Intel Open Source License` | Intel | `stated` | OSI Approved | - |
| `ISC License (ISCL)` | ISC | `stated` | OSI Approved | 8 |
| `MirOS License (MirOS)` | MirOS | `stated` | OSI Approved | - |
| `MIT License` | MIT | `stated` | OSI Approved | - |
| `MIT No Attribution License (MIT-0)` | MIT-0 | `stated` | OSI Approved | - |
| `Motosoto License` | Motosoto | `stated` | OSI Approved | - |
| `Mozilla Public License 1.0 (MPL)` | MPL-1.0 | `stated` | OSI Approved | - |
| `Mozilla Public License 1.1 (MPL 1.1)` | MPL-1.1 | `stated` | OSI Approved | - |
| `Mozilla Public License 2.0 (MPL 2.0)` | MPL-2.0 | `stated` | OSI Approved | - |
| `Mulan Permissive Software License v2 (MulanPSL-2.0)` | MulanPSL-2.0 | `stated` | OSI Approved | - |
| `NASA Open Source Agreement v1.3 (NASA-1.3)` | NASA-1.3 | `stated` | OSI Approved | - |
| `Nethack General Public License` | NGPL | `stated` | OSI Approved | - |
| `Nokia Open Source License` | Nokia | `stated` | OSI Approved | - |
| `Nokia Open Source License (NOKOS)` | Nokia | `stated` | top level | - |
| `Open Group Test Suite License` | OGTSL | `stated` | OSI Approved | - |
| `Open Software License 3.0 (OSL-3.0)` | OSL-3.0 | `stated` | OSI Approved | - |
| `PostgreSQL License` | PostgreSQL | `stated` | OSI Approved | - |
| `Ricoh Source Code Public License` | RSCPL | `stated` | OSI Approved | - |
| `SIL Open Font License 1.1 (OFL-1.1)` | OFL-1.1 | `stated` | OSI Approved | - |
| `Sleepycat License` | Sleepycat | `stated` | OSI Approved | - |
| `Sun Industry Standards Source License (SISSL)` | SISSL | `stated` | OSI Approved | - |
| `The Unlicense (Unlicense)` | Unlicense | `stated` | OSI Approved | - |
| `Universal Permissive License (UPL)` | UPL-1.0 | `stated` | OSI Approved | 1 |
| `University of Illinois/NCSA Open Source License` | NCSA | `stated` | OSI Approved | - |
| `Vovida Software License 1.0` | VSL-1.0 | `stated` | OSI Approved | - |
| `X.Net License` | Xnet | `stated` | OSI Approved | - |
| `Zero-Clause BSD (0BSD)` | 0BSD | `stated` | OSI Approved | - |

Through the table: 13 names, 84 projects, 251,241,258 downloads. The 35
`none` names, each with its reason, are in `trovenames.py`; among them
`BSD License`, `Apache Software License` and `Python Software Foundation
License` (by usage only: Q3 of `resolver-0-7-plan.md`, deferred to 0.8),
and names with no version (`Artistic License`, `Common Public License`).
`Universal Permissive License (UPL)` is the one name with no version that
reads (`UPL-1.0`, the only UPL; the maintainer, 2026-11-05).

## 4. The projects that declare each entry

The October sample (`[S]`) keeps counts, not project names, and its raw
fetch is not in the repository. The names below come from a new fetch of
the same kind (`[R]`): the top 10,000 PyPI projects by downloads on
2026-11-06, the latest release of each (4 failed to fetch), the value
chosen as the sampler chooses it (`License-Expression`, then a one-line
`License`, then the classifiers). Rank is the project's place in that
list. A project counts under the first table step its value's reading
takes.

Against October, the BSD aliases moved by a few projects, as the list and
the releases moved: `BSD 3` 3 to 5, `BSD-3` 9 to 10, `modified BSD` 1 to
2, `2-clause BSD` 3 to 2, `new BSD` 1 to 0; the other values are as in
October. In all: BSD aliases 39 to 41 projects, titles 15 to 11, trove
names 84 to 80.

### BSD aliases

| Entry | Project | Rank | Declared value | Read as |
| --- | --- | --- | --- | --- |
| `2-clause bsd` | `patsy` | 608 | `2-clause BSD` | BSD-2-Clause |
| `2-clause bsd` | `imagehash` | 1620 | `2-clause BSD License` | BSD-2-Clause |
| `2-clause bsd` | `scrypt` | 8220 | `2-clause BSD` | BSD-2-Clause |
| `3-clause bsd` | `protobuf` | 34 | `3-Clause BSD License` | BSD-3-Clause |
| `3-clause bsd` | `twofish` | 5859 | `3-clause BSD` | BSD-3-Clause |
| `3-clause bsd` | `sphinx-gallery` | 5864 | `3-clause BSD` | BSD-3-Clause |
| `bsd 3` | `ddapm-test-agent` | 3325 | `BSD 3` | BSD-3-Clause |
| `bsd 3` | `pymonctl` | 9047 | `BSD 3` | BSD-3-Clause |
| `bsd 3` | `pywinbox` | 9073 | `BSD 3` | BSD-3-Clause |
| `bsd 3` | `ewmhlib` | 9788 | `BSD 3` | BSD-3-Clause |
| `bsd 3` | `iterative-stratification` | 9935 | `BSD 3` | BSD-3-Clause |
| `bsd-3` | `category-encoders` | 3299 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `session-info` | 5775 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `torchtnt` | 6477 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `pyeapi` | 6872 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `torcheval` | 7610 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `ncnn` | 7834 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `torchx` | 8005 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `torch-tb-profiler` | 8095 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `globmatch` | 8356 | `BSD-3` | BSD-3-Clause |
| `bsd-3` | `hstspreload` | 8443 | `BSD-3` | BSD-3-Clause |
| `bsd3` | `flagsmith-flag-engine` | 3447 | `BSD3` | BSD-3-Clause |
| `bsd3` | `flagsmith` | 3454 | `BSD3` | BSD-3-Clause |
| `modified bsd` | `jsonpointer` | 216 | `Modified BSD License` | BSD-3-Clause |
| `modified bsd` | `jobflow` | 5539 | `modified BSD` | BSD-3-Clause |
| `modified bsd` | `mp-pyrho` | 6549 | `modified BSD` | BSD-3-Clause |
| `modified bsd` | `panda3d` | 8047 | `Modified BSD License` | BSD-3-Clause |
| `new bsd` | `click-plugins` | 438 | `New BSD` | BSD-3-Clause |
| `new bsd` | `scandir` | 2837 | `New BSD License` | BSD-3-Clause |
| `new bsd` | `pyexcel-io` | 4095 | `New BSD` | BSD-3-Clause |
| `new bsd` | `lml` | 4144 | `New BSD` | BSD-3-Clause |
| `new bsd` | `pyexcel` | 4700 | `New BSD` | BSD-3-Clause |
| `new bsd` | `pyexcel-xls` | 5230 | `New BSD` | BSD-3-Clause |
| `new bsd` | `tinysegmenter` | 5743 | `New BSD` | BSD-3-Clause |
| `new bsd` | `awacs` | 6661 | `New BSD license` | BSD-3-Clause |
| `new bsd` | `pyexcel-xlsx` | 7075 | `New BSD` | BSD-3-Clause |
| `new bsd` | `pytracking2` | 7922 | `New BSD` | BSD-3-Clause |
| `revised bsd` | `uncertainties` | 2676 | `Revised BSD License` | BSD-3-Clause |
| `simplified bsd` | `bottleneck` | 1386 | `Simplified BSD` | BSD-2-Clause |
| `simplified bsd` | `gtsam` | 9086 | `Simplified BSD license` | BSD-2-Clause |
| `two-clause bsd` | `whoosh` | 3799 | `Two-clause BSD license` | BSD-2-Clause |

41 projects.

### Titles of a licence text

| Entry | Project | Rank | Declared value | Read as |
| --- | --- | --- | --- | --- |
| `cc0` | `libarchive-c` | 4915 | `CC0` | CC0-1.0 |
| `cc0` | `cryptg` | 7090 | `CC0` | CC0-1.0 |
| `cc0 1.0 universal` | `hbreader` | 4548 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `jsonasobj2` | 4550 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `pyjsg` | 4770 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `pyshex` | 4804 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `shexjsg` | 4805 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `rdflib-shim` | 4833 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `sparqlslurper` | 4859 | `CC0 1.0 Universal` | CC0-1.0 |
| `cc0 1.0 universal` | `fractional-indexing` | 6470 | `CC0 1.0 Universal` | CC0-1.0 |
| `gnu general public license version 3, 29 june 2007` | `remotezip2` | 6634 | `GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007` | GPL-3.0 |

11 projects.

### Trove classifier names

| Entry | Project | Rank | Declared value | Read as |
| --- | --- | --- | --- | --- |
| `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | `rust-just` | 2932 | `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | CC0-1.0 |
| `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | `gzip-stream` | 3201 | `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | CC0-1.0 |
| `CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | `mmhash3` | 7664 | `License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication` | CC0-1.0 |
| `GNU Affero General Public License v3` | `pyswisseph` | 3907 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `nuitka` | 4855 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `pymeshfix` | 5931 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `minisbd` | 6466 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `zendriver` | 7490 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `solc-select` | 7829 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `deadcode` | 7988 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `surt` | 8321 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `policyengine-core` | 8622 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `policyengine-us` | 8835 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3` | `codex-app-server-sdk` | 9305 | `GNU Affero General Public License v3` | AGPL-3.0 |
| `GNU Affero General Public License v3 or later (AGPLv3+)` | `ebooklib` | 4063 | `GNU Affero General Public License v3 or later (AGPLv3+)` | AGPL-3.0-or-later |
| `GNU Affero General Public License v3 or later (AGPLv3+)` | `pyhwp` | 5125 | `GNU Affero General Public License v3 or later (AGPLv3+)` | AGPL-3.0-or-later |
| `GNU General Public License v2 (GPLv2)` | `jdk4py` | 6219 | `GNU General Public License v2 (GPLv2)` | GPL-2.0 |
| `GNU General Public License v2 (GPLv2)` | `aioping` | 7470 | `GNU General Public License v2 (GPLv2)` | GPL-2.0 |
| `GNU General Public License v2 (GPLv2)` | `allianceauth` | 9577 | `GNU General Public License v2 (GPLv2)` | GPL-2.0 |
| `GNU General Public License v2 or later (GPLv2+)` | `pylint-django` | 2836 | `GNU General Public License v2 or later (GPLv2+)` | GPL-2.0-or-later |
| `GNU General Public License v2 or later (GPLv2+)` | `linkchecker` | 8744 | `GNU General Public License v2 or later (GPLv2+)` | GPL-2.0-or-later |
| `GNU General Public License v3 (GPLv3)` | `jaro-winkler` | 3359 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `country-converter` | 3747 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `pedalboard` | 4026 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `bgutil-ytdlp-pot-provider` | 4148 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `peakrdl-ipxact` | 5217 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `cursor` | 5808 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `pycel` | 6863 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `ipi` | 7279 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `markdown-include` | 7691 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `readline` | 8302 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `soynlp` | 8394 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `evo` | 8398 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `zipstream-new` | 8746 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `censusgeocode` | 9406 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `django-esi` | 9503 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 (GPLv3)` | `sphinx-markdown-tables` | 9743 | `GNU General Public License v3 (GPLv3)` | GPL-3.0 |
| `GNU General Public License v3 or later (GPLv3+)` | `pymsgbox` | 2701 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `phonemizer` | 3430 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `plyfile` | 3833 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `phonemizer-fork` | 4339 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `diceware` | 5909 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `ipsw-parser` | 6433 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `opack2` | 6562 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `pytun-pmd3` | 6578 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `pygnuutils` | 6606 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `developer-disk-image` | 6608 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `pycrashreport` | 6611 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `pygmsh` | 6771 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `pyiosbackup` | 7754 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `sure` | 8845 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU General Public License v3 or later (GPLv3+)` | `libscrc` | 9022 | `GNU General Public License v3 or later (GPLv3+)` | GPL-3.0-or-later |
| `GNU Lesser General Public License v2 (LGPLv2)` | `pyxdg` | 4291 | `GNU Lesser General Public License v2 (LGPLv2)` | LGPL-2.0 |
| `GNU Lesser General Public License v2 or later (LGPLv2+)` | `pygobject` | 4661 | `GNU Lesser General Public License v2 or later (LGPLv2+)` | LGPL-2.0-or-later |
| `GNU Lesser General Public License v2 or later (LGPLv2+)` | `biotraj` | 5569 | `GNU Lesser General Public License v2 or later (LGPLv2+)` | LGPL-2.0-or-later |
| `GNU Lesser General Public License v3 (LGPLv3)` | `edge-tts` | 1256 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 (LGPLv3)` | `rtfde` | 1325 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 (LGPLv3)` | `pyte` | 2257 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 (LGPLv3)` | `img2pdf` | 2448 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 (LGPLv3)` | `qpsolvers` | 3836 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 (LGPLv3)` | `django-admin-autocomplete-filter` | 5393 | `GNU Lesser General Public License v3 (LGPLv3)` | LGPL-3.0 |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `casadi` | 2344 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `dramatiq` | 2892 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `fickling` | 4658 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `apeye` | 5506 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `python-bitcoinlib` | 5914 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `pyclamd` | 7685 | `License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `odoo-test-helper` | 8179 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `utils` | 8198 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `mdanalysis` | 8253 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `GNU Lesser General Public License v3 or later (LGPLv3+)` | `wsdiscovery` | 9247 | `GNU Lesser General Public License v3 or later (LGPLv3+)` | LGPL-3.0-or-later |
| `ISC License (ISCL)` | `ptyprocess` | 234 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `isoduration` | 493 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `mongomock` | 1331 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `anyascii` | 1974 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `cerberus` | 2056 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `aiologic` | 2106 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `culsans` | 2177 | `ISC License (ISCL)` | ISC |
| `ISC License (ISCL)` | `mapbox-earcut` | 2656 | `ISC License (ISCL)` | ISC |
| `Universal Permissive License (UPL)` | `ocifs` | 8328 | `Universal Permissive License (UPL)` | UPL-1.0 |

80 projects.

## References

`[L]` SPDX Workgroup. "SPDX License List Data," version 3.29.0, released
September 16, 2026. `json/licenses.json`, entries `BSD-2-Clause` and
`BSD-3-Clause`. <https://github.com/spdx/license-list-data>. Copy in the
repository: `tests/fixtures/license-list/spdx-license-ids.json`.

`[O3]` Open Source Initiative. "The 3-Clause BSD License." Accessed
November 6, 2026. <https://opensource.org/license/bsd-3-clause>.

`[O2]` Open Source Initiative. "The 2-Clause BSD License." Accessed
November 6, 2026. <https://opensource.org/license/bsd-2-clause>.

`[T]` SPDX Workgroup. "SPDX License List Data," version 3.29.0. `text/`,
files `CC0-1.0.txt`, `MulanPSL-2.0.txt` and `GPL-3.0-only.txt`.
<https://github.com/spdx/license-list-data>. Copies in the repository:
`tests/fixtures/license-text-long/`.

`[C]` Python Packaging Authority. "trove-classifiers," version
2026.9.21.13. <https://pypi.org/project/trove-classifiers/>. The version
is `trovenames.TROVE_CLASSIFIERS_VERSION`.

`[R]` licenseid. A fetch of `tools/pypi_licence_sample` (`fetch --count
10000`), 2026-11-06, of the `top-pypi-packages` list (Hugo van Kemenade,
<https://hugovk.github.io/top-pypi-packages/>) and the PyPI JSON API. Not
kept in the repository.

`[S]` licenseid. "PyPI Licence Values of `sample-2026-10.jsonl`: 10,000
Projects." `tests/fixtures/pypi_values_2026-10.tsv`, built by
`tools/pypi_licence_sample` (see its `README.md` and
[dataset-licence-values.md](dataset-licence-values.md)).

## How the numbers were made

Each value of `tests/fixtures/pypi_values_2026-10.tsv` (read as Python
`unicode_escape`) was resolved on an SPDX 3.29.0 database, and its projects
and downloads summed under the first `alias_name`, `text_title` or
`trove_name` step of its reading, by script, on 2026-11-06 (`main`
253690f with PR #170). The OSI wording was read from the two pages on that
day; it is not kept in the repository.

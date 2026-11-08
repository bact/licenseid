---
Created: 2026-11-08
Last-Modified: 2026-11-09
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Licence URLs in package metadata

How real package metadata writes a licence as a URL, and what a reader built
on the SPDX License List (`seeAlso`) would read of it. Survey for issue #14
(a licence URL as its licence). Raw frames and samples are not committed; the
paths and SHA-256 of what this note counts are at the end.

## Method

- **Tool.** `tools/licence_sample` (`rank`, then `fetch`), at commit
  `73eef35` (licenseid 0.7.3), run from a scratch directory outside the
  repository. Criteria and per-channel sources:
  `collection-criteria.md`. Requests send the tool's User-Agent, 8 at a
  time, with its own retries; no credentials. No fetch failed (0 errors in
  all five samples).
- **Frames (taken 2026-11-07, UTC).** Maven Central: top 1,000 by dependent
  packages. NuGet, npm, PyPI, crates.io: top 300 by 30-day downloads. All
  ranked by ecosyste.ms (`rank`), values read from each registry (`fetch`).
- **A URL value.** A `url`, `parent:url` (Maven), `licenseUrl` (NuGet) or
  `licenses.url` (npm) value, or any value that is wholly a URL
  (`http(s)://` or `www.`). A URL inside prose is not counted (out of scope
  for v1).
- **List.** SPDX License List 3.29.0
  (`spdx-data-v3.29.0.tar.gz` of the read-only cache), `seeAlso` of
  licences and, apart, of exceptions, plus each ID's own page
  `spdx.org/licenses/<ID>`.
- **Prototype key.** The plan's key function, written again in a script kept
  outside the repository: the query is kept, the fragment, `www.`, port,
  trailing slash, `index.html|htm|php` and one `.html|.htm|.txt|.php` suffix
  are dropped, case folded; `opensource.org` `license|licenses` to `license`
  and `.` to `-` in the slug; `gnu.org` `-standalone`; `creativecommons.org`
  `legalcode` and `deed.*`; `spdx.org` `.json`; `spdx:` prefix. A value that
  gives no key (a relative `LICENSE.txt`) is counted as `unkeyable`.
- **Classes.** A package counts once, in the best class among its URLs:
  `list page` (`spdx.org/licenses/<ID>`), `see also` (key names one
  licence), `id in path` (`licenses.nuget.org/<ID>`,
  `choosealicense.com/licenses/<id>`, ScanCode LicenseDB key whose SPDX ID
  is on the List), `family` (key names one base with `-only`, `-or-later`,
  `+` or bare), `ambiguous` (several unrelated licences), `exception`
  (names only exceptions), `unread`.
- **PyPI 2026-10 sample.** `tests/fixtures/pypi_values_2026-10.tsv`: 10
  values that are wholly a URL, 20 projects (used for alias counts only).

## Counts per channel

Packages in the frame, packages stating a URL, distinct URL values, and the
URL-stating packages by class:

```text
channel  pkgs  with_url  urls  list  see  path  family  ambig  unread  unkeyable
maven    1000      962   157     7   793     0       5      1     145        11
nuget     300      295    11     0     0   182       0      0     113         0
npm       300        1     1     0     0     1       0      0       0         0
pypi      300        0     0     0     0     0       0      0       0         0
cargo     300        0     0     0     0     0       0      0       0         0
```

- Maven states a URL in 96% of packages and the List reads 83% of those
  (800 of 962, `list page` plus `see also`); 675 of the 1,000 packages carry
  `apache.org/licenses/license-2.0` (key), in several spellings.
- NuGet: 182 `licenses.nuget.org/<single ID>`; 85 `go.microsoft.com/fwlink`
  and 8 `aka.ms/deprecateLicenseUrl` name no licence (113 unread in all,
  with 15 `raw.githubusercontent.com` and 3 GitHub blob paths).
- npm, PyPI and crates.io top 300 hold no URL as a licence value (one npm
  package writes `choosealicense.com/licenses/mit/`). The 2026-10 PyPI
  sample, on 10,000 projects, has the 10 URL values above: 10 projects
  read by `see also`, 10 unread (`gpl.html`, `mit-license.php` x2, aspose,
  `aka.ms` x4, fontawesome, mosek).
- Distinct keys in the survey: 18 `see also`, 6 `list page`, 5 `id in path`,
  3 `family`, 1 `ambiguous`, 91 `unread`, 1 `unkeyable`.
- Family keys: `gnu.org/licenses/old-licenses/lgpl-2.1` (7 packages),
  `opensource.org/license/lgpl-2-1` (2), `gnu.org/licenses/lgpl-3.0` (2).
- Ambiguous key: `mozilla.org/mpl/2.0` (MPL-2.0 and
  MPL-2.0-no-copyleft-exception; 1 package).
- Most read keys by packages: `apache.org/licenses/license-2.0` 675,
  `eclipse.org/legal/epl-2.0` 32, `opensource.org/license/mit` 26,
  `eclipse.org/org/documents/edl-v10` 25 (BSD-3-Clause), `epl-v20` 19.

## Top 60 unread keys

Packages (survey plus PyPI sample), most first. Keys are in the prototype
normal form; 97 distinct unread keys in all.

```text
 85 go.microsoft.com/fwlink?linkid=329770
 17 opensource.org/license/mit-license
 14 raw.githubusercontent.com/aspnet/aspnetcore/2.0.0/license
 12 asm.ow2.io/license
 11 (not a URL: LICENSE.txt)
  9 repository.jboss.org/licenses/apache-2.0
  8 aka.ms/deprecatelicenseurl
  8 raw.githubusercontent.com/akka/akka/v2.8.8/license
  6 glassfish.dev.java.net/nonav/public/cddl+gpl
  6 jquery.org/license
  6 openjdk.java.net/legal/gplv2+ce
  6 scala-lang.org/downloads/license
  6 w3.org/consortium/legal/copyright-documents-19990405
  5 aws.amazon.com/apache2.0
  5 bouncycastle.org/licence
  5 eclipse.org/org/documents/epl-2.0/epl-2.0
  5 eclipse.org/org/documents/epl-v10
  5 opensource.org/license/bsd-license
  4 antlr.org/license
  4 apache.org/license/license-2.0
  4 gnu.org/licenses/lgpl-2.1
  4 oss.oracle.com/licenses/cddl+gpl-1.1
  3 github.com/dotnet/emsdk/blob/main/license
  3 gnu.org/licenses/gpl-2.0
  3 gwtproject.org/terms
  3 jmock.org/license
  3 opensource.org/license/cpl1-0
  3 raw.githubusercontent.com/hamcrest/javahamcrest/master/license
  2 eclipse.org/licenses/edl-v10
  2 fsf.org/licensing/licenses/lgpl
  2 github.com/googleapis/google-cloud-java/blob/main/license
  2 github.com/sbt/junit-interface/blob/master/license
  2 glassfish.dev.java.net/public/cddlv1.0
  2 gnu.org/copyleft/lesser
  2 javaee.github.io/javamail/license
  2 mozilla.org/en-us/mpl/2.0
  2 opensource.org/license/eclipse-1-0
  2 raw.github.com/hunterhacker/jdom/master/license
  2 raw.githubusercontent.com/elastic/elasticsearch/v7.17.29/licenses...
  1 day.com/content/dam/day/downloads/jsr283/license
  1 day.com/dam/day/downloads/jsr283/day-spec-license
  1 docs.ldap.com/ldap-sdk/docs/license-unboundid-ldapsdk
  1 github.com/dom4j/dom4j/blob/master/license
  1 github.com/dotnet/standard/blob/master/license
  1 github.com/flyway/flyway/blob/main/readme
  1 github.com/highsource/jaxb-tools/blob/master/license
  1 github.com/hjson/hjson-java/blob/master/license
  1 github.com/javaee/activation/blob/master/license
  1 github.com/javaee/javax.annotation/blob/master/license
  1 github.com/javaee/javax.transaction/blob/master/license
  1 github.com/javaee/javax.xml.soap/blob/master/license
  1 github.com/javaee/jax-ws-spec/blob/master/license.md
  1 github.com/mockito/mockito/blob/main/license
  1 github.com/mockito/mockito/blob/master/license
  1 github.com/pagehelper/pagehelper-spring-boot/blob/master/license
  1 github.com/redis/jedis/blob/master/license
  1 github.com/redis/lettuce/blob/main/license
  1 github.com/sbt/test-interface/blob/master/license
  1 github.com/scalameta/scalameta/blob/main/license.md
  1 github.com/stleary/json-java/blob/master/license
```

The fixture-only key `aka.ms/azureml-sdk-license` (4 projects) sits among
the rest: it is not in the Maven or NuGet survey. Of the 60 rows, the
unread keys fall in four groups: pages that name no licence (`fwlink`,
`aka.ms`), a file in one project's repository (`github.com/.../blob/...`,
`raw.githubusercontent.com/...`: 35 + 25 packages by host), a project's own
statement page (`asm.ow2.io`, `jquery.org`, `scala-lang.org`, ...), and a
licence page the List lacks (the alias candidates below).

## NuGet path forms

`licenses.nuget.org/` URLs, percent-decoded, with packages:

```text
154 single ID   MIT
 23 single ID   Apache-2.0
  4 single ID   BSD-3-Clause
  1 single ID   PostgreSQL
  1 compound    MS-PL OR Apache-2.0
```

No bracket form occurs. 182 of 183 are one ID; the compound form (0.5% of
the NuGet URLs) was deferred in v1 and gave `not found`. Issue #187 asked
for it; it is read since 0.8.3 (1 of 183 read), with the page's
URL-encoded expression (`%20`, `( ) +` literal) decoded for that host only.

## ScanCode LicenseDB

`https://scancode-licensedb.aboutcode.org/index.json` (fetched once on
2026-11-08; 2,733 entries). No survey package uses a ScanCode URL, so the
host rule rests on the format, not on frequency.

- **No List SPDX ID.** 1,947 keys have an empty `spdx_license_key` or a
  `LicenseRef-scancode-*` one. Their case-folded key is mostly no List ID, so
  the reader finds an unknown ID and says nothing.
- **Key folds to a List ID but ScanCode's ID differs: 24 keys.** 11 are the
  same licence under the `-only` ID of the deprecated bare ID (`gpl-2.0`
  gives `GPL-2.0-only`, likewise `agpl-1.0`, `agpl-3.0`, `gfdl-1.1`,
  `gfdl-1.2`, `gfdl-1.3`, `gpl-1.0`, `gpl-3.0`, `lgpl-2.0`, `lgpl-2.1`,
  `lgpl-3.0`): the family policy answers them. 13 are another licence or no
  SPDX ID, so reading the key as the ID would be wrong; they form
  `SCANCODE_NOT_SPDX` below. Examples: `bsl-1.0` is
  `LicenseRef-scancode-bsl-1.0`, `x11` is `ICU`, `openssl` is
  `OpenSSL-standalone`, `net-snmp` is `LicenseRef-scancode-net-snmp` (other
  key `Net-SNMP`).
- 253 keys in all have a ScanCode SPDX ID on the List that differs from the
  key (for example `agpl-3.0-plus` to `AGPL-3.0-or-later`). Those whose key
  folds to no List ID stay unknown IDs for a reader that takes the key as an
  ID, and are left unread; reading them through the index would need data
  the wheel does not ship.

## Alias candidates

Acceptance rule (plan): at least 3 distinct packages in the survey plus the
PyPI sample, a primary source that shows exactly one licence and version,
absent from the List table, not an unversioned or family page. Pages were
fetched on 2026-11-07 and 2026-11-08, one request per second per host, one
redirect followed (a second hop only for the OSI hosts, from an
`opensource.org` redirect), 38 requests in all. `gnu.org` (and
`glassfish.dev.java.net`) did not answer within 30 s in five attempts, so no
GNU page could be read.

```text
key (normal form)                       pkgs  decision
opensource.org/license/mit-license        17  accept: 301 to /license/mit
eclipse.org/org/documents/epl-v10          5  accept: 301 to epl-1.0 page
eclipse.org/org/documents/epl-2.0/epl-2.0 5  accept: EPL 2.0 text, 200
repository.jboss.org/licenses/apache-2.0   9  accept: Apache 2.0 text, 200
aws.amazon.com/apache2.0                   5  accept: 301 to /apache-2-0/
opensource.org/license/cpl1-0              3  accept: 301 to /license/cpl-1-0
openjdk.java.net/legal/gplv2+ce            6  accept: openjdk.org page
oss.oracle.com/licenses/cddl+gpl-1.1       4  accept, flag: CDDL 1.1 text
```

Evidence and notes for each:

- `opensource.org/license/mit-license` (from
  `opensource.org/licenses/mit-license.php`): the OSI redirects it to
  `https://opensource.org/license/mit` ("The MIT License"). 15 survey
  packages (Maven) plus 2 PyPI projects. Target `MIT`.
- `eclipse.org/org/documents/epl-v10` (from `.../epl-v10.php`): 301 to
  `https://www.eclipse.org/org/documents/epl-1.0/` ("Eclipse Public
  License"). The List has only `eclipse.org/legal/epl-v10`. Target
  `EPL-1.0`.
- `eclipse.org/org/documents/epl-2.0/epl-2.0` (from `.../EPL-2.0.txt`):
  200, text "Eclipse Public License - v 2.0". Last modified 2026-11-03.
  Target `EPL-2.0`.
- `repository.jboss.org/licenses/apache-2.0` (from `.../apache-2.0.txt`):
  200, the text "Apache License Version 2.0"; a vendor copy, last modified
  2025-07-03. Target `Apache-2.0`. Accept this one key, not a host rule.
- `aws.amazon.com/apache2.0`: 301 to `/apache-2-0/`, page "Apache 2.0",
  modified 2026-11-06. Target `Apache-2.0`.
- `opensource.org/license/cpl1-0` (from `.../licenses/cpl1.0.txt`): the OSI
  redirects it to `https://opensource.org/license/cpl-1-0`. Exactly 3
  packages. Target `CPL-1.0`.
- `openjdk.java.net/legal/gplv2+ce` (from `.../gplv2+ce.html`): 301 to
  `https://openjdk.org/legal/gplv2+ce.html`, "OpenJDK: GPLv2 + Classpath
  Exception". Target `GPL-2.0-with-classpath-exception` (deprecated; the List
  already gives that ID `gnu.org/software/classpath/license`).
- `oss.oracle.com/licenses/cddl+gpl-1.1`: 200, the text "Common Development
  and Distribution License (CDDL) Version 1.1". The name `cddl+gpl` hints at
  a dual licence, but the page shows CDDL 1.1 only, as the List treats
  `glassfish.java.net/public/cddl+gpl_1_1`. Target `CDDL-1.1`; the
  maintainer should confirm (flag).

Rejected:

- `opensource.org/license/bsd-license`: 5 packages; 301 to
  `opensource.org/licenses/bsd-license.php`, a page for the 2-clause (and in
  practice 3-clause) licence. Never aliased.
- `gnu.org/licenses/lgpl-2.1` (4), `gnu.org/licenses/gpl-2.0` (3),
  `gnu.org/licenses/agpl-3.0` (0 packages): family pages, and not
  fetchable (timeouts). The family policy would have to read them; they are
  not static aliases. `gnu.org/copyleft/lesser` (2) and `gpl.html` (1) are
  unversioned.
- `opensource.org/license/apache2-0`: 0 packages in the survey and the
  sample (the OSI redirects `apache2.0.php` to `/license/apache-2-0`, which
  the List has). `opensource.org/license/eclipse-1-0` (2): redirect to
  `/license/epl-1.0`, only 2 packages.
- `apache.org/license/license-2.0` (4): a misspelt path (`license`), the
  server answers 404.
- `eclipse.org/licenses/edl-v10` (2): redirects to `/legal`, so the page is
  gone.
- `glassfish.dev.java.net/...cddl+gpl` (6) and `.../cddlv1.0` (2): the
  host did not answer; a dual-licence name.
- `w3.org/consortium/legal/copyright-documents-19990405` (6): a document
  licence ("DOCUMENT NOTICE"), no List ID.
- Project statement pages: `asm.ow2.io/license` (12), `jquery.org/license`
  (6, 301 to `jquery.com/license/`), `scala-lang.org/downloads/license`
  (6, 301 to `scala-lang.org/license/`), `bouncycastle.org/licence` (5),
  `antlr.org/license` (4), `gwtproject.org/terms` (3), `jmock.org/license`
  (3): their titles ("ASM - License", "ANTLR v4 License", ...) were read,
  not their text, so "exactly one licence and version" is not shown; each is
  a project's page, not a licence's. Revisit with a body check.
- GitHub blob and raw paths: a file of one project, not a licence's page.
- `go.microsoft.com/fwlink`, `aka.ms/...`, `fontawesome.com`, `mosek.com`,
  `about.aspose.com`: name no SPDX licence.

### Mozilla locale segment and hosts

`mozilla.org/en-US/MPL/2.0/` appears in 2 packages and `/en-US/MPL/1.1/` in 1;
the same pages without a locale occur in 3 more. 3 locale URLs in all, under
the 5-package bar for a host rule: no `mozilla.org` locale rule. (`mozilla.org
/MPL/2.0` is the ambiguous key above: the plan's MPL override handles it.)
No host rule for `eclipse.org`, `opensource.org` beyond the plan's, or
`repository.jboss.org`: the accepted keys are single entries.

## Files counted

All under `/private/tmp/claude-501/url-survey/` (not committed):

```text
sha256                                                            file
f04aeb8fab72a9f27583d2606bb5299a2df61d4131b766ef3b3ab07f8d797154  frame-maven.jsonl
bbc983c2682501fde54a27b7575d1adb284e1b4c710a555cc3fb80e106d9baed  frame-nuget.jsonl
b78c0a8f8789a7b50a2ee86409968840af309e4820b918c91bd88fa3f867d7ee  frame-npm.jsonl
edd7cbe435b169238b8fa11916af34e69b2225e7d82a07d1a73140d947d067fb  frame-pypi.jsonl
783e7bee6dab12749604f3f404e960e0000ca1e2366255d3e56cc6afb9b9cf28  frame-cargo.jsonl
d3cd4f99d55dd199086bbc6d06a131502110e0cecb92970b1663dbc09a82fa1c  sample-maven.jsonl
df623071557fdfa1ba6618570e2acbfc7ac86c143ea70f8cb72a83304f484059  sample-nuget.jsonl
7ba41714a318f9d008c89f9fb874606522ba0fee57022b2735cd07fa3cd3e2b7  sample-npm.jsonl
b9937f03e0843f989f6c308f2b97db3407a4b5ed5ca064f74c0b4dbea891f731  sample-pypi.jsonl
07679c56bdf3cca4f6ae19f5c920d7749df4102ade65804971edb9cbf45dc714  sample-cargo.jsonl
9b0bdc5cc63a53bcc73bd90c87755a5db6da0096258642832ba54be78e3ad40b  scancode/index.json
72a037d484d8c283b0221d2ac7df9823054e7eb097afcae82aa7053c3ba25f35  urls.tsv
d69195f5b11d4b84ffccd12d943e90732694d00fea42dc81fcc66f79d6cc8104  spdx-data-v3.29.0.tar.gz
```

`urls.tsv` lists every URL value of every channel (channel, url, packages).
The analysis script is `/private/tmp/claude-501/url-survey-scripts/survey.py`
(run with `python -I`); the page probe is `probe.py` beside it, its replies
in `alias-probe*.tsv`.

## Machine-readable block

Keys are in normal form (the plan's `url_key`). Paste into `resolveurl.py`.

```text
SCANCODE_NOT_SPDX
brian-gladman-3-clause
bsd-2-clause-freebsd
bsd-2-clause-netbsd
bsl-1.0
intel
libtool-exception
mvt-1.1
net-snmp
nokia-qt-exception-1.1
openssl
opl-1.0
tpl-1.0
x11

URL_ALIASES (key -> SPDX ID, source URL)
opensource.org/license/mit-license -> MIT, https://opensource.org/license/mit
eclipse.org/org/documents/epl-v10 -> EPL-1.0, https://www.eclipse.org/org/documents/epl-1.0/
eclipse.org/org/documents/epl-2.0/epl-2.0 -> EPL-2.0, https://www.eclipse.org/org/documents/epl-2.0/EPL-2.0.txt
repository.jboss.org/licenses/apache-2.0 -> Apache-2.0, https://repository.jboss.org/licenses/apache-2.0.txt
aws.amazon.com/apache2.0 -> Apache-2.0, https://aws.amazon.com/apache-2-0/
opensource.org/license/cpl1-0 -> CPL-1.0, https://opensource.org/license/cpl-1-0
openjdk.java.net/legal/gplv2+ce -> GPL-2.0-with-classpath-exception, https://openjdk.org/legal/gplv2+ce.html
```

`oss.oracle.com/licenses/cddl+gpl-1.1` was dropped from the block on
2026-11-08: the name says a dual licence (CDDL and GPL), so reading it as
CDDL-1.1 alone would narrow what the author wrote.

`SCANCODE_NOT_SPDX` holds the 13 collisions; the full list of 1,947 keys
with no List SPDX ID is `scancode_not_spdx.txt` beside the data. Keys of
the 11 `-only` renames are left out on purpose (same licence).

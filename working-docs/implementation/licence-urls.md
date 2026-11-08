---
Created: 2026-11-08
Last-Modified: 2026-11-09
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Licence URLs read as their licence

Record of the reader built for issue #14 (PR for #14, number not yet
given): `resolve()`, `detect()`, a tag and a manifest field read a licence
URL as the licence it names. The survey that fed it is
[`../paper-notes/licence-urls.md`](../paper-notes/licence-urls.md); the
user-facing rules are in `docs/resolve.md`.

## The problem

Package metadata states a licence as a URL (a Maven POM `<url>`, NuGet's
`licenseUrl`). Before this change a URL was matched as text:
`opensource.org/licenses/MIT` gave `any-OSI-perl-modules` at 0.87 and
`spdx.org/licenses/MIT.html` gave `Parity-7.0.0` (roadmap item 45). A tag
read the second as `MIT`, `resolve()` did not, and a path that ends in an ID
on any host could be read as that ID.

## Decisions and why

- **Hybrid, derived from the List.** The reader keeps no table of known
  hosts. A URL is read by what the SPDX License List itself says: the
  `seeAlso` pages of each licence (the new `license_urls` table, 997 rows
  for licences and 128 for exceptions on 3.29.0) plus the List's own page
  of an ID. A new List release adds its pages with no code change.
- **Rejected: a host table that reads the last path segment as an ID.**
  `https://evil.com/licenses/MIT` would be `MIT`. The reader takes an ID
  from a path only on four hosts whose pages end in an ID (`ID_PAGES`:
  spdx.org, licenses.nuget.org, choosealicense.com, ScanCode LicenseDB).
- **Rejected: pre-computed keys in the database.** Every change to a key
  rule would need a rebuild; the table keeps the raw URLs.
- **Rejected: a static table of all 900 or so URLs.** It goes stale with
  each List release and is far over the file-size limit.
- **Rejected: URLs from the bundle and answers from the database.** Two
  List versions would stand in one answer; the URLs and the answer come from
  the one List `resolve()` reads, with a database or without.
- **Decided by the user (2026-11-08).** A GNU family page answers the bare
  deprecated ID, `assumed_only` with both candidates; MPL-2.0 and OFL-1.1
  pages that also list variants get an alias, and every other shared URL is
  refused; the database build goes from 3 to 4; planned for 0.8.0. Deferred:
  a URL inside prose. NuGet's compound paths came later (issue #187, below).
- **Not a regex of URLs found in prose.** A URL inside a sentence is out of
  scope here; the reader takes a whole value or one operand.
- **One key, one reader.** `urlkey.url_key` writes each spelling of a URL as
  one string; the List's URLs and a declared one go through it, so they
  compare as strings. `resolveurl.py` is the only reader; a tag and a field
  call it through `url_license_id` for each word of the value.
- **A refusal claims the value.** A page of several licences, or of
  exceptions only, gives `unresolved` with a reason of its own, so no later
  reader guesses at the URL. A URL that names nothing is not claimed.

## Decisions after review (2026-11-08)

An independent review of the branch found these; each was decided by the
user and fixed as follows.

- **B1, a List URL with a fragment.** The first version skipped every List
  URL with a fragment, but a declared URL loses its fragment in the key, so
  `fedoraproject.org/wiki/Licensing/MIT#enna`, written as the List writes
  it, read as `mpich2`, the owner of the bare page: wrong, and exact. Five
  such URLs (`#AdobeGlyph`, `#enna`, `#feh`, FSFUL's
  `#License_Retention_Variant`, Python's `#execution-tracing`) read as
  another licence. Now `fragment_page_key` keys those URLs by their page,
  and a page counts the owners of both: `Licensing/MIT` is refused
  (`Adobe-Glyph`, `MIT-enna`, `MIT-feh`, `mpich2`), and a page the List
  gives only with a fragment still names nothing (`gpl-faq.html`). One
  index holds both (`page_index_key`, a fragment URL under `#` and its
  page key): the list keeps the index of one key function, and two would
  rebuild it, 5.5 ms each, at every lookup.
- **S2, a licence and an exception on one page.** The licence beat the
  exception, so `maranget/hevea`'s LICENSE read as `QPL-1.0-INRIA-2004`
  without its exception. Now such a page is refused (`url names a licence
  with an exception: ...`), unless each licence is one of the List's old
  IDs of both (deprecated, no successor, `-with-` in the ID:
  `GPL-2.0-with-classpath-exception`), read as it is. `wxWindows` is no
  such ID, so `opensource.org/license/wxWindows` is now refused.
- **S4, `spdx.org/licenses/<ID>+`.** Before the reader, a tag read
  `https://spdx.org/licenses/MIT+` as `MIT+` (683 IDs). On the List's own
  page (and `spdx:`) only, an ID with a `+` operator (`plusoperator`) is
  read as the leaf reads `MIT+`; a `+` after a qualifier, after a
  `LicenseRef-*` or an exception names nothing. Other losses the review
  counted are accepted: `opensource.org/licenses/<ID>` for an ID the OSI
  does not publish (635), with a `+` (12), and
  `spdx.org/licenses/LicenseRef-foo` (1): a URL on a host that does not
  publish that ID no longer reads.
- **S5, a page that offers a choice.** The List gives the GlassFish pages
  (`glassfish.java.net/public/CDDL+GPL_1_1.html`,
  `javaee.github.io/glassfish/LICENSE`) to `CDDL-1.1` alone, but each offers
  CDDL 1.1 or GPL 2 with the Classpath exception. `DUAL_PAGES`, a reviewed
  table, refuses them as several licences.
- **N1.** A port above 65535 is no URL.
- **Not done: the OpenJDK LICENSE page.** The review asked for
  `github.com/openjdk/jdk/.../LICENSE` to be refused as a licence with an
  exception, but the List gives it only to `GPL-2.0-only` and
  `GPL-2.0-or-later`, so the S2 rule does not reach it: it is still the
  family page, `GPL-2.0`. Refusing it needs a reviewed table entry.

## Key rules (`urlkey.py`)

Applied in this order: refuse a value over 2,048 characters, a character
that is not ASCII or not one RFC 3986 allows, or a bad `%`; fold ASCII case;
`spdx:<ID>` is `spdx.org/licenses/<ID>`; drop `https://` or `http://` (a
host and `/` with no scheme is also a URL, any other scheme is not); drop a
`#fragment`, keep a non-empty `?query`, decode nothing; host: no user
information, no IP literal, port (0 to 65535) and one trailing `.`
dropped, one leading `www.` dropped, at least two labels with the last of
letters; path: one trailing `/`, an `index.html|htm|php` and one
`.html|.htm|.txt|.php` dropped, an empty, `.` or `..` segment refused; host
rules (`opensource.org`'s two page forms, `gnu.org` `-standalone`,
`creativecommons.org` `legalcode` and `deed.*`, `spdx.org` `.json`); a key
must key to itself.

Why these: the keys of Maven's top 1,000 packages differ in scheme, `www.`,
case, `.txt` and `.html` alone (675 packages state
`apache.org/licenses/license-2.0` in several spellings). The query is kept
because the List tells some pages apart by it alone. Non-ASCII is refused
because a look-alike host (`exämple.com`) is not the host it resembles.

## What the reader does (`resolveurl.py`)

In order, the first that has an answer wins:

1. **ID pages** (`ID_PAGES`), step detail `list page` or `id in path`. The
   ID must be on the List; an exception's page is refused. A ScanCode key
   that folds to the SPDX ID of another licence (`SCANCODE_NOT_SPDX`, 13
   keys, from ScanCode's `index.json` on 2026-11-08) is not read as that ID.
   On `spdx.org/licenses/` only, `<ID>+` is the ID with its `+` (S4).
2. **Pages that offer a choice** (`DUAL_PAGES`, 2 entries): refused (S5).
3. **The List's `seeAlso`**, detail `see also`. One licence, or a licence
   and the ID it was renamed to (`StandardML-NJ` and `SMLNJ`), is that
   licence. A page that names `X`, `X-only` and `X-or-later` is the **family
   rule**: the bare deprecated `X`, `assumed_only` with both candidates, as
   the bare ID is read (`gnu.org/licenses/gpl-3.0.html` is `GPL-3.0`). Several
   other licences: `url names several licences: <IDs>`. Exceptions only:
   `url names an exception: <IDs>`. A licence and an exception: `url names a
   licence with an exception: <IDs>`, unless each licence is an old ID of
   both (S2).
4. **Aliases** (`URL_ALIASES`, 11 entries), detail `alias`: pages the List
   lacks (7, each declared by three packages or more and shown to name one
   licence and version) and pages the List gives a licence with its variants
   (4: `mozilla.org/MPL/2.0`, `opensource.org/license/MPL-2.0`,
   `opensource.org/license/OFL-1.1`, the SIL `OFL_web` page). An alias is
   read only where the List gives no page or gives its ID among others.
   Evidence for each: the survey note. `oss.oracle.com/licenses/cddl+gpl-1.1`
   was left out: the name says a dual licence.

Each answer is a `license_url` step to the ID, then the steps of the ID read
alone (`resolvetable.read_as`): a rename and a deprecation read as they do
for the ID. One pair of angle brackets round the URL comes off first
(`brackets` step).

**Fragment rule.** A List URL with a fragment names a place on a page
(`fragment_page_key`): its owner is an owner of the page only beside the
owners of the page itself, so `gpl-faq.html#FontException` does not make
`gpl-faq.html` a licence's page (B1). A fragment of a declared URL is
dropped as in every key.

## Data model

The `license_urls` table (`owner_id`, `is_exception`, `url`) keeps the
List's pages as written, in List order, licences then exceptions; the key is
computed in memory (`ListLookup.get_ids_by_url(key)`, one index per key
function), so a change to the key needs no rebuild. `records.BUILD_VERSION`
is now `"4"`: a database of build 3 or older warns `build vN outdated` and
`update` rebuilds it. The packaged index (`listindex.py`) builds the same
index from the shipped bundle. `tests/fixtures/license-list/spdx-see-also.json`
holds the pages of 3.29.0 for the tests.

## Measured on List 3.29.0

From `spdx-see-also.json`, with `urlkey.url_key` and
`resolveurl.list_url_key`:

- 997 licence rows, 910 distinct URLs, 861 distinct keys; 25 URLs give no
  key (web.archive.org copies with a second `//`, among them).
- 133 licence URLs have a fragment and are not indexed: 751 keys of
  licences remain, 709 of them name one licence and 42 name several.
- With the exceptions: 1,125 rows, 1,030 distinct URLs, 971 keys, 829 keys
  indexed.

After the review fixes, `resolve()` on the 829 pages
(`tests/test_resolver_url_data.py`): 702 one licence, 1 rename, 15
families, 4 aliases, 27 several licences, 78 exceptions only, 2 a licence
with an exception. Of the 172 List URLs with a fragment, as written, 167
name nothing and 5 are refused as several licences. Of the 740 licence IDs
with a `+` on the List's page, 700 read and 40 (an ID that ends in
`-only`, `-or-later` or `+`) name nothing.

## Counts in the survey

Maven: 962 of 1,000 packages state a URL and the List reads 83% of them
(800: `list page` plus `see also`). NuGet: 182 of 300 state a
`licenses.nuget.org/<ID>`. npm, PyPI and crates.io top 300: no URL as a
licence value. Details and the unread keys are in the survey note.

## NuGet expression paths (issue #187, 2026-11-09)

`licenseUrl` of a NuGet package that declares a licence expression is
`https://licenses.nuget.org/` and the expression as the path. Source:
<https://learn.microsoft.com/en-ie/nuget/nuget-org/licenses.nuget.org>
(a space is `%20`; `(`, `)` and `+` stay as written; the service is case
sensitive). The survey had 1 of 183 such URLs as a compound
(`MS-PL OR Apache-2.0`); a package on the live service has
`(MIT)%20OR%20ISC`. `nugetpath.py` reads it:

- **The path is another licence expression, URL-encoded.** It is decoded
  for the host `licenses.nuget.org` only, every `%XX` once, in one pass.
  The decoded text must then match the expression character set,
  `[A-Za-z0-9.+()-]`, words one space apart. That set, not a list of
  allowed escapes, refuses `%2F`, `%3F`, `%23`, `%3B`, `%00`, `%0A`,
  `%7F`, `%C2%A0` and a doubled `%2520` (it decodes to `%20`, and `%` is
  outside the set). `%4D` is an `M` and is read, which is harmless.
  `urlkey.url_key` still decodes nothing (`tests/test_urlkey.py` pins it).
- **Rejected: an allow-list of escapes** (`%20`, `%28`, `%29`, `%2B`): it
  needs a second list to keep in step with the first.
- **Operators are upper case**, as the service is case sensitive; IDs are
  read case-folded as the ID alone is (`/mit` reads). A word is a List
  licence or, after `WITH`, an exception. A phrase (`or later`), a
  `LicenseRef-*`, `UNLICENSED` and an unknown ID name nothing here
  (`not found`); a qualifier the grammar refuses (`GPL-2.0-only+`,
  `MIT++`) and a broken expression (`(MIT`, `MIT%20OR`) are refused with the
  reason `resolve()` gives the decoded text.
- **The ID page comes first.** `/MIT`, `/mit`, `/GPL-2.0+` and
  `/FLTK-exception` keep their answers; `/MIT+` was `not found` and is
  `MIT+` now (detail `expression in path`).
- **One operand per URL**, text and span the URL's, expression the whole
  result (as one part of a `;` list is). A URL of an expression as an
  operand of a compound is refused, `operand names an expression`, since
  the leaf reader gives one licence. Two URLs of one licence each join
  (`.../MIT OR .../ISC`).
- **The reader is in `nugetpath.py`, not in `resolvecompound`**, which
  imports `resolveurl`: a static cycle fails pylint R0401. It uses
  `resolveleaf.read_leaf` and `exprcanon`, as the compound reader does.
- **A tag word keeps its precedence**: `url_license_id` returns
  `(A OR B)` for a compound, so `ISC AND <url>` is `ISC AND (A OR B)`. This
  is a new, pinned difference from `resolve()`, which refuses that value.
- Not read: a bracketed path with raw spaces
  (`.../(MIT) OR ISC`) and a URL over 2,048 characters.

## Deferred

- A URL inside prose (`see https://...`).
- GNU pages that could not be fetched during the survey (no alias without a
  check of the page); project statement pages (`asm.ow2.io/license`, ...)
  until a body check shows one licence.
- Moving the rest of a tag's and a field's value to `resolve()` (0.8).

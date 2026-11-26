---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The result of `resolve()`

What `licenseid.resolve()` reads in a declared licence value and what it
returns: every field, the categories and their trust, the reasons for a
refusal, and how quote marks are read. The
[Python API](python-api.md) shows how to call it. A value that is not
a `str` (`None`, bytes, a number) raises `TypeError` before any list is
read, as does a `db` that is neither a `LicenseDatabase` nor the path of
one (a `str` or `os.PathLike`); a blank path raises `InvalidInputError`
(`database: missing: db`). A path is opened read-only, and every database
is checked ready before it is read: a missing file raises
`DatabaseNotReadyError` (`not found`) and is never created.

`detect()` reads a whole input with `resolve()` first:
[how `detect()` uses `resolve()`](#how-detect-uses-resolve) says what it
answers, and what it does with a value `resolve()` refuses.

## What `resolve()` reads

`resolve()` turns one declared licence value into an SPDX expression and the
steps taken, without fuzzy matching. The lists it reads besides the SPDX
License List (BSD names, titles, classifier names, licence URLs) and its named
rules (T1 to T3, P1 to P3) are published, row by row, in [the lists
page](lists.md):

- with no database it reads the SPDX License List shipped in the wheel, in
  memory, and gives the answer a database built from that list gives;
  with both, the newer List wins, and a tie goes to the database only if
  this licenseid's build rules made its rows (`source=` picks one);
- exact and case-folded IDs; loosely written IDs (`Apache2`, `GPLv3`,
  `GPLv2 or any later version`); a bare major the List has another minor
  of names none of them and is refused, `version ambiguous` (`Apache-1`,
  `LGPLv2`; `Apache 2` and `Apache-1.1` are read, and so are `Apache-1+`,
  `LGPLv2+` and `LGPLv2 or later`, as a grant covers every later minor; the
  trove classifier `(LGPLv2)` stays `LGPL-2.0`, from its table); the
  List's own licence names, where a run of white space reads as one space
  (`MIT  License` is `MIT`, `listed_name`); "or later"
  on an ID with no `-or-later` form is the `+` operator (`MIT or later` is
  `MIT+`, `Apache 2.0 or later` is `Apache-2.0+`). "or" in a grant is a word
  of its own (`MIT ora later` is not found). Between an ID and its grant
  only white space (any, a no-break space too), one `.` or `,`, a `(` or
  `[` before the "or", a dash between words, and one dash or `_` glued to the
  ID may stand (`GPL-2.0 - or - later`, `GPL-2.0- or later` are
  `GPL-2.0-or-later`, category `separator`); any other mark is refused
  (`MIT; or later`, `GPL-2.0-- or later`: `character dropped`).
  A "+" after a space is no operator (`GPL-2.0 +`: `plus after a space`).
  Keywords ignore case in ASCII only (`MIT WİTH X` is not found). A
  `LicenseRef-`, `DocumentRef-` or `AdditionRef-` prefix is written in SPDX's
  case (`licenseref-foo` is `LicenseRef-foo`, an `id_case` step; the rest of
  the ID is kept as written);
- a bare deprecated ID (`GPL-3.0`) comes back as written, category
  `assumed_only`, with both candidates, never narrowed; a renamed one
  (`StandardML-NJ`) becomes its successor (`SMLNJ`);
- quote marks around the whole value are taken off (`"MIT"`, `'MIT'`,
  `“MIT”`, `«MIT»`, `「MIT」`, one or several layers, as an `unquote` step), and the
  inside is read as it would be alone; a mark on one end only (`"MIT`) is
  read too, as a weaker answer (`separator`); one end mark after the
  closing marks (`"MIT".`) is an ending; marks of two kinds
  (`"MIT'`) or inside the value (`Apache "2.0"`) are not read;
- a loose reading never drops a character that says something:
  `Apache 2.0?`, `MIT*` and `"MIT?"` are `unresolved`, with a
  `reason` and a `drop` step that was not applied; white space, `-`, `_`,
  `.`, a dash and one trailing comma are still dropped, but not a dash or
  `_` joined to the end of the ID (`MIT-`, `GPL-2.0-`: a cut value, as at
  the start; a tag too: `SPDX-License-Identifier: MIT-` has no answer). So is
  no word:
  a list or comment marker (`REM MIT`, `1. MIT`, `iv. MIT`) is refused
  with `word dropped: rem`. At the end of a value one `.`, `,`, `;` or
  `:`, with white space around it, is an ending and is left off (`MIT;`,
  `(MIT).`, `The Unlicense.`, `MIT License :`; a `separator` step, detail
  `end mark`, before the reading), also after an "or later" grant (`MIT or
  later;` is `MIT+`, `separator`, not exact). A run of end marks after a
  grant (`MIT or later..`, `MIT or later.;`) is refused as `MIT;;` is,
  `character dropped: U+002E`, in the argument and a JSON field too (a
  licence name in a field, `GNU General Public License v2.0 or later..`, is
  still read: a known gap); a tag still reads it (it runs on into prose).
  A closing bracket after a grant passes and ends a run (`MIT or later.)` is
  `MIT+`, with no step and exact: a known gap; `MIT or later.).` is read).
  Two or more marks otherwise, an ellipsis and a lone dash (`MIT;;`, `MIT...`,
  `MIT…`, `MIT -`) are refused, also after a `+`, an exception, a
  `LicenseRef-*` or a prose form (`MIT+;` is `MIT+`; `GPL-2.0+?`,
  `MIT License -` are refused). At the start nothing is left off: `-- MIT`,
  `; MIT`, `... MIT`, and an ID cut from a longer one (`.GPL-3.0-only`,
  `-MIT`) are refused;
- a zero-width character at either end of the value is white space: U+200B
  zero width space, U+200C zero width non-joiner, U+200D zero width joiner,
  U+2060 word joiner, U+FEFF zero width no-break space (a byte order mark)
  and U+00AD soft hyphen (`MIT\u200b`, `\ufeffMIT`, `"MIT"\u200b`,
  `MIT OR ISC\u200b`). They carry no text and reorder nothing, so they are
  left off as a trimmed space is: one `trim` step with the detail
  `zero-width characters`, category `lexical` at best, `EXACT` yes;
- any other control or format character at either end of the value is left
  off as a cut (`MIT\u202e`, `MIT\x07`, `MIT\x1f`, a run of Unicode tag
  characters, or one of them beside a zero-width one): one `trim` step with
  the detail `invisible characters`, and the answer is `separator` at best
  (`resolver_rule`) and never exact, since a character was dropped that may say
  something: a bidi control can reorder what is shown after the value, a
  separator control may stand for a field that was lost, and tag characters
  are text no one sees. An SPDX tag and a manifest field agree with the
  argument. Nothing that shows is lost at an end: no text stands beyond it for
  a bidirectional control to reorder. A bidi control at the *start*
  (`\u202eMIT`, which shows as `TIM`), a hidden character anywhere inside
  (`M\u200bIT`, `MIT\u200bOR ISC`), a NUL (a sign of binary data) and a value
  of nothing else are still refused (`control or format character`). Inside
  the quote marks around the whole value, a format character that is no bidi
  control is left off the same way (`"MIT\u200b"`: `unquote`, then `trim`); a
  bidi control, a control character or a NUL there stays refused. Inside the
  value, a format character that is no bidi control and touches white space is
  that white space (`MIT OR\u200b ISC`, `MIT\u200b OR ISC`): a second `trim`
  step makes it a space, one code point for one, so the spans still index the
  raw value; the step is a cut, as above, unless every character it made a
  space is zero-width;
  `operands[].span` indexes the raw value, so it counts the characters left
  off at the start. The 2,000 character limit counts the value after that;
- licences joined by a `;` (`MIT ; Apache 2`) name two licences and not how
  they combine (`AND` or `OR`), so the value is `unresolved`, with the
  `reason` `operator not stated: ;` and one operand for each part, each
  read as it would be alone: a caller can still ask whether every one is
  OSI approved. A comma or `/` is not read this way, nor is a `;` that
  ends an operand (`MIT; OR ISC`);
- list IDs joined by a `/` (`MIT/Apache-2.0`, Cargo's way to write `OR`)
  are read as `OR`: `Apache-2.0 OR MIT`, category `separator` at best, with a
  `separator` step (detail `slash as OR`). Every piece must be an ID spelt as
  listed, so a name or a path with a `/` is not read (see
  [IDs joined by a slash](#ids-joined-by-a-slash));
- a compound expression is read operand by operand: one-word operands
  (with `WITH`, `+` or an "or later" grant), each as the same text would be
  read alone, and per operand only a balanced pair of quotes; an operand
  of several words is refused; with the operators in upper case, the
  `reason` is `operand of several words: BSD 3-Clause` for a leaf that
  reads alone, else `operand not resolved: Foo Bar`. The result is written
  in licenseid's canonical order: operators in upper case, a chain of one
  operator flattened, operands sorted (IDs, then `LicenseRef-*`, then
  `WITH`, then bracketed groups), duplicates dropped, and brackets only where
  precedence needs them (`mit or "Apache2"` → `Apache-2.0 OR MIT`);
  `[ ]` and `{ }` count as brackets;
- the PyPI trove classifier names of the `License ::` family are read from
  a table that records what each name states (`GNU General Public License
  v3 or later (GPLv3+)` is `GPL-3.0-or-later`, category `trove_name`);
  a name that writes a version but not "only" or "or later" (`... v3
  (GPLv3)`) is the bare ID, `assumed_only`; a name that names no single
  licence (`BSD License`, `W3C License`) or only by usage (`Apache
  Software License`) stays `unresolved`; a name with no version is
  `unresolved` too, even where the List holds one version (`Common Public
  License`), except `Universal Permissive License (UPL)`, which is
  `UPL-1.0`. The table matches case and
  spacing exactly, except that a name it reads as no licence is refused
  however it is written. A path in its real form
  (`License :: OSI Approved :: MIT License`) is read as its name is
  read alone, with a `trove_path` step;
- a name followed by a parenthesis (`MIT License (MIT)`) is read as the
  name when the name and the parenthesis are each an ID, a List name or
  a prose form (below) and are one expression (`trailing_name` step); if
  they differ, or only one reads, the value is not read. Where the List
  backs both parts this is read before the table, so `Eclipse Public
  License 2.0 (EPL-2.0)` is `listed_name`;
- the title a licence's own text gives itself is read as that licence,
  from a table (category `text_title`, a `text_title` step): `CC0 1.0
  Universal` is `CC0-1.0`, `Mulan PSL v2` is `MulanPSL-2.0`, and the title
  line `GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007` is the bare
  `GPL-3.0`, `assumed_only`, on one line or on two as the text writes it,
  and `CC0` is `CC0-1.0`, the only CC0. Case does not matter, in ASCII
  only, and a run of white space reads as one space;
- another name a BSD licence is known by is read as that licence, from a
  table (category `alias_name`, an `alias_name` step): `New BSD`, `Revised
  BSD`, `Modified BSD`, `3-clause BSD`, `BSD-3`, `BSD 3`, `BSD3`,
  `BSD (3 clause)` and `BSD (3-clause)` are `BSD-3-Clause`;
  `Simplified BSD`, `2-clause BSD` and `Two-clause BSD` are
  `BSD-2-Clause`. Each word is the List's (`BSD 3-Clause "New" or
  "Revised" License`) or the OSI's, or the clause count of the ID. A final `License`
  is read as a prose form (below): `New BSD License` is `New BSD`, and
  `New BSD License (BSD-3-Clause)` is read as a prose form with its short
  form, while `New BSD (BSD-3-Clause)` is not. A name with no clause count
  (`BSD`, `BSD License`), `FreeBSD` (the List's `FreeBSD-DOC` too) and a
  spelling no project declares (`BSD 2`, `BSD 4`) are not read; nor is a
  version (`BSD License v3`). Case does not matter, in ASCII only, and a
  run of white space reads as one space (`New  BSD`);
- a licence URL is read as the licence it names, first of the name readers
  (category `license_url`, a `license_url` step, then the steps of the ID
  read alone, so a rename reads as it does for the ID). A URL is compared by
  a key, not as written: `http` or `https` (or neither, `www.apache.org/...`),
  `www.`, a port, a `#fragment`, a trailing `/`, `index.html` and one `.html`,
  `.htm`, `.txt` or `.php` are dropped, and case is folded; a query is kept.
  What it reads:
  - the List's own page of an ID (`https://spdx.org/licenses/MIT`, with
    `.html` or `.json`) and `spdx:MIT`; the pages of NuGet
    (`licenses.nuget.org/MIT`), choosealicense.com and ScanCode LicenseDB,
    which end in an ID (the `detail` of the step is `list page`, or `id in
    path`). On the List's own page only, an ID and a `+` is read as the ID
    with the `+` is (`spdx:MIT+` is `MIT+`); a `+` the ID cannot take
    (`GPL-2.0-only+`) names nothing;
  - on `licenses.nuget.org`, a path that is a licence expression,
    URL-encoded (NuGet's `licenseUrl` of an expression: `(MIT)`,
    `(Apache-2.0+)`, `MIT%20OR%20Apache-2.0`; detail `expression in path`).
    The path is decoded for that host only, every `%XX` once, and the
    decoded text must hold only letters, digits, `.`, `+`, `-`, brackets and
    single spaces: `%2F`, `%3F`, `%00`, `%C2%A0` and a doubled `%2520` name
    nothing. `AND`, `OR` and `WITH` are in upper case, and each word is a
    licence ID of the List, or an exception ID after `WITH` (a `LicenseRef-*`
    or a loose spelling such as `Apache2` is not). The expression is written
    as `resolve()` writes it
    (`https://licenses.nuget.org/(MIT)%20OR%20ISC` is `ISC OR MIT`). The
    URL is one operand. As an operand of a compound it is refused when it
    names an expression (`ISC AND https://licenses.nuget.org/MIT%20OR%20ISC`:
    `operand names an expression`); a tag reads it as one bracketed word;
  - a page the List gives a licence in `seeAlso`
    (`https://www.apache.org/licenses/LICENSE-2.0`, detail `see also`):
    one licence, or a licence and the ID it was renamed to. The GNU pages
    of a family (`X`, `X-only`, `X-or-later`) are the bare deprecated `X`,
    `assumed_only` with both candidates, as the bare ID is read
    (`https://www.gnu.org/licenses/gpl-3.0.html` is `GPL-3.0`);
  - a small table of pages the List lacks or gives a licence with its
    variants (`https://opensource.org/license/mit-license` is `MIT`,
    `https://www.mozilla.org/MPL/2.0/` is `MPL-2.0`; detail `alias`);
  - one pair of angle brackets round the URL comes off (a `brackets` step),
    and a URL is an operand of a compound (`https://spdx.org/licenses/MIT OR
    ISC`).

  A fragment is dropped from a declared URL: it names a place on a page,
  so a URL with one reads as its page. A List URL with a fragment adds its
  licence to the owners of its page: `Licensing/MIT#enna` and the bare
  `Licensing/MIT` page are both refused, as the List gives that page to
  `mpich2` and its places to three other licences. A page the List gives
  only with a fragment names nothing (`gpl-faq.html`). A page of several
  licences is refused (`url names several licences: Unicode-3.0,
  Unicode-DFS-2016`), and so is a page the List gives one licence that
  offers a choice of several (the GlassFish pages: CDDL-1.1 or GPL 2 with
  the Classpath exception). A page of exceptions is refused
  (`url names an exception: Classpath-exception-2.0`), and so is a page of
  a licence and an exception (`url names a licence with an exception:
  wxWindows, WxWindows-exception-3.1`), unless the licence is one of the
  List's old IDs of both, which is read as it is
  (`https://www.gnu.org/software/classpath/license.html` is the deprecated
  `GPL-2.0-with-classpath-exception`). A URL that names nothing is `not
  found`, and so is a host that is not ASCII, any other scheme, user
  information, an IP address or a port above 65535:
  `https://evil.com/licenses/MIT` names no licence, whatever its path ends
  in, and nor does `https://opensource.org/licenses/<ID>` for an ID the OSI
  does not publish. A URL inside prose is not read;
- the prose form of one licence is read last, as category `prose_form`
  (a `prose_form` step, then the steps of what it reduces to): a final
  `license` or `licence` after a value that names one licence (not after a
  title: `CC0 License` is refused), with a `+`
  or a `WITH` if it has one (`BSD 3-Clause License`, `MIT+ License`), `<name>
  License[,] (Version|v) N` as `<name> N`, or as the List name `<name>
  License N` if both name the same licence (`Apache License, Version 2.0`,
  `Mozilla Public License, Version 2.0`); the word `License` may be left
  out (`Apache Version 2.0`, `Apache, Version 2.0`) and the version put in
  brackets (`Apache License (2.0)`); `Apache Software License` and
  `Academic Free License` with a version are `Apache N` and `AFL-N` (a
  fixed table, and the ID must be listed); `ASL 2.0` stays `unresolved`.
  A leading `The` goes with
  either, or with a List name (`The MIT License`; `The MIT` is not
  read). One mark at the end is left off, as for any value (`MIT
  License.`, `MIT License;`). A name that
  states no licence (`BSD License`, `W3C License`) and a bare family
  (`BSD`) stay `unresolved`, and a prose form is no operand of a
  compound (`BSD 3-Clause License OR MIT`: `operand of several words`);
- a compound is all or nothing: its category is the weakest operand's,
  and one operand that names nothing leaves the whole unresolved, with a
  `reason` naming it, for `OR` as for `AND`: dropping an alternative would
  hand over an expression the author did not write (`GPL-3.0-only OR
  Apache 2.0` would read as `GPL-3.0-only`, and a policy would deny a package
  it should accept). The operands it did read stay in `operands` (see below);
  a mark used as an operator (`MIT | ISC`) is refused, with a `reason`;
- `detect()` holds a tag or a `license` field to the same List: it names only
  IDs on the List or `LicenseRef-*`, so `MIT OR Apache 2.0` gives no answer
  there, as here, nor does a tag with a licence right after a mark
  (`MIT/Apache-2.0`, `MIT, ISC`; a `license` field reads the `/` of IDs, as
  `resolve()` does, and a tag never does; prose such as `MIT, see LICENSE` keeps
  `MIT`), and a bare "or later" after an ID is the grant (`MIT or later` is
  `MIT+`); a tag whose grant an operator follows reads as here
  (`MIT (or later) AND Apache-2.0` is `Apache-2.0 AND MIT+`);
- every result names its category and trust level, each step, the list
  it rests on with its version and where it was read (`database` or
  `packaged`), and the resolver's version (see
  [The whole result](#the-whole-result)).

### Which list, and its warnings

With no database given (`source="auto"`, the default), `resolve()` reads the
database at the default path or the SPDX License List shipped in the wheel,
whichever holds the newer List; a tie goes to the database only if this
licenseid's build rules made its rows (not those of an older or a newer
licenseid). With no database file it reads the shipped list; with a
database that is there but unusable, the shipped list after one warning,
`database: <condition>: <detail>; using packaged data v<version>`.
`source="database"` reads only the database (and raises for one that
cannot answer, as `auto` would call it unusable) and `source="packaged"`
only the shipped list. The answer is the same from either, and
`lists[*].source` says which was read. `licenseid.DatabaseNotReadyError` is
raised only when the chosen list cannot be read: with `auto`, when there is
neither (an editable install ships no list).

The choice is kept while the database file is unchanged (one `stat` per
call, no connection to choose), so a loop over many values is fast. A new,
deleted or updated file is seen at the next call, unless the file system
keeps coarse times (FAT, HFS+) and the update keeps the file's size within
one tick.

A warning is a `licenseid.LicenseIdWarning` given through Python's
`warnings` (see [the Python API](python-api.md#warnings)), never a line written
to standard error: the fallback above, a database built by an older or a
newer licenseid (`database: build v2 outdated: current v6; run 'licenseid
update'`) and an unusable shipped list (`spdx-bundle.json.gz: invalid:
...`). Each is given once per process, not once per value; `licenseid
resolve` prints each as a `WARNING:` line. A database of build 3 or older
has no pages of the List: it still reads an ID page (`spdx:MIT`), but no
other licence URL until `licenseid update` rebuilds it; opening it writes
nothing.

## The whole result

For `resolve("Apache2")` with no database file, as JSON (the versions are
those of one run):

```json
{
  "schema": 2,
  "input": "Apache2",
  "expression": "Apache-2.0",
  "category": "version_spelling",
  "trust": "resolver_rule",
  "steps": [
    {"kind": "separator", "applied": true, "from": "Apache2",
     "to": "Apache-2.0", "list": "spdx-license-list", "detail": null},
    {"kind": "version_spelling", "applied": true, "from": "Apache2",
     "to": "Apache-2.0", "list": "spdx-license-list", "detail": null}
  ],
  "expansions": [],
  "candidates": [],
  "operands": [
    {"text": "Apache2", "span": [0, 7], "expression": "Apache-2.0",
     "category": "version_spelling", "trust": "resolver_rule",
     "steps": ["... the two steps above ..."], "expansions": [],
     "candidates": [], "reason": null}
  ],
  "resolver": {
    "name": "licenseid",
    "version": "0.9.3",
    "url": "https://github.com/bact/licenseid/releases/tag/v0.9.3",
    "purl": "pkg:pypi/licenseid@0.9.3"
  },
  "components": [],
  "lists": [
    {
      "id": "spdx-license-list",
      "name": "SPDX License List",
      "version": "3.29.0",
      "source": "packaged",
      "url": "https://github.com/spdx/license-list-data/releases/tag/v3.29.0",
      "license": "CC0-1.0",
      "provides": ["deprecation", "ids", "names", "texts"],
      "id_authority": true
    }
  ],
  "reason": null
}
```

| Field | What it holds | Example |
| --- | --- | --- |
| `schema` | the version of this shape | `2` |
| `input` | the value as given | `"Apache2"` |
| `expression` | the answer, or `null` | `"Apache-2.0"` |
| `category`, `trust` | how the answer was read ([steps and categories](#steps-and-categories)) | `"version_spelling"`, `"resolver_rule"` |
| `steps`, `expansions` | each change made, and each qualifier added or declined (below) | `{"kind": "separator", ...}` |
| `candidates` | the IDs a bare deprecated ID may mean, sorted | `["GPL-3.0-only", "GPL-3.0-or-later"]` for `GPL-3.0` |
| `operands` | each licence the value names ([operands](#operands-and-components)) | `{"text": "Apache2", ...}` |
| `resolver` | licenseid: `name`, `version`, `url` of its release, `purl` | `"pkg:pypi/licenseid@0.9.3"` |
| `components` | the other tools that took part, with the keys of `resolver` | the parser `py-spdx-license` |
| `lists` | each list the answer rests on: `id`, `name`, `version`, `source` (`database` or `packaged`), `url` of its release, `license` of its data, `provides` (what it gives: `ids`, `names`, `texts`, `deprecation`), `id_authority` (whether it defines IDs) | `"source": "database"` |
| `reason` | why there is no answer ([reasons](#reasons-for-a-refusal)), or `null` | `null` |

A step holds its `kind`, `applied` (false for a step declined or a reading
refused), `from` and `to`, the `id` of the list it rests on in `list`, and
a `detail`, `null` when it has nothing to add (each example gives the
detail in its place):

| Step kind | `detail` | Example value |
| --- | --- | --- |
| `separator` | `end mark`, `slash as OR`, `version brackets` | `MIT;`, `MIT/ISC`, `Apache License (2.0)` |
| `unquote` | `balanced`, `balanced, 2 layers`, `unbalanced, start`, `unbalanced, end` | `"MIT"`, `'"MIT"'`, `"MIT`, `MIT"` |
| `trim` | `zero-width characters`, `invisible characters` | `MIT\u200b`, `MIT\u202e` |
| `prose_form` | `licence word`, `version`, `leading article` | `BSD 3-Clause License`, `Apache License, Version 2.0`, `The MIT License` |
| `stated_qualifier` | `or later stated` | `MIT or later` |
| `license_url` | `list page`, `id in path`, `expression in path`, `see also`, `alias` | `spdx:MIT`, `https://licenses.nuget.org/MIT`, `https://licenses.nuget.org/(MIT)%20OR%20ISC`, `https://www.apache.org/licenses/LICENSE-2.0`, `https://opensource.org/license/mit-license` |
| `drop` | the code points of the marks | `Apache 2.0?`: `U+003F` |

`detect()` gives each of its results `lists` in this same shape, built the
same way: the SPDX License List of the database it read, `source`
`database`.

## The command line

`licenseid resolve VALUE` prints the expression alone, or an empty line
when `expression` is `None` (exit 1); why it is `None` (`reason`) is not
printed. `--json` prints the result whole, as above, as one RFC 8785 object
on one line (the bytes `licenseid.json_line(resolve(value))` gives), with or
without `-v`. With `-v` (`--verbose`), the result is a few `KEY=VALUE` lines,
one data point each, with one tab between the fields (shown here as
`<TAB>`):

<!-- docs-example: skip: a template of the lines -->

```text
EXPRESSION=<expression><TAB>CATEGORY=<category><TAB>TRUST=<trust>
STEP=<kind><TAB>FROM=<from><TAB>TO=<to>
REASON=<reason>
OPERAND=<text><TAB>EXPRESSION=<expression><TAB>CATEGORY=<category>
```

The first line is always there; `EXPRESSION=` is empty for `None`. A `STEP`
line is printed for each step of `steps` that was applied, in order, then for
each of `expansions` that was applied (`GPL-2.0+` has only its
`plus_to_or_later`); a step not applied is not printed, so a refusal shows
its `reason` alone. `REASON` is printed when `reason` is not `None`, and the
`OPERAND` lines (one per operand, in order) only for licences joined by a
`;`, whose reason is `operator not stated: ;`. A value is written as it
is (`FROM=Apache License, Version 2.0`), except a tab, a carriage return, a
line feed and a backslash, written `\t`, `\r`, `\n` and `\\`, and a
character the locale of standard output cannot encode, written `\xHH`,
`\uHHHH` or `\UHHHHHHHH`. So `cut -f` and `awk -F'\t'` split a line into
its fields, and `licenseid.result.read_text_field` gives a value back; `=`
is not escaped, as a key ends at the first one. `--json` is UTF-8 on every
locale. The lines of `licenseid detect` are written the same way.

The first key of a line names its kind, and each maps to the JSON result:

| Text line | Its fields | In the JSON result |
| --- | --- | --- |
| the answer | `EXPRESSION`, `CATEGORY`, `TRUST` | `expression`, `category`, `trust` |
| a step | `STEP`, `FROM`, `TO` | `steps[].kind`, `.from`, `.to`, then `expansions[].kind`, `.from`, `.to` (applied ones only) |
| a refusal | `REASON` | `reason` |
| an operand | `OPERAND`, `EXPRESSION`, `CATEGORY` | `operands[].text`, `.expression`, `.category` |

An empty text value is `null` in JSON. A later release only appends fields
to a line, so read a field by its key; an `EXPRESSION` that is not the first
key of its line is an operand's.

The exit status (0 when `expression` is not `None`, else 1, with no `ERROR`
line), `--source`, `--db` and the values `resolve` leaves to `detect` (a
licence text, `-`, a line break, over 2,000 characters, the name of a file)
are in [the command line reference](cli.md#resolve-a-declared-value).

## Operands and components

`operands` holds each
licence the value names, in the order written: its `text`, its `span`, which
indexes the raw `input` (`[start, end)` in code points; the trim and the
quotes and brackets around the whole fall outside it), and the answer the
same text would get alone (an operand is one word, so a loose ID with a space
is no operand; a part of a value joined by `;`, below, is the exception). A
refused compound keeps them: `GPL-2.0-only OR Commercial` has no `expression`,
and `operands` holds `GPL-2.0-only` (`exact`) and `Commercial` (`unresolved`),
so a consumer can apply its own rule; licenseid gives no partial answer. A
compound adds the steps of the whole after those of its operands, in this
order: `operator_case`, `whitespace`,
`brackets`, `reorder` and `dedupe`, each with the expression before and
after. `components` names the tools besides licenseid that took part (the
expression parser, `py-spdx-license`, whenever it parsed the value: a
compound, read or refused); every step is licenseid's own. A compound's
top-level `candidates` is empty: the candidates of a bare deprecated ID
inside it are its operand's, in `operands[*].candidates` (`GPL-2.0 OR MIT`:
`GPL-2.0-only` and `GPL-2.0-or-later` on its first operand). For
`resolve("GPLv2+ or MIT")`, shortened (the parser's version is that of one
run):

```json
{
  "schema": 2,
  "input": "GPLv2+ or MIT",
  "expression": "GPL-2.0-or-later OR MIT",
  "category": "version_spelling",
  "trust": "resolver_rule",
  "steps": [
    {"kind": "separator", "from": "GPLv2", "to": "GPL-2.0", "...": "..."},
    {"kind": "version_spelling", "from": "GPLv2", "to": "GPL-2.0",
     "...": "..."},
    {"kind": "operator_case", "from": "GPL-2.0-or-later or MIT",
     "to": "GPL-2.0-or-later OR MIT", "list": null, "...": "..."}
  ],
  "expansions": [
    {"kind": "plus_to_or_later", "from": "GPLv2+", "to": "GPL-2.0-or-later",
     "...": "..."}
  ],
  "operands": [
    {"text": "GPLv2+", "span": [0, 6], "expression": "GPL-2.0-or-later",
     "category": "version_spelling", "...": "..."},
    {"text": "MIT", "span": [10, 13], "expression": "MIT",
     "category": "exact", "...": "..."}
  ],
  "components": [
    {"name": "py-spdx-license", "version": "0.0.1",
     "url": "https://pypi.org/project/py-spdx-license/0.0.1/",
     "purl": "pkg:pypi/py-spdx-license@0.0.1"}
  ],
  "reason": null,
  "...": "..."
}
```

## Licences joined by a semicolon

A `;` between licences says there are several and not how they combine:
`MIT ; Apache 2` may be `Apache-2.0 AND MIT` or `Apache-2.0 OR MIT`.
`resolve()` does not choose. The value is `unresolved`, `expression` is
`None`, `reason` is `operator not stated: ;`, and `operands` holds one entry
for each part, in order, each read as the same text would be alone (so a part
that is a compound, `MIT OR ISC`, is read as that compound, and a part that
cannot be read keeps its own category and `reason`). A caller that asks only
whether every licence is OSI approved has an answer whatever the operator.
For `resolve("MIT ; Apache 2")`, shortened:

```json
{
  "input": "MIT ; Apache 2",
  "expression": null,
  "category": "unresolved",
  "trust": "none",
  "operands": [
    {"text": "MIT", "span": [0, 3], "expression": "MIT",
     "category": "exact", "...": "..."},
    {"text": "Apache 2", "span": [6, 14], "expression": "Apache-2.0",
     "category": "version_spelling", "...": "..."}
  ],
  "reason": "operator not stated: ;",
  "...": "..."
}
```

The rule is narrow. The `;` must stand outside brackets, with a non-empty
part on each side: `MIT;;Apache-2.0` and `; MIT` are refused as before, and
one `;` at the very end is an ending (`MIT; ISC;` is two parts). At least two
parts must name a licence, or would but for a mark they drop (`Apache
2.0?`), and one must resolve: `MIT; Copyright (c) 2016` and `-MIT ; -MIT`
stay `unresolved`, with the reason they had. A `;` beside an operator word
(in any case) means one was stated: `MIT; OR ISC` is `ISC OR MIT`, and
`MIT; OR ISC; Apache-2.0` is no list. A value that reads whole as a name
(`MIT; (MIT)`) is read as that name. A comma and `/` are not separators here
(`not an SPDX operator: ,`; a `/` between IDs is read first, below). A part
is not split again, so a `;` in brackets inside a part is not read as a list.
`steps` holds only what was done to the whole before the split (`trim`,
`unquote`, `brackets`).

## IDs joined by a slash

`MIT/Apache-2.0` and `Apache-2.0/MIT` are `Apache-2.0 OR MIT`: Cargo documents
the form, and the crates that declare it are many (`winapi`,
`filetime_creation`, `sourcefile`). The rule is narrow, as a `/` is also in
names and paths.

The whole value must be two or more pieces cut at `/`, with spaces and tabs
around each piece dropped (`MIT / Apache-2.0`), and every piece one of:

- a List licence ID spelt exactly as listed, with a `+` if the "+" rule takes
  one (not after `-only` or `-or-later`): `zlib/libpng` is not read, as case
  would make it `Libpng OR Zlib` and the author means the one licence
  `zlib-acknowledgement`;
- `LicenseRef-` and letters, digits, `.` and `-`, with no `+`.

At least one piece is a List ID, there are at most 150, and no piece is empty
(`MIT//ISC`, `/MIT`, `MIT/`). The value is then read as `A OR B` is: canonical
order, a repeat dropped (`MIT/MIT` is `MIT`), a deprecated ID kept as
`assumed_only`. One `separator` step comes first (`from` the value, `to` the
`OR` form, detail `slash as OR`), then the compound's own; the category is the
weaker of `separator` and the compound's. Each operand is one piece, at its
span in the value.

Anything else keeps its answer. Not read: an operand that is no exact ID
(`MIT/Apache`, `Apache2/MIT`, `BSD/MIT`, `MIT/NONE`), an exception
(`MIT/Classpath-exception-2.0`), only `LicenseRef-*` operands, a `/` that is
not ASCII (U+2215, U+FF0F), a URL or a path (`LICENSE/MIT`,
`opensource.org/licenses/MIT`), and a `/` mixed with another operator or
`;` (`MIT/ISC OR Zlib`, `MIT/ISC; Apache-2.0`). A text that holds the value
(a licence text, a sentence) is not a whole value. A tag never reads a `/`
(its value can run on into prose); a `license` field of `package.json`,
`pyproject.toml`, `Cargo.toml` and `setup.cfg` answers as `resolve()` does,
and lower case in a `Cargo.toml` (`mit/apache-2.0`) is refused. `--id` still
declares one licence.

A value with both IDs of a pair that is one licence under a name with a `/`
is refused, in any order and place (`MIT/X11/ISC`, `X11/MIT`), by a table
(`resolveslash.REFUSED_PAIRS`, with its reasons in
[the lists page](lists.md#ids-joined-by-a-slash)); another pair needs a
measured count. The value is also refused when its `OR` form is over 2,000
characters.

## Steps and categories

`steps` change the value; `expansions` hold a qualifier (`-only`,
`-or-later`) added or, with `applied` false, declined. `null` means nothing
in a step as anywhere: a `list` or `detail` with nothing to say is `null`,
never `""`. A step that rests on a list names it in `list`: the SPDX
License List, or, for `trove_name` and `trove_path`,
`pypi-trove-classifiers` (a second entry of `lists`, naming the classifier
vocabulary of licenseid's table: `provides` `["names"]`, `id_authority`
false, `version` the classifier list read (`2026.9.21.13`), `source` always
`packaged`, even beside a `database` SPDX entry:
find the SPDX list by its `id`, not by position). The
`category` of a result is the weakest of its steps, and of a compound the
weakest of its operands, in this order (strongest first):

| Category | Trust | `EXACT` | The value |
| --- | --- | --- | --- |
| `exact` | `identity` | yes | is a listed ID as written |
| `lexical` | `identity` | yes | differs in case, spacing, brackets, quotes, order, a classifier prefix, an agreeing parenthesis or a zero-width character at an end |
| `listed_name` | `list_data` | yes | is the List's name of a licence |
| `deprecated_equal_successor` | `list_data` | yes | is a renamed deprecated ID |
| `plus_to_or_later` | `list_data` | yes | is `X+`, read as `X-or-later` |
| `stated_qualifier` | `author_words` | yes | states "or later" in words |
| `separator` | `resolver_rule` | no | is an ID with other separators, or with another hidden character at an end |
| `version_spelling` | `resolver_rule` | no | is an ID with its version re-spelt |
| `prose_form` | `resolver_rule` | no | is an ID in a prose form (`BSD 3-Clause License`, `Apache License, Version 2.0`) |
| `text_title` | `resolver_rule` | yes | is the title a licence's text gives itself (`CC0 1.0 Universal`) |
| `alias_name` | `resolver_rule` | yes | is another name of a BSD licence (`New BSD`, `BSD-3`) |
| `license_url` | `resolver_rule` | yes | is the URL of a licence (`https://spdx.org/licenses/MIT`, `spdx:MIT`, a page the List gives it) |
| `trove_name` | `resolver_rule` | yes | is a PyPI trove classifier name that states one licence |
| `deprecated_ambiguous` | `list_data` | yes | is deprecated, with no successor |
| `assumed_only` | `none` | yes | is a bare split ID (`GPL-3.0`), kept |
| `malformed` | `none` | — | states a qualifier twice, or breaks the grammar |
| `unresolved` | `none` | — | names no licence |

A consumer ignores a step kind it does not know.

The category `exact` is not the `exact` of `detect()`. Here it says the
value was the listed ID as written, with no step; `detect()`'s `exact` says
of one result that it was found exactly (declared, a name in full, or the
whole licence text). The `EXACT` column says which categories
`detect()` calls exact for a declared value: where a list defines the reading
it is exact, where a rewrite rule (`separator`, `prose_form`,
`version_spelling`) made it, it is not; a compound is exact when every operand
is. A bare `GPL-2.0` kept as written is exact (the answer is the declaration;
`variant_stated` says it is ambiguous). Four exceptions to the column. A
value that was cut is not exact, whatever its category: an end mark left
off (a `separator` step, detail `end mark`: `New BSD.`, `GPL-3.0;`,
`spdx:MIT.`), a quote mark with no pair (`unquote`, detail `unbalanced`:
`"GPL-2.0 OR MIT`) or a hidden character that is not zero-width (`trim`,
detail `invisible characters`: `CC0 1.0 Universal\u202e`). An ID that a rule
re-spelt is not exact although it is kept (`GPL2`, `assumed_only`), nor is a
deprecated `-with-` ID a rule re-spelt (`GPL v2 with classpath exception`,
`deprecated_ambiguous`). IDs joined by a slash (`MIT/Apache-2.0`,
`separator`) are exact. So `detect("GPL-2.0")` and `resolve("GPL-2.0")`
agree: `GPL-2.0`, `assumed_only`; only `detect(..., variant="only")` narrows
it to `GPL-2.0-only`, not exact, with a warning.

## How `detect()` uses `resolve()`

`detect()` asks `resolve()` first for the whole input (an argument, `--text`,
standard input, a file, `detect(text=...)`): when it names an expression,
that is `detect()`'s answer, in the same order (method `name` when a step
read a name, else `id`; exact as [the `EXACT` column](#steps-and-categories)
says). A bare deprecated ID stays as written, as here; only `variant="only"`
or `"or-later"` narrows it, a choice that is not exact, in the detector's
order, as for a tag (`MirOS OR MIT OR GPL-2.0` is `GPL-2.0-only OR MIT OR
MirOS`). A value `resolve()` refuses goes on as follows:

- a value that is an expression but for a "+" after `-only` or `-or-later`
  (`GPL-2.0-only+`) or "+" signs at its end that are no operator (`MIT +`,
  `MIT++`, `(MIT)+`) is not matched as text. Under 10 words it warns `input:
  too few words for text: <reason>` (`qualifier stated twice: MIT++`; `C++`,
  `g++` and `Notepad++` are such values too); a longer one has no warning;
- a URL is no text to match: no answer, with the warning `input: too few
  words for text: <reason>`;
- any other value under 10 words is not matched as text (Chinese and
  Japanese, written without spaces, are matched at any length). A licence
  name or ID in it can still answer, except where `normalize_text` would
  drop what it was refused for: a mark or a word (`Apache 2.0?`), an
  unpaired bracket (`(MIT`) or a "+" that is no operator (`"MIT++"`,
  `MIT License++`, `Apache 2.0 +`, `GPL-2.0 (+)`; not `C++`). With no
  answer it warns `input: too few words for text: <reason>` (`not found: GNU
  GPL v2`), unless the input has no word.

A tag and a manifest field have readers of their own, which put a compound
in the detector's order (`MIT OR MirOS`) and read no title and no BSD alias
(`SPDX-License-Identifier: CC0` has no answer); a field they do not take (a
quoted INI value, a title, a name) is read by `resolve()`. Both read a
licence URL with the reader of `resolve()`, in any word of the value
(`SPDX-License-Identifier: https://spdx.org/licenses/MIT` is `MIT`), and a
tag's grant followed by an operator as `resolve()` does (above).

## Reasons for a refusal

`reason` is `None` unless the value was refused; every refusal has one, the
whole value's and each refused operand's. It is one line, `CONDITION[: DETAIL]`.
Once no reader has a reason of its own, it is `empty` (nothing once trimmed and
unquoted: `""`, `' '`, `"".`), `too long: <N> characters` (over 2,000), `special
value: NONE` or `special value: NOASSERTION` (as the SPDX specification writes
them; `none` is not one), `exception not found: <exception>` (the licence before
`WITH` reads, the words after it are no listed exception; with an `AND` or `OR`
in capitals after them, or a listed exception and more words, it is `not found:
<value>`), else `not found: <value>`. A qualifier the grammar refuses says
which: `qualifier stated twice: GPL-2.0-only+` (also `MIT++`), `qualifier on a
reference: LicenseRef-x+` (also `LicenseRef-x or later`, and `LicenseRef-a+-`: a
malformed core has its own reason), `plus after a space: GPL-2.0 +`, `plus after
an exception: MIT WITH Classpath-exception-2.0+` (also `++`) and `plus after a
bracket: (MIT)+` (also in a compound, `(MIT)+ OR ISC`). The readers' own
reasons, the detail of a mark in code points: `character dropped: U+003F` (the
value would be read as a licence only by dropping a mark that is not a
separator, such as `?`, `!`, `*` or a quote inside the value, a mark at the
start, two or more at the end, or a lone dash, or a dash or underscore joined to
the end of an ID (`MIT-`, `GPL-2.0 or later-`; two or more before a grant,
`GPL-2.0-- or later`), a `+`, an exception or a prose form: `MIT+-`,
`MIT+-?`, `MIT License--`, `MIT License_`; several are space separated, in the
order they stand, `U+002D U+003F`), `word dropped: rem 1` (a comment or list
marker that the reading would drop, in lower case), `lone surrogate`, `control
or format character: U+200B` (U+001C to U+001F too: they are not white space;
refused inside the value, as a first bidi control, as a NUL and alone, but left
off at an end, above; `input` shows a lone surrogate as U+FFFD); for a compound,
`operand not resolved: <operand>` (or that operand's own reason), `operand of
several words: <leaf>` (a leaf that reads alone, as `BSD 3-Clause` does), `not
an SPDX operator: /` (also `|`, `&` and `,` between IDs, a `/` between pieces
that are not all exact IDs, and `;` when fewer than
two parts name a licence: `MIT; Foo`), `operator not stated: ;` (above), `url
names several licences: <IDs>` (sorted; a page the List gives to unrelated
licences, or one that offers a choice), `url names an exception: <IDs>` (a page
of exceptions only), `url names a licence with an exception: <licence IDs>,
<exception IDs>` (each sorted; a page of both), `version ambiguous: <IDs>`
(sorted: the IDs a cut ID may mean, `Apache-1` giving `Apache-1.0,
Apache-1.1`; cut at 60 characters; given only when the cut is the value's first
fault: `LGPL-2 WITH Classpath-exception-2.0+` is `plus after an exception`, and
`LGPLv2 or above`, prose, is `not found`), `parse failed: <the parser's
message>`, `mismatched brackets` (a bracket pairs only with the same kind:
`(MIT]`), `too many operators` (over 150) and `too deeply nested` (over 150). A
value with a part of several words (`Apache License 2.0 OR MIT`) is no compound,
but, when its operators are in upper case, its reason names the first operand
refused: `operand of several words: <leaf>` if that leaf reads alone, else
`operand not resolved: <leaf>`. An operand that reads as an expression of
several licences (a `licenses.nuget.org` URL of `MIT OR ISC`) is refused,
`operand names an expression: <operand>`. A detail taken from the input is
folded to one line and cut at 60 characters. One with a lower-case `or` or `and`
whose words name nothing (`GPL-3.0 or higher`) is prose: `not found: GPL-3.0 or
higher`, unless an operand has its own (a dropped mark). A refused value is
category `unresolved` with no expression, or `malformed` when the compound
breaks the grammar but names a licence (`MIT AND`). For a dropped mark, `steps`
holds one `drop` step with `applied` false: its `to` is the listed ID the loose
reading named (`resolve("Apache 2.0?")` would have read `Apache-2.0`; a renamed
ID is not followed) and its `detail` the code points. White space, `_`, `.`, a
dash (the hyphen-minus, the Unicode hyphens and dashes and the minus sign) and
one `.` or `,` at the end are not marks; nor is one `;` or `:` there, which is
an ending left off. The same holds after a `+`, an exception or a `LicenseRef-*`
(`MIT+;` is `MIT+`; `GPL-2.0+?` is refused). A dot or dash that ends a
`LicenseRef-*`, `AdditionRef-*` or `DocumentRef-*` is part of the ID, so
`LicenseRef-a.;`, `LicenseRef-a-;` and `MIT WITH AdditionRef-x.;` read without
the end mark; `LicenseRef-a;;` is refused. A mark after a bracket, a trove name
or path, or a prose form in brackets that is not one ending is named: `(MIT)-`
and `MIT License (MIT)-` are `character dropped: U+002D`, `"(MIT;)".` is
`character dropped: U+003B U+002E`, and quote marks around a bracketed operand
(`"(MIT)" OR Zlib`) are `character dropped: U+0022`. One end mark after
brackets, a trove name or path or a listed name is an ending (`(MIT).`, `Apache
License 2.0.`). A `reason` keeps the `;` of the value it names (`not found:
Foo;Bar baz`); only the diagnostic lines of the CLI turn it into `,`. A lone
bracket or slash at an end (`(MIT`, `MIT)`, `/MIT`, `MIT/`) is refused: it is a
piece of a cut compound or list. A lone quote mark is read (`"MIT`). A value
that is only quote marks, with or without an ending or a `+` (`"".`, `""+`), is
`empty`.

## Quote marks

Quote marks that delimit the whole value are not marks of that kind: the
`unquote` step takes them off first. Two marks of one kind, double
(`"`, `“ ”`, `„ “`, `« »`; the corner brackets `「」` and `『』` quote too, but
only as a pair, opener first) or single (`'`, `‘ ’`, `‹ ›`, the grave accent
and the other quotes `normalize_text` folds), delimit it, whichever
opens; nested pairs (`'"MIT"'`) all come off, with `detail` `balanced, 2
layers`. A quotation mark on one end only is taken off too, with `detail`
`unbalanced, start` or `unbalanced, end`; the answer is `separator` at best
(`resolver_rule`) and not exact, because the value may be cut:
`"MIT'"` is read, `"MIT'` (two kinds) is not. A prime or a modifier letter
(`GPL-2.0′`) is never taken off alone. The marks around each operand of a
compound come off too (`"MIT" or "Apache-2.0"`), a balanced pair only. The
marks of two kinds (`"MIT'`), or inside a word (`Apache "2.0"`), stay, and
the value is refused as above. One `.`, `,`, `;` or `:` after the closing
marks (`"MIT".`, `'MIT';`) is an ending: a `separator` step comes first, then
`unquote`. The marks may be on one end only (`MIT".`, `Apache-2.0'.`). Two
marks (`"MIT"..`), or a mark inside the quote marks as well, even behind a
bracket (`"MIT.".`, `"(MIT;)".`), are refused.
A format character inside the marks, at an end of the value they quote, is left
off after `unquote`, as it is outside them (`"MIT\u200b"`: a `trim` step, see
the characters at the ends above): white space if it is zero-width (`lexical`
at best), else a cut (`separator` at best, not exact). With a mark inside as well
as one after the quotes (`"MIT.\u200b".`) the value is still refused.
An apostrophe inside a word (`AMD's`) is not a
mark.

---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The values `resolve()` reads

What `licenseid.resolve()` accepts as a declared licence value (IDs, names,
titles, URLs, licences joined by `;` or `/`), how quote marks are read, and
which list it reads. [The result of `resolve()`](resolve.md) holds the fields,
categories, trust and refusal reasons; [the lists page](lists.md) holds the
lists it reads.

## What `resolve()` reads

`resolve()` turns one declared licence value into an SPDX expression and the
steps taken, without fuzzy matching. The lists it reads besides the SPDX
License List (BSD names, titles, classifier names, licence URLs) and its named
rules (T1 to T3, P1 to P3) are published, row by row, in [the lists
page](lists.md):

- with no database it reads the SPDX License List shipped in the wheel, in
  memory, and gives the answer a database built from that list gives;
  with both, the newer List wins, and a tie goes to the database unless a
  newer licenseid built it (`source=` picks one);
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
  it should accept). The operands it did read stay in `operands` (see
  [operands](resolve.md#operands-and-components));
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
  [The whole result](resolve.md#the-whole-result)).

### Which list, and its warnings

With no database given (`source="auto"`, the default), `resolve()` reads the
database at the default path or the SPDX License List shipped in the wheel,
whichever holds the newer List; a tie goes to the database unless a newer
licenseid built it. With no database file it reads the shipped list; with a
database that is there but unusable, the shipped list after one warning,
`database: <condition>: <detail>; using packaged data v<version>`. A database an
older licenseid built is unusable, whatever List it holds (`database: build v7
outdated: current v10; using packaged data v3.29.0`), as an empty one is, until
`licenseid update` builds it again. So is one a newer licenseid built in a shape
this version cannot read (`database: build v11 newer: current v10; using
packaged data v3.29.0`). `source="database"` reads only the database (and raises
for one that cannot answer, as `auto` would call it unusable) and
`source="packaged"` only the shipped list. The answer is the same from either,
and `lists[*].source` says which was read. `licenseid.DatabaseNotReadyError` is
raised only when the chosen list cannot be read: with `auto`, when there is
neither (an editable install ships no list).

The choice is kept while the database file is unchanged (one `stat` per
call, no connection to choose), so a loop over many values is fast. A new,
deleted or updated file is seen at the next call, unless the file system
keeps coarse times (FAT, HFS+) and the update keeps the file's size within
one tick.

A warning is a `licenseid.LicenseIdWarning` given through Python's `warnings`
(see [the Python API](python-api.md#warnings)), never a line written to standard
error: the fallback above, a database built by a newer licenseid (`database:
build v11 newer: current v10`) and an unusable shipped list
(`spdx-bundle.json.gz: invalid: ...`). Each is given once per process, not once
per value; `licenseid resolve` prints each as a `WARNING:` line. Opening a
database writes nothing.

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
weaker of `separator` and the compound's. Each operand is one piece, at its span
in the value.

Anything else keeps its answer. Not read: an operand that is no exact ID
(`MIT/Apache`, `Apache2/MIT`, `BSD/MIT`, `MIT/NONE`), an exception
(`MIT/Classpath-exception-2.0`), only `LicenseRef-*` operands, a `/` that is not
ASCII (U+2215, U+FF0F), a URL or a path (`LICENSE/MIT`,
`opensource.org/licenses/MIT`), and a `/` mixed with another operator or `;`
(`MIT/ISC OR Zlib`, `MIT/ISC; Apache-2.0`). A text that holds the value (a
licence text, a sentence) is not a whole value. A tag never reads a `/` (its
value can run on into prose); a `license` field of `package.json`,
`pyproject.toml`, `Cargo.toml` and `setup.cfg` answers as `resolve()` does, and
lower case in a `Cargo.toml` (`mit/apache-2.0`) is refused. `--id` still
declares one licence.

A value with both IDs of a pair that is one licence under a name with a `/` is
refused, in any order and place (`MIT/X11/ISC`, `X11/MIT`), by a table
(`resolveslash.REFUSED_PAIRS`, with its reasons in [the lists
page](lists.md#ids-joined-by-a-slash)); another pair needs a measured count. A
value of two IDs that is also one List ID with a `/` for its `-` is refused too,
as either may be meant: `HPND/DOC` (`HPND-doc`) and `HPND/Intel` (`HPND-Intel`)
are `character dropped: U+002F`, while `DOC/HPND` is `DOC OR HPND`. The value is
also refused when its `OR` form is over 2,000 characters.

## Quote marks

Quote marks that delimit the whole value are not marks of that kind: the
`unquote` step takes them off first. Two marks of one kind, double (`"`, `“ ”`,
`„ “`, `« »`; the corner brackets `「」` and `『』` quote too, but only as a pair,
opener first) or single (`'`, `‘ ’`, `‹ ›`, the grave accent and the other
quotes `normalize_text` folds), delimit it, whichever opens; nested pairs
(`'"MIT"'`) all come off, with `detail` `balanced, 2 layers`. A quotation mark
on one end only is taken off too, with `detail` `unbalanced, start` or
`unbalanced, end`; the answer is `separator` at best (`resolver_rule`) and not
exact, because the value may be cut: `"MIT'"` is read, `"MIT'` (two kinds) is
not. A prime or a modifier letter (`GPL-2.0′`) is never taken off alone. The
marks around each operand of a compound come off too (`"MIT" or "Apache-2.0"`),
a balanced pair only. The marks of two kinds (`"MIT'`), or inside a word
(`Apache "2.0"`), stay, and the value is refused as above. One `.`, `,`, `;` or
`:` after the closing marks (`"MIT".`, `'MIT';`) is an ending: a `separator`
step comes first, then `unquote`. The marks may be on one end only (`MIT".`,
`Apache-2.0'.`). Two marks (`"MIT"..`), or a mark inside the quote marks as
well, even behind a bracket (`"MIT.".`, `"(MIT;)".`), are refused. A format
character inside the marks, at an end of the value they quote, is left off after
`unquote`, as it is outside them (`"MIT\u200b"`: a `trim` step, see the
characters at the ends above): white space if it is zero-width (`lexical` at
best), else a cut (`separator` at best, not exact). With a mark inside as well
as one after the quotes (`"MIT.\u200b".`) the value is still refused. An
apostrophe inside a word (`AMD's`) is not a mark.

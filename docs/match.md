---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The result of `match()`

What `licenseid.match()` reads in a declared licence value and what it
returns: every field, the categories and their trust, the reasons for a
refusal, and how quote marks are read. The
[README](../README.md#python-api) shows how to call it. A value that is not
a `str` (`None`, bytes, a number) raises `TypeError` before any list is
read, as does a `db` that is neither a `LicenseDatabase` nor the path of
one (a `str` or `os.PathLike`); a blank path raises `InvalidInputError`
(`database: missing: db`). A path is opened read-only, and every database
is checked ready before it is read: a missing file raises
`DatabaseNotReadyError` (`not found`) and is never created.

## What `match()` reads

`match()` turns one declared licence value into an SPDX expression and the
steps taken, without fuzzy matching:

- with no database it reads the SPDX License List shipped in the wheel, in
  memory, and gives the answer a database built from that list gives;
  with both, the newer List wins, and a tie goes to the database only if
  this licenseid's build rules made its rows (`source=` picks one);
- exact and case-folded IDs; loosely written IDs (`Apache2`, `GPLv3`,
  `GPLv2 or any later version`); the List's own licence names; "or later"
  on an ID with no `-or-later` form is the `+` operator (`MIT or later` is
  `MIT+`, `Apache 2.0 or later` is `Apache-2.0+`). "or" in a grant is a word
  of its own (`MIT ora later` is not found). Between an ID and its grant
  only white space, one `.` or `,`, and a `(` or `[` before the "or" may
  stand; any other mark is refused (`MIT; or later`: `character dropped`).
  A "+" after a space is no operator (`GPL-2.0 +`: `plus after a space`).
  Keywords ignore case in ASCII only (`MIT WİTH X` is not found). A
  `LicenseRef-`, `DocumentRef-` or `AdditionRef-` prefix is written in SPDX's
  case (`licenseref-foo` is `LicenseRef-foo`, an `id_case` step; the rest of
  the ID is kept as written);
- a bare deprecated ID (`GPL-3.0`) comes back as written, category
  `assumed_only`, with both candidates, never narrowed; a renamed one
  (`StandardML-NJ`) becomes its successor (`SMLNJ`);
- quote marks around the whole value are taken off (`"MIT"`, `'MIT'`,
  `“MIT”`, `«MIT»`, one or several layers, as an `unquote` step), and the
  inside is read as it would be alone; a mark on one end only (`"MIT`) is
  read too, as a weaker answer (`separator`); one end mark after the
  closing marks (`"MIT".`) is an ending; marks of two kinds
  (`"MIT'`) or inside the value (`Apache "2.0"`) are not read;
- a loose reading never drops a character that says something:
  `Apache 2.0?`, `MIT*` and `"MIT?"` are `unresolved`, with a
  `reason` and a `drop` step that was not applied; white space, `-`, `_`,
  `.`, a dash and one trailing comma are still dropped. So is no word:
  a list or comment marker (`REM MIT`, `1. MIT`, `iv. MIT`) is refused
  with `word dropped: rem`. At the end of a value one `.`, `,`, `;` or
  `:`, with white space around it, is an ending and is left off (`MIT;`,
  `(MIT).`, `The Unlicense.`, `MIT License :`; a `separator` step before the
  reading, as after an ID); two or more marks, an ellipsis
  and a lone dash (`MIT;;`, `MIT...`, `MIT…`, `MIT -`) are refused, also
  after a `+`, an exception, a `LicenseRef-*` or a prose form (`MIT+;` is
  `MIT+`; `GPL-2.0+?`, `MIT License -` are refused). At
  the start nothing is left off: `-- MIT`, `; MIT`, `... MIT`, and an ID
  cut from a longer one (`.GPL-3.0-only`, `-MIT`) are refused;
- licences joined by a `;` (`MIT ; Apache 2`) name two licences and not how
  they combine (`AND` or `OR`), so the value is `unresolved`, with the
  `reason` `operator not stated: ;` and one operand for each part, each
  read as it would be alone: a caller can still ask whether every one is
  OSI approved. A comma or `/` is not read this way, nor is a `;` that
  ends an operand (`MIT; OR ISC`);
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
  Software License`) stays `unresolved`. The table matches case and
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
- the prose form of one licence is read last, as category `prose_form`
  (a `prose_form` step, then the steps of what it reduces to): a final
  `license` or `licence` after a value that names one licence, with a `+`
  or a `WITH` if it has one (`BSD 3-Clause License`, `MIT+ License`), `<name>
  License[,] (Version|v) N` as `<name> N`, or as the List name `<name>
  License N` if both name the same licence (`Apache License, Version 2.0`,
  `Mozilla Public License, Version 2.0`), and a leading `The` with
  either, or with a List name (`The MIT License`; `The MIT` is not
  read). One mark at the end is left off, as for any value (`MIT
  License.`, `MIT License;`). A name that
  states no licence (`BSD License`, `W3C License`) and a bare family
  (`BSD`) stay `unresolved`, and a prose form is no operand of a
  compound (`BSD 3-Clause License OR MIT`: `operand of several words`);
- a compound is all or nothing: its category is the weakest operand's,
  and one operand that names nothing leaves the whole unresolved, with a
  `reason` naming it; a mark used as an operator (`MIT/Apache-2.0`) is
  refused, with a `reason`;
- `detect()` holds a tag or a `license` field to the same List: it names only
  IDs on the List or `LicenseRef-*`, so `MIT OR Apache 2.0` gives no answer
  there, as here, and a bare "or later" after an ID is the grant (`MIT or
  later` is `MIT+`);
- every result names its category and trust level, each step, the list
  it rests on with its version and where it was read (`database` or
  `packaged`), and the resolver's version (see
  [The whole result](#the-whole-result)).

### Which list, and its warnings

With no database given (`source="auto"`, the default), `match()` reads the
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
`warnings` (see the [README](../README.md#warnings)), never a line written
to standard error: the fallback above, a database built by an older or a
newer licenseid (`database: build v2 outdated: current v3; run 'licenseid
update'`) and an unusable shipped list (`spdx-bundle.json.gz: invalid:
...`). Each is given once per process, not once per value; `licenseid
match` prints each as a `WARNING:` line.

## The whole result

For `match("Apache2")`, as JSON:

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
    "version": "0.7.0",
    "url": "https://github.com/bact/licenseid/releases/tag/v0.7.0",
    "purl": "pkg:pypi/licenseid@0.7.0"
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

`detect()` gives each of its results `lists` in this same shape, built the
same way: the SPDX License List of the database it read, `source`
`database`.

## The command line

`licenseid match VALUE` prints this result for one value. `--json` prints
it whole, as above, as one RFC 8785 object on one line (the bytes
`licenseid.json_line(match(value))` gives). Without it, the result
is a few `KEY=VALUE` lines, one data point each, with one tab between
the fields (shown here as `<TAB>`):

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

The exit status is 0 when `expression` is not `None`, 1 when it is `None`
(the lines are still printed, with no `ERROR` line; a `WARNING` about the
database can still come with it), and 2 for a
usage error, a list that cannot be read or a result that cannot be written.
`--source` and `--db` choose the list as `match(value, source=...)` and
`match(value, db)` do; `--db` with `--source packaged` exits 2. A licence
text, `-` (standard input), a value with a line break and one
over 2,000 characters (counted as `match()` counts them, after the
surrounding white space is trimmed) are refused with exit 2, nothing on
standard output and `; run 'licenseid detect'`: `detect` answers those.
The value is read first: one that resolves is answered even when a file or
directory of that name exists, and one that resolves to nothing and names
one is refused the same way (`input: invalid: path: LICENSE`). An empty
argument is `input: empty: argument` and no argument `input: missing; pass
one declared licence value`: `match` never reads standard input. An argument
with U+001C to U+001F is refused as a line break and names it (`invalid:
line break U+001C: MIT`; `--text` of `detect` reads them as white space).

## Operands and components

`schema` is the version of this shape (2 since 0.7.0). `operands` holds each
licence the value names, in the order written: its `text`, its `span`, which
indexes the raw `input` (`[start, end)` in code points; the trim and the
quotes and brackets around the whole fall outside it), and the answer the
same text would get alone (an operand is one word, so a loose ID with a space
is no operand; a part of a value joined by `;`, below, is the exception). A
compound adds the steps of the whole after those of its operands, in this
order: `operator_case`, `whitespace`,
`brackets`, `reorder` and `dedupe`, each with the expression before and
after. `components` names the tools besides licenseid that took part (the
expression parser, `py-spdx-license`, whenever it parsed the value: a
compound, read or refused); every step is licenseid's own. A compound's
top-level `candidates` is empty: the candidates of a bare deprecated ID
inside it are its operand's, in `operands[*].candidates` (`GPL-2.0 OR MIT`:
`GPL-2.0-only` and `GPL-2.0-or-later` on its first operand). For
`match("GPLv2+ or MIT")`, shortened:

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
  "reason": null
}
```

## Licences joined by a semicolon

A `;` between licences says there are several and not how they combine:
`MIT ; Apache 2` may be `Apache-2.0 AND MIT` or `Apache-2.0 OR MIT`.
`match()` does not choose. The value is `unresolved`, `expression` is
`None`, `reason` is `operator not stated: ;`, and `operands` holds one entry
for each part, in order, each read as the same text would be alone (so a part
that is a compound, `MIT OR ISC`, is read as that compound, and a part that
cannot be read keeps its own category and `reason`). A caller that asks only
whether every licence is OSI approved has an answer whatever the operator.
For `match("MIT ; Apache 2")`, shortened:

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
  "reason": "operator not stated: ;"
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
(`not an SPDX operator: ,` and `/`). A part is not split again, so a `;` in
brackets inside a part is not read as a list. `steps` holds only what was done
to the whole before the split (`trim`, `unquote`, `brackets`).

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

| Category | Trust | The value |
| --- | --- | --- |
| `exact` | `identity` | is a listed ID as written |
| `lexical` | `identity` | differs in case, spacing, brackets, quotes, order, a classifier prefix or an agreeing parenthesis |
| `listed_name` | `list_data` | is the List's name of a licence |
| `deprecated_equal_successor` | `list_data` | is a renamed deprecated ID |
| `plus_to_or_later` | `list_data` | is `X+`, read as `X-or-later` |
| `stated_qualifier` | `author_words` | states "or later" in words (`GPL-2.0 or_later` too) |
| `separator` | `resolver_rule` | is an ID with other separators |
| `version_spelling` | `resolver_rule` | is an ID with its version re-spelt |
| `prose_form` | `resolver_rule` | is an ID in a prose form (`BSD 3-Clause License`, `Apache License, Version 2.0`) |
| `trove_name` | `resolver_rule` | is a PyPI trove classifier name that states one licence |
| `deprecated_ambiguous` | `list_data` | is deprecated, with no successor |
| `assumed_only` | `none` | is a bare split ID (`GPL-3.0`), kept |
| `malformed` | `none` | states a qualifier twice, or breaks the grammar |
| `unresolved` | `none` | names no licence |

A consumer ignores a step kind it does not know. Before 0.7.0 a compound
was category `expression`, with no expression; that category is gone.

The category `exact` is not the `exact` of `detect()`. Here it says the
value was the listed ID as written, with no step; `detect()`'s `exact` says
of one result that it was found exactly (declared, a name in full, or the
whole licence text). The two can differ for one value: `detect("GPL-2.0")`
answers `GPL-2.0-only`, not exact, a guess said aloud with a warning, where
`match("GPL-2.0")` keeps `GPL-2.0` as `assumed_only`. Reading `detect()`'s
declared values through `match()` is planned for 0.8.

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
an exception: MIT WITH Classpath-exception-2.0+` and `plus after a bracket:
(MIT)+` (also in a compound, `(MIT)+ OR ISC`). The readers' own reasons, the
detail of a mark in code points: `character dropped: U+003F` (the value would be
read as a licence only by dropping a mark that is not a separator, such as `?`,
`!`, `*` or a quote inside the value, a mark at the start, two or more at the
end, or a lone dash, or a dash or underscore joined to the end of a `+`, an
exception, a `LicenseRef-*` or a prose form: `MIT+-`, `MIT+-?`, `MIT License--`,
`MIT License_`; several are space separated, in the order they stand, `U+002D
U+003F`), `word dropped: rem 1` (a comment or list marker that the reading would
drop, in lower case), `lone surrogate`, `control or format character: U+200B`
(U+001C to U+001F too: they are not white space; `input` shows a lone surrogate
as U+FFFD); for a compound, `operand not resolved: <operand>` (or that operand's
own reason), `operand of several words: <leaf>` (a leaf that reads alone, as
`BSD 3-Clause` does), `not an SPDX operator: /` (also `|`, `&` and `,` between
IDs, and `;` when fewer than two parts name a licence: `MIT; Foo`), `operator
not stated: ;` (above), `parse failed: <the parser's message>`, `mismatched
brackets`, `too many operators` (over 150) and `too deeply nested` (over 150). A
value with a part of several words (`Apache License 2.0 OR MIT`) is no compound,
but, when its operators are in upper case, its reason names the first operand
refused: `operand of several words: <leaf>` if that leaf reads alone, else
`operand not resolved: <leaf>`. A detail taken from the input is folded to one
line and cut at 60 characters. One with a lower-case `or` or `and` whose words
name nothing (`GPL-3.0 or higher`) is prose: `not found: GPL-3.0 or higher`,
unless an operand has its own (a dropped mark). A refused value is category
`unresolved` with no expression, or `malformed` when the compound breaks the
grammar but names a licence (`MIT AND`). For a dropped mark, `steps` holds one
`drop` step with `applied` false: its `to` is the listed ID the loose reading
named (`match("Apache 2.0?")` would have read `Apache-2.0`; a renamed ID is not
followed) and its `detail` the code points. White space, `_`, `.`, a dash (the
hyphen-minus, the Unicode hyphens and dashes and the minus sign) and one `.` or
`,` at the end are not marks; nor is one `;` or `:` there, which is an ending
left off. The same holds after a `+`, an exception or a `LicenseRef-*` (`MIT+;`
is `MIT+`; `GPL-2.0+?` is refused). A dot or dash that ends a `LicenseRef-*`,
`AdditionRef-*` or `DocumentRef-*` is part of the ID, so `LicenseRef-a.;`,
`LicenseRef-a-;` and `MIT WITH AdditionRef-x.;` read without the end mark;
`LicenseRef-a;;` is refused. A mark after a bracket, a trove name or path, or a
prose form in brackets that is not one ending is named: `(MIT)-` and `MIT
License (MIT)-` are `character dropped: U+002D`, `"(MIT;)".` is `character
dropped: U+003B U+002E`, and quote marks around a bracketed operand (`"(MIT)" OR
Zlib`) are `character dropped: U+0022`. One end mark after brackets, a trove
name or path or a listed name is an ending (`(MIT).`, `Apache License 2.0.`). A
`reason` keeps the `;` of the value it names (`not found: Foo;Bar`); only the
diagnostic lines of the CLI turn it into `,`. A value that is only quote marks,
with or without an ending or a `+` (`"".`, `""+`), is `empty`.

## Quote marks

Quote marks that delimit the whole value are not marks of that kind: the
`unquote` step takes them off first. Two marks of one kind, double
(`"`, `“ ”`, `„ “`, `« »`) or single (`'`, `‘ ’`, `‹ ›`, the grave accent
and the other quotes `normalize_text` folds), delimit it, whichever
opens; nested pairs (`'"MIT"'`) all come off, with `detail` `balanced, 2
layers`. A quotation mark on one end only is taken off too, with `detail`
`unbalanced, start` or `unbalanced, end`, and the answer counts as
`separator` (`resolver_rule`), not `lexical`, because the value may be cut:
`"MIT'"` is read, `"MIT'` (two kinds) is not. A prime or a modifier letter
(`GPL-2.0′`) is never taken off alone. The marks around each operand of a
compound come off too (`"MIT" or "Apache-2.0"`), a balanced pair only. The
marks of two kinds (`"MIT'`), or inside a word (`Apache "2.0"`), stay, and
the value is refused as above. One `.`, `,`, `;` or `:` after the closing
marks (`"MIT".`, `'MIT';`) is an ending: a `separator` step comes first, then
`unquote`. The marks may be on one end only (`MIT".`, `Apache-2.0'.`). Two
marks (`"MIT"..`), or a mark inside the quote marks as well, even behind a
bracket (`"MIT.".`, `"(MIT;)".`), are refused.
An apostrophe inside a word (`AMD's`) is not a
mark.

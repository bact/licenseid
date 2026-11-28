---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The result of `resolve()`

What `licenseid.resolve()` returns: every field, the categories and their
trust, and the reasons for a refusal. [The values `resolve()`
reads](resolve-values.md) says what a value may look like and how quote marks
are read. The [Python API](python-api.md) shows how to call it. A value that
is not a `str` (`None`, bytes, a number) raises `TypeError` before any list is
read, as does a `db` that is neither a `LicenseDatabase` nor
the path of one (a `str` or `os.PathLike`); a blank path raises
`InvalidInputError` (`database: missing: db`). A path is opened read-only, and
every database is checked ready before it is read: a missing file raises
`DatabaseNotReadyError` (`not found`) and is never created.

`detect()` reads a whole input with `resolve()` first:
[how `detect()` uses `resolve()`](#how-detect-uses-resolve) says what it
answers, and what it does with a value `resolve()` refuses.

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
    "version": "0.10.0",
    "url": "https://github.com/bact/licenseid/releases/tag/v0.10.0",
    "purl": "pkg:pypi/licenseid@0.10.0"
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
| `resolver` | licenseid: `name`, `version`, `url` of its release, `purl` | `"pkg:pypi/licenseid@0.10.0"` |
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

`operands` holds each licence the value names, in the order written: its `text`,
its `span`, which indexes the raw `input` (`[start, end)` in code points; the
trim and the quotes and brackets around the whole fall outside it), and the
answer the same text would get alone (an operand is one word, so a loose ID with
a space is no operand; a part of a value
[joined by `;`](resolve-values.md#licences-joined-by-a-semicolon) is the
exception). A refused compound keeps them: `GPL-2.0-only OR Commercial` has no
`expression`, and `operands` holds `GPL-2.0-only` (`exact`) and `Commercial`
(`unresolved`), so a consumer can apply its own rule; licenseid gives no partial
answer. A compound adds the steps of the whole after those of its operands, in
this order: `operator_case`, `whitespace`, `brackets`, `reorder` and `dedupe`,
each with the expression before and after. `components` names a tool besides
licenseid only when it took part in the reading: the parser, `py-spdx-license`,
when it parsed the value or a part of it (a value with `AND` or `OR`, read or
refused: `MIT AND`); none for `MIT`, `Apache-2.0 WITH LLVM-exception`, `MIT;
Apache-2.0` or `Apache 2.0 OR MIT` (refused first). Every step is licenseid's
own. A compound's top-level `candidates` is empty: the candidates of a bare
deprecated ID inside it are its operand's, in `operands[*].candidates` (`GPL-2.0
OR MIT`: `GPL-2.0-only` and `GPL-2.0-or-later` on its first operand). For
`resolve("GPLv2+ or MIT")`, shortened (the parser's version is that of one run):

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

A consumer ignores a step kind it does not know. A result's `trust` is that of
its category, so a compound's may be stronger than an operand's, as
`deprecated_ambiguous` comes after the rules: `Apache2 AND
GPL-2.0-with-classpath-exception` is `list_data`, its operand `Apache2`
`resolver_rule` (read `operands[*].trust`). What each level says:

| Trust | A caller may rely on |
| --- | --- |
| `identity` | the expression is the value's own IDs; only their form changed |
| `list_data` | the List's data read it: a name, a successor, `X+`, or a deprecated ID kept |
| `author_words` | the value states the `-only` or `-or-later` form in words |
| `resolver_rule` | a rule of licenseid read the value; `steps` name the rule |
| `none` | no reading: no expression, or a bare ID the List split, kept (`GPL-3.0`, `assumed_only`) with its form unstated |

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
tag's grant followed by an operator as `resolve()` does
([what `resolve()` reads](resolve-values.md#what-resolve-reads)).

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
off at an end ([what `resolve()` reads](resolve-values.md#what-resolve-reads));
`input` shows a lone surrogate as U+FFFD); for a compound,
`operand not resolved: <operand>` (or that operand's own reason), `operand of
several words: <leaf>` (a leaf that reads alone, as `BSD 3-Clause` does), `not
an SPDX operator: /` (also `|`, `&` and `,` between IDs, a `/` between pieces
that are not all exact IDs, and `;` when fewer than
two parts name a licence: `MIT; Foo`), `operator not stated: ;`
([licences joined by a
semicolon](resolve-values.md#licences-joined-by-a-semicolon)), `url
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

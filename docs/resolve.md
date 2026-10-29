---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The result of `resolve()`

What `licenseid.resolve()` returns for a declared licence value: every
field, the categories and their trust, the reasons for a refusal, and how
quote marks are read. The [README](../README.md#python-api) shows how to
call it.

## The whole result

For `resolve("Apache2")`, as JSON:

```json
{
  "schema": 2,
  "input": "Apache2",
  "expression": "Apache-2.0",
  "category": "version_spelling",
  "trust": "resolver_rule",
  "steps": [
    {"kind": "separator", "applied": true, "from": "Apache2",
     "to": "Apache-2.0", "list": "spdx-license-list", "detail": "", "by": ""},
    {"kind": "version_spelling", "applied": true, "from": "Apache2",
     "to": "Apache-2.0", "list": "spdx-license-list", "detail": "", "by": ""}
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
compound, read or refused), and `by` on a step names the one that took it
(`""`: licenseid). For `resolve("GPLv2+ or MIT")`, shortened:

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
     "to": "GPL-2.0-or-later OR MIT", "list": "", "...": "..."}
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
`-or-later`) added or, with `applied` false, declined. A step that rests on a
list names it in `list`: the SPDX License List, or, for `trove_name` and
`trove_path`, `pypi-trove-classifiers` (a second entry of `lists`, naming
the classifier vocabulary of licenseid's table: `provides` `["names"]`,
`id_authority` false, `source` always `packaged`, even beside a `database`
SPDX entry: find the SPDX list by its `id`, not by position). The
`category` of a result is the weakest of its steps, and of a compound the
weakest of its operands, in this order (strongest first):

| Category | Trust | The value |
| --- | --- | --- |
| `exact` | `identity` | is a listed ID as written |
| `lexical` | `identity` | differs in case, spacing, brackets, quotes, order, a classifier prefix or an agreeing parenthesis |
| `listed_name` | `list_data` | is the List's name of a licence |
| `deprecated_equal_successor` | `list_data` | is a renamed deprecated ID |
| `plus_to_or_later` | `list_data` | is `X+`, read as `X-or-later` |
| `stated_qualifier` | `author_words` | states "or later" in words |
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

## Reasons for a refusal

`reason` is `None` unless the value was refused, when it is one line,
`CONDITION[: DETAIL]`, the detail of a mark in code points:
`character dropped: U+003F`
(the value would be read as a licence only by dropping a mark that is not a
separator, such as `?`, `!`, `*` or a quote inside the value, a mark at the
start, two or more at the end, or a lone dash; several are space
separated), `word dropped: rem 1` (a comment or list marker that the reading would drop, in lower case),
`lone surrogate`, `control or format character: U+200B`; for a compound,
`operand not resolved: <operand>` (or that operand's own reason),
`operand of several words: <leaf>` (a leaf that reads alone, as
`BSD 3-Clause` does),
`not an SPDX operator: /` (also `|`, `&` and `,` between IDs, and `;` when
fewer than two parts name a licence: `MIT; Foo`),
`operator not stated: ;` (above),
`parse failed: <the parser's message>`, `mismatched brackets`,
`too many operators` (over 150) and `too deeply nested` (over 150). A value
with a part of several words (`Apache License 2.0 OR MIT`) is no compound,
but, when its operators are in upper case, its reason names the first
operand refused: `operand of several words: <leaf>` if that leaf reads
alone, else `operand not resolved: <leaf>`. A detail taken from the input is
folded to one line and cut at 60 characters. One with a lower-case `or` or
`and` whose words name nothing (`GPL-3.0 or higher`) is prose: no reason,
unless an operand has its own (a dropped mark). A refused value is category
`unresolved` with no expression, or `malformed` when the compound breaks the
grammar but names a licence (`MIT AND`). For a dropped mark, `steps` holds
one `drop` step with `applied` false: its `to` is the listed ID the loose
reading named (`resolve("Apache 2.0?")` would have read `Apache-2.0`; a
renamed ID is not followed) and its `detail` the code points. White space,
`_`, `.`, a dash (the hyphen-minus, the Unicode hyphens and dashes and the
minus sign) and one `.` or `,` at the end are not marks; nor is one `;` or
`:` there, which is an ending left off. The same holds after a `+`, an
exception or a `LicenseRef-*` (`MIT+;` is `MIT+`; `GPL-2.0+?` is refused).

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
the value is refused as above. An apostrophe inside a word (`AMD's`) is not a
mark.

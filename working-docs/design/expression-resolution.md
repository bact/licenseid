---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Expression resolution: one entry point for a declared value

Status: design, unbuilt. Proposed by the maintainer on 2026-10-28; input to a
0.7.0 release and to Pitloom's adoption of it (Pitloom #359 is the interim
state).

See also:
[`../implementation/declared-value-resolver.md`](../implementation/declared-value-resolver.md)
(what 0.6.0 built), [`tech-debt-roadmap.md`](tech-debt-roadmap.md).

## 1. Question

`resolve()` (0.6.0) reads one licence value: `Apache2` is `Apache-2.0`. For a
compound (`Apache2 OR MIT`) it answers category `expression` with no
expression. Pitloom therefore parses and canonicalises compounds itself, with
`py-spdx-license`, beside `licenseid`.

Proposal: `licenseid` calls `py-spdx-license` for the expression grammar and
canonicalisation, and `resolve()` returns the result. A consumer such as
Pitloom then calls only `resolve()` and drops its own use of
`py-spdx-license` at run time.

## 2. Evidence

`licenseid` already depends on `py-spdx-license` (`>=0.0.1,<0.1`).
`normalize_identifier()` already normalises operator case and ids, drops
redundant brackets and sorts through `py_spdx_license` (`identifiers.py`).
Pitloom's only use of the library is one module (`_license_classify.py`).

Probe of 42 values (Pitloom 0.21.0 local parse against
`normalize_identifier()`, 2026-10-28): 29 agree, 13 differ. The 29 include
`+`, `AdditionRef-`, `LicenseRef-`, `WITH`, brackets and case.

| Value | Pitloom today | `normalize_identifier()` | Gap |
| - | - | - | - |
| `MIT OR ISC OR MIT OR ISC` | `ISC OR MIT` | unchanged | `sort()` raises `TypeError` on repeated terms |
| `GPL-3.0`, `GPL-3.0 OR MIT` | as written | `GPL-3.0-only` | it narrows a bare deprecated id |
| `StandardML-NJ` | as written | `SMLNJ` | Pitloom keeps the deprecated id |
| `Apache2 OR MIT` | text | `MIT OR Apache2` | an unresolved operand is kept |
| `GPLv3+ OR MIT` | text | `GPL-3.0-or-later OR MIT` | none (better) |
| `MIT OR Foo`, `MIT AND`, `(MIT`, `MIT/Apache-2.0` | text | unchanged | no category, no reason |

Pitloom's workarounds for the library, which belong with the library user
that owns the grammar: a flat-chain de-duplication for the `sort()` bug, a
gap reader for `+` and `AdditionRef-` (upstream issue 1), and a successor
table for deprecated `+` ids.

## 3. Goals and non-goals

Goals:

1. `resolve()` answers for any single-line value, compound or not, with one
   policy: never narrow a bare deprecated id, rename only a provably equal
   successor, accept all or nothing.
2. The answer depends on the `licenseid` version and the list version, not on
   whether `licenseid update` was run.
3. The result says who did what: which tool, which step, which operand.
4. A consumer needs no second implementation of the grammar.

Non-goals: fuzzy matching in an expression; reading licence text; a new
grammar. Text detection stays in `match()`.

## 4. Design

### 4.1 Compounds in `resolve()`

Tokenise with `py-spdx-license` (operators `AND`, `OR`, `WITH`, brackets).
Resolve each leaf with the single-value code that `resolve()` has today
(`_lookup`), and each `WITH` exception against the exception list. Rebuild the
expression, then canonicalise it (operator case, id case, sorted terms,
repeats removed, redundant brackets dropped).

Acceptance is all or nothing: one unresolved operand makes the value
`unresolved` with `expression` `None`; the operand results still come back.
`Apache2 OR Foo` records nothing, as emitting an invented `LicenseRef-` would.

### 4.2 Result shape (additive)

New keys of `Resolution`:

| Key | Meaning |
| - | - |
| `operands` | one entry per leaf, in input order: `text`, `span` (start, end), `expression`, `category`, `steps`, `expansions`, `candidates` |
| `components` | tools that took part besides `licenseid`: `name`, `version`, `url`, `purl` (`py-spdx-license`) |
| `reason` | one line saying why there is no expression (the parser's message, or `'/' is not an SPDX operator`); `None` otherwise |

New step kinds: `operator_case`, `brackets`, `reorder`, `dedupe`. A step may
carry `by` (`"py-spdx-license"`) where `licenseid` did not do it. A single
value is one operand; its `operands` entry repeats the top-level answer.

Categories: the value's category is its weakest operand's (the 0.6.0 order).
`expression` stops being an outcome: a compound that resolves has the weakest
operand's category (`lexical` for a reorder only). Document the change; the
0.6.0 release is public, but its only known consumer is Pitloom.

### 4.3 Policy

- A bare deprecated id stays as written (`assumed_only`), in a compound too,
  with `candidates` per operand. `normalize_identifier()` is not used for this
  path: it narrows (`GPL-3.0` to `GPL-3.0-only`).
- `deprecated_equal_successor` renames (`StandardML-NJ` to `SMLNJ`), keeping
  the old id in the step.
- `plus_to_or_later` applies per operand, `GPL-2.0+ OR MIT` included.
- A value the grammar cannot parse is `malformed` (broken syntax) or
  `unresolved` (no candidate), with `reason`.

### 4.4 Who is the resolver

`resolver` stays `licenseid`: it is the API the caller invoked and the entity
that decided. Other tools go in `components`, and a step names its tool in
`by`. Setting `resolver` to `py-spdx-license` when only canonicalisation ran
is rejected: a value like `mit or apache2` mixes both tools' decisions, and a
consumer keying on `resolver.name` would see it change from value to value.

Consumer provenance then reads `Tool: licenseid==X` and, when a step has a
`by`, `Tool: py-spdx-license==Y`.

### 4.5 No database

`resolve(value, db=None)` today raises when the database is missing. Change:
fall back to the packaged list bundle (`spdx-bundle.json.gz`, in the wheel),
loaded as an in-memory index. The categories that need only the list
(ids, names, deprecation, `superseded_by`) then work with no database.

- `lists[*].source` says `database` or `packaged`, with the list version.
- When both exist, use the database (it can be newer); say so in `lists`.
- A category that needs the database (fuzzy, text detection) is not part of
  `resolve()`, so nothing is lost.

This removes the environment dependence the consumer saw in review: the same
value gave different SBOM bytes with and without `licenseid update`.

### 4.6 The library's limits

| Limit | Handling |
| - | - |
| `sort()` raises on repeated terms | flat-chain de-duplication first (Pitloom's `_canonical_string`), or a fix upstream |
| `+` and `AdditionRef-` not in the grammar | strip and restore (`plusoperator.strip_plus_operator`), or support upstream (issue 1) |
| quadratic tokeniser on a long token | the existing token and operator caps (`_MAX_CANONICALIZE_OPERATORS`) |
| deep nesting, `RecursionError` | cap the depth; answer `malformed` with a reason |
| single maintainer, 0.0.1 | keep the `<0.1` pin; contribute upstream before vendoring |

### 4.7 Dropped characters

The `separator` step discards any punctuation: `Apache 2.0?` is read as
`Apache-2.0`, and a lone surrogate (U+FFFD) is dropped. That turns the
author's doubt into a claim. Add a step kind `drop` with the dropped
characters, and refuse (category `unresolved`) when a character other than
space, `-`, `_`, `.` and a trailing `,` is dropped. Pitloom guards this itself
today (`_license_resolve._FOLDABLE`); the guard goes when `licenseid` has it.

## 5. The consumer (Pitloom)

After the change, `_classify` is: the early exits that are not licences
(lone surrogates, `NOASSERTION`, `NONE`, `UNKNOWN`, several lines, over 200
characters), then `resolve()`. Accepted categories include `assumed_only` and
`deprecated_ambiguous`, recorded as written. The `Deprecated-License-Id` note
comes from `candidates`; the broken-expression warning from `reason`.

Removed from Pitloom: the strict parse, the gap reader, the successor table
and the direct `py-spdx-license` calls (about 250 lines).
`py-spdx-license` stays a test dependency: a drift-guard test asserts every
accepted answer parses with it.

Behaviour changes for Pitloom, to announce: `StandardML-NJ` becomes `SMLNJ`;
compounds with a respelt operand resolve; the list version comes from
`lists`.

## 6. Migration

| Phase | Change | Exit criterion |
| - | - | - |
| 1 | 0.7.0: packaged-list fallback; compounds; `operands`, `components`, `reason`; the `sort()` workaround; the `drop` step | the 42-value table (section 2) as a parity test: the 29 agreements unchanged, the 13 gaps closed as section 4 says; `resolve()` equal with and without a database for list-only values |
| 2 | Pitloom: floor `licenseid>=0.7.0`, `_classify` on `resolve()`, drift guard | a before/after sweep of Pitloom's licence corpus lists every value whose answer changed, each explained |
| 3 | Pitloom: `Resolution-n` per operand, the list version into the SBOM | per-operand notes in provenance; no `py-spdx-license` import in `src/` |

Budget: under 1 ms per leaf on a built database (0.6 ms today for a single
value); a 50,000-character payload stays under 0.2 s (the 200-character cap).

## 7. Risks and open questions

1. `py-spdx-license` is one person's 0.0.1 library: its open issue 1 and the
   `sort()` bug become `licenseid`'s to carry. Decide: upstream fix, vendor,
   or workaround.
2. Retiring the `expression` category changes 0.6.0 behaviour. Alternative:
   keep it for a compound that resolves nothing and add no new category.
3. Release order is lockstep: `licenseid` first, then Pitloom's floor.
4. `span` offsets are of the stripped input, not the raw value; say so.
5. `StandardML-NJ` to `SMLNJ` follows decision Q7 (replace, keep the old id in
   provenance); confirm it for compounds.
6. Whether a consumer may still ask for the old `normalize_identifier()`
   narrowing (`GPL-3.0-only`): it stays for `match()`, not for `resolve()`.

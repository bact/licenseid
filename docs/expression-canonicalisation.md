---
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# SPDX expression canonicalisation

How licenseid puts an SPDX licence expression in canonical form, rule by
rule, in the order the rules apply. Written for a reviewer and as source
material for a paper. It describes the code at release 0.7.2 plus PR #172
(`main` at commit `7276ee4`).

Every example was run against that code with `licenseid.resolve()` on
2026-11-07. The steps named in each example are the `kind` of the steps in
the result. The reference is the SPDX Specification 3.0.1, Annex D
([SPDX license expressions](https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/)),
read the same day; the version 3.0 address redirects to it. Where the code
differs from the Annex, the rule says so, and
[the last section](#differences-from-the-spdx-specification) collects the
differences.

## What "canonical" means here

The Annex defines no canonical form. It says that `AND` and `OR` are
commutative ("should be considered equivalent"), that precedence is `+`,
`WITH`, `AND`, `OR`, and that brackets override it. It says nothing about
operand order, duplicates, spacing or bracket redundancy. The canonical form
below is therefore licenseid's own convention (decisions D1, Q19, Q21 and
Q24 of the 0.7.0 plan), chosen so that two spellings with the same meaning
give one string. Two properties are tested over a corpus of generated
values: the answer does not depend on the order written
([`test_the_order_written_does_not_change_the_answer`](../tests/test_resolver_compounds.py#L144)),
and canonical form is a fixed point, so resolving an answer gives the same
answer ([`test_every_answer_is_a_fixed_point`](../tests/test_resolver_compounds.py#L121)).

## Two canonical orders in one package

The package holds two canonicalisers, and they do not always agree.

| Used by | Code | Sorts |
| --- | --- | --- |
| `resolve()`, and `detect()` on a whole input | [`exprcanon.canonical`](../src/licenseid/exprcanon.py#L282) | leaves before groups; by rank, then case-folded text |
| A tag or field found inside a file or manifest | [`identifiers._canonicalize_expression`](../src/licenseid/identifiers.py#L680), which calls `py_spdx_license` `sort()` | by that library's own order |

On the same expression they can differ. Run on 2026-11-07:

| Expression | `resolve()` | tag `SPDX-License-Identifier:` |
| --- | --- | --- |
| `Zlib OR MirOS OR MIT` | `MirOS OR MIT OR Zlib` | `MIT OR MirOS OR Zlib` |
| `(MIT AND ISC) OR 0BSD` | `0BSD OR ISC AND MIT` | `ISC AND MIT OR 0BSD` |

Both are valid and equivalent expressions. `docs/resolve.md` states the
difference for guessed `-only` narrowing; this page is about `resolve()`,
which is the order the rest describes. The tag path is in
[`identifiers.py:618`](../src/licenseid/identifiers.py#L618)
(`_normalize_expression`) and is not followed further here.

## The rules, in the order they apply

Stage A prepares the whole value. Stage B cuts it into leaves and reads
each leaf. Stage C parses the shape. Stage D makes the canonical form in
five passes; each pass that changes the text records one step, in this order:
`operator_case`, `whitespace`, `brackets`, `reorder`, `dedupe`.

### Stage A: prepare the whole value

**A0. Leave off hidden characters at the ends.** A control or format character
(categories `Cc` and `Cf`, not white space, not NUL) at the start or end of
the value comes off, with the white space beside it (step `trim`, detail
`invisible characters`; the answer is `separator`, `resolver_rule`). *Reason:*
nothing that shows is lost at an end, since no text stands beyond it for a bidi
control to reorder. A bidi control at the start (`U+202E`, which shows as
`TIM`) is not left off but refused by rule A4. *Source:*
[`hiddenchars.strip_hidden`](../src/licenseid/hiddenchars.py).
*Example:* `MIT\u200b` and `\ufeffMIT` give `MIT`.
Inside the value, a format character (`Cf`, not a bidi control) in a run that
touches white space is made a space, one code point for one
([`hiddenchars.space_out_hidden`](../src/licenseid/hiddenchars.py)): `MIT
OR\u200b ISC` gives `ISC OR MIT`. *Reason:* the run joins no words, since a
space stands beside it. A run between two other characters (`M\u200bIT`), a
control character and a bidi control (`MIT OR\u202e ISC` shows the rest
reversed) are refused by rule A4.
*Test:* [`test_hiddenchars.py`](../tests/test_hiddenchars.py).
*Spec:* not addressed.

**A1. Trim white space.** White space at both ends comes off (step `trim`).
White space is Unicode's `White_Space` property, less U+001C to U+001F
([`WHITE_SPACE`](../src/licenseid/exprtokens.py#L50)).
*Reason:* those four are control characters that `str.isspace()` accepts;
the gate in rule A4 refuses them instead of dropping them. *Source:*
[`resolver.py:306`](../src/licenseid/resolver.py#L306).
*Example:* `' MIT '` gives `MIT`, category `lexical`, steps `trim`.
*Test:* [`test_resolver_end_marks.py:72`](../tests/test_resolver_end_marks.py#L72).
*Spec:* Annex D says "white space" without defining it; no difference found.

**A2. Take off quote marks round the whole value.** `"MIT"` gives `MIT`
(step `unquote`); one end mark after the closing quotes (`"MIT".`) comes off
first (step `separator`). *Reason:* a quote delimits a text and qualifies
nothing, so removing the pair that encloses the whole value drops no word;
marks inside the value are kept for the drop guard to refuse. *Source:*
[`quotes.py`](../src/licenseid/quotes.py),
[`resolver.py:317`](../src/licenseid/resolver.py#L317).
*Test:* [`test_resolver_quotes.py:137`](../tests/test_resolver_quotes.py#L137).
*Spec:* quote marks are not part of the grammar; this is licenseid's rule for
declared values, not for expressions.

**A3. Take off brackets round the whole value, of any kind.** `(MIT)`,
`[MIT]` and `{[MIT]}` give `MIT` (step `brackets`). One pass: the shallowest
depth between the leading and trailing runs says how many pairs go, so
`[A] OR [B]` loses none. A pair of two kinds (`[MIT)`) stays. *Source:*
[`exprcanon.unbracketed`](../src/licenseid/exprcanon.py#L72).
*Example:* `("MIT")` gives `MIT`, steps `brackets`, `unquote`.
*Test:* [`test_exprcanon.py:75`](../tests/test_exprcanon.py#L75).
*Spec:* **differs.** Annex D has parentheses only; the code also reads `[]`
and `{}` (decision Q21).

**A4. Refuse control and format characters.** What rule A0 left in the value
refuses it, with no step (`unresolved`, `control or format character: U+200B`):
a NUL, a bidi control at the start, and a zero-width space or another such
character anywhere inside, or a value of nothing else. *Reason:* dropping such
a character as a separator would resolve text that shows other than it
reads. *Source:*
[`resolver.py:349`](../src/licenseid/resolver.py#L349).
*Test:* [`test_hiddenchars.py`](../tests/test_hiddenchars.py) (`REFUSED`).
*Spec:* not addressed.

### Stage B: cut into leaves and read each leaf

**B1. Find the operators.** `AND` and `OR` are operators when they have white
space or a bracket on both sides, in any ASCII case; `WITH` stays inside its
leaf. An `or` that starts an "or later" grant is no operator
(`GPL-2.0 or later OR MIT` has one: the second). Anything else is part of a
leaf, so `and_mask` and `MIT"OR"ISC` hold no operator. One pass. *Source:*
[`exprcanon.split`](../src/licenseid/exprcanon.py#L96),
[`_delimited`](../src/licenseid/exprcanon.py#L119),
[`_grant`](../src/licenseid/exprcanon.py#L127).
*Example:* `(MIT)OR(ISC)` reads as `ISC OR MIT`, steps `whitespace`,
`brackets`, `reorder`.
*Test:* [`test_exprcanon.py:51`](../tests/test_exprcanon.py#L51).
*Spec:* Annex D: "white space and/or parentheses" on either side of `AND` and
`OR`, and white space on either side of `WITH`. **Differs** in two ways: the
code accepts `[]` and `{}` as the bracket, and any Unicode white space,
including a line break (`MIT\n OR ISC` reads as `ISC OR MIT`). The Annex
forbids a line break only in tag:value format, so the second is a choice,
not a clash.

**B2. Require operand-shaped leaves.** Every leaf must be one word, with its
`WITH` and exception, a `+`, or an "or later" grant. A leaf of several words
(`Apache License 2.0 OR MIT`) makes the value no compound; the name readers
take it ([flow](resolve-flow.md)). *Source:*
[`resolvecompound.py:398`](../src/licenseid/resolvecompound.py#L398).
*Test:* [`test_resolver_compounds_generated.py:192`](../tests/test_resolver_compounds_generated.py#L192).
*Spec:* licenseid's rule; the Annex has no notion of a prose operand.

**B3. Refuse oversize and mismatched brackets.** More than 150 operators or
150 levels of brackets, and a pair of two kinds (`(MIT OR [ISC)]`), are
refused before the parser runs (`too many operators`, `too deeply nested`,
`mismatched brackets`). *Reason:* the parser recurses without a guard, so
where it gave up depended on the interpreter; one limit makes every supported
Python answer alike. *Source:*
[`exprcanon.oversize`](../src/licenseid/exprcanon.py#L185),
[`identifiers.py:115`](../src/licenseid/identifiers.py#L115).
*Test:* [`test_exprcanon.py:81`](../tests/test_exprcanon.py#L81).
*Spec:* **differs.** The Annex sets no limit.

**B4. Read each leaf as it would be read alone.** The reading gives the
List's spelling of the ID (`id_case`), a renamed ID's successor, `X+` as
`X-or-later` where the List has that ID (`plus_to_or_later`), `WITH` in upper
case with one space (`operator_case`, `whitespace`), and the exception's
List spelling. A `LicenseRef-`, `DocumentRef-` or `AdditionRef-` prefix is
written in SPDX's case; the idstring after it is kept as written. A balanced
pair of quotes round one operand comes off first. *Example:*
`mit WITH llvm-exception AND isc` gives `ISC AND MIT WITH LLVM-exception`
(steps `id_case` three times, `reorder`). *Source:*
[`resolveleaf.py:139`](../src/licenseid/resolveleaf.py#L139),
[`exprtokens.canonical_ref`](../src/licenseid/exprtokens.py#L166).
*Test:* [`test_readers_items.py:234`](../tests/test_readers_items.py#L234)
(reference prefixes); leaf rules in `tests/test_resolver_leaf_rules.py`.
*Spec:* Annex D, case sensitivity: identifiers "should be matched in a
case-insensitive manner"; operators are case-sensitive, "all upper case or
all lower case". Matching the identifier's case is consistent. **Two
differences:** (1) `licenseref-foo` is "not a valid license identifier" in
the Annex, and the code repairs it (`LicenseRef-foo`, step `id_case`, trust
`identity`) instead of refusing it; (2) the Annex says `LicenseRef-Name` and
`LicenseRef-name` "should be treated as the same identifier", and the code
keeps them apart (`LicenseRef-A OR LicenseRef-a` stays as written, and
neither is dropped as a duplicate).

**B5. Refuse the value if any operand names nothing.** All or nothing:
`MIT OR Foo` is `unresolved`, `operand not resolved: Foo`. `NONE` and
`NOASSERTION` are not operands (the Annex does not mention them). *Source:*
[`resolvecompound.py:317`](../src/licenseid/resolvecompound.py#L317).
*Test:* [`test_cli_resolve.py:105`](../tests/test_cli_resolve.py#L105).

### Stage C: parse the shape

**C1. Parse a skeleton, not the text.** Each leaf becomes a placeholder
`LicenseRef-licenseid-leaf-N`; the skeleton goes to `py-spdx-license`. The
parser then sees only `AND`, `OR`, brackets and references, so neither its
snapshot of the List, nor its want of `+` and `AdditionRef-`, nor its sort
can change the answer. A refusal is `malformed` with `parse failed: ...`
(`MIT AND`: `parse failed: Unexpected 'AND'`). *Source:*
[`exprcanon.parse`](../src/licenseid/exprcanon.py#L225).
*Test:* [`test_exprcanon.py:126`](../tests/test_exprcanon.py#L126).

**C2. Precedence: `AND` binds tighter than `OR`.** Taken from the parser,
and so the tree of `MIT OR ISC AND 0BSD` is `MIT OR (ISC AND 0BSD)`. *Spec:*
agrees (Annex D, order of precedence: "the AND operator takes precedence
over ... the OR operator"). `WITH` binds tighter still, and is inside the
leaf here, so `(MIT OR ISC) WITH LLVM-exception` is not read at all (the
Annex also requires a simple expression on the left of `WITH`).
*Test:* [`test_exprcanon.py:179`](../tests/test_exprcanon.py#L179), row
`MIT AND (ISC OR 0BSD)`.

### Stage D: the canonical form, five passes

[`canonical`](../src/licenseid/exprcanon.py#L282) builds six texts and
compares them in pairs. A pair that differs gives a step of the matching
kind. A single input can give several steps, always in this order.

| Pass | From | To | Step |
| --- | --- | --- | --- |
| D1 | operators as written | operators in upper case | `operator_case` |
| D2 | spacing as written | one space, none inside brackets | `whitespace` |
| D3 | brackets as written | brackets by precedence, chains flattened | `brackets` |
| D4 | written order | canonical order | `reorder` |
| D5 | with repeats | each operand once | `dedupe` |

**D1. Operators in upper case.** `and`, `or`, and any mixed case (`Or`)
become `AND`, `OR`. *Source:* [`_written`](../src/licenseid/exprcanon.py#L304).
*Example:* `MIT or ISC` gives `ISC OR MIT`, steps `operator_case`,
`reorder`.
*Test:* [`test_exprcanon.py:157`](../tests/test_exprcanon.py#L157); the
check "written in upper case" is
[`test_exprcanon.py:112`](../tests/test_exprcanon.py#L112).
*Spec:* **differs.** Annex D has the letters of an operator "all upper case
or all lower case". The code accepts `MIT Or ISC` and a value that mixes
`AND` with `or` (`MIT AND ISC or 0BSD`), and records an `operator_case` step.
[`test_resolver_compound_limits.py:25`][mixed-case]
pins `MIT Or ISC` as `ISC OR MIT`, category `lexical`. A lower-case
operator in a value with an operand that names nothing and says nothing is
read as prose, not as a compound (`GPL-3.0 or higher`).

**D2. One space, none inside brackets.** Any run of white space between
tokens becomes one space; none after an opening or before a closing bracket.
*Source:* [`_spaced`](../src/licenseid/exprcanon.py#L320).
*Example:* `MIT  OR ISC` and `MIT\tOR\tISC` give `ISC OR MIT`, steps
`whitespace`, `reorder`.
*Test:* [`test_exprcanon.py:158`](../tests/test_exprcanon.py#L158).
*Spec:* Annex D requires white space (or a bracket) around `AND`/`OR`; one
space satisfies it. `MIT OR(ISC)` becomes `ISC OR MIT`, which is valid.

**D3. Brackets by precedence only; chains flattened.** The expression is
rendered again from the tree. A bracket stays only round an `OR` inside an
`AND`, which is the one case where it changes the meaning. Brackets of any
other kind, redundant pairs and the pair round the whole value go. A chain
of one operator becomes one group (`A OR (B OR C)` is `A OR B OR C`). The
step is `brackets` for all of these. *Source:*
[`_flat`](../src/licenseid/exprcanon.py#L333),
[`_render`](../src/licenseid/exprcanon.py#L352).
*Examples:* `MIT AND (ISC OR 0BSD)` keeps its bracket (no `brackets` step);
`(MIT AND ISC) OR 0BSD` loses it (`0BSD OR ISC AND MIT`); `[MIT OR ISC] AND
0BSD` becomes `0BSD AND (ISC OR MIT)`.
*Test:* [`test_exprcanon.py:159-162`](../tests/test_exprcanon.py#L159).
*Spec:* Annex D: parentheses "override" precedence; removing those that do
not is meaning-preserving. Flattening uses associativity, which the Annex
does not state (it names commutativity only). **Reading of the step:**
`brackets` covers three different edits (removed, replaced, flattened);
a reader of the steps cannot tell which.

**D4. Canonical order.** In each group: every leaf before every bracketed
group. A leaf sorts by rank (a listed ID 0, a `LicenseRef-` or
`DocumentRef-` 1, a `WITH` 2), then by its text case-folded, then as is. A
group sorts by its rendered text, case-folded, then as is.
*Reason:* the code calls the case-folded key "the SPDX License List's
order, made total" (decision Q24, which adds the third key); the ranks and
"leaves before groups" are decision Q19, whose reason the code does not
record. *Source:*
[`leaf_key`](../src/licenseid/exprcanon.py#L271),
[`_text_key`](../src/licenseid/exprcanon.py#L369),
[`_ordered`](../src/licenseid/exprcanon.py#L375).
*Examples:* `Zlib OR MirOS OR MIT` gives `MirOS OR MIT OR Zlib` (`mirOS`
before `mit` when folded: `m-i-r` before `m-i-t`);
`LicenseRef-b OR MIT OR LicenseRef-a` gives `MIT OR LicenseRef-a OR
LicenseRef-b`; `MIT OR GPL-2.0-only WITH Classpath-exception-2.0 OR ISC`
gives `ISC OR MIT OR GPL-2.0-only WITH Classpath-exception-2.0`;
`(MIT OR Zlib) AND (MirOS OR Zlib)` gives `(MirOS OR Zlib) AND (MIT OR
Zlib)`.
*Test:* leaf order
[`test_exprcanon.py:134`](../tests/test_exprcanon.py#L134); group order
[`test_exprcanon.py:173`](../tests/test_exprcanon.py#L173); independence of
the hash seed
[`test_resolver_compounds.py:156`](../tests/test_resolver_compounds.py#L156).
*Spec:* the Annex fixes no order and states that `AND` and `OR` are
commutative, so any order is equivalent. Nothing differs; the order is a
licenseid choice, and it is **not** the order of the tag path (see
[above](#two-canonical-orders-in-one-package)).

**D5. Remove repeats.** After sorting, each operand is kept once, by its
rendered text; a group left with one operand is that operand, and joins its
parent's operator. Done on the resolved leaf text, so `MIT OR mit` is `MIT`
and `GPL-2.0+ AND GPL-2.0-or-later` is `GPL-2.0-or-later`. *Source:*
[`_ordered`](../src/licenseid/exprcanon.py#L375), `dedupe` branch.
*Examples:* `(MIT OR ISC) AND (ISC OR MIT)` gives `ISC OR MIT`;
`Zlib AND ((MIT AND ISC) OR (ISC AND MIT))` gives `ISC AND MIT AND Zlib`.
*Test:* [`test_exprcanon.py:163-172`](../tests/test_exprcanon.py#L163).
*Spec:* the Annex does not mention duplicates or idempotence. This rule
uses `A OR A = A` and `A AND A = A`, which hold in logic and which the
Annex neither states nor contradicts.

### What the canonical form does not do

Run on 2026-11-07, these are left as they are:

- No absorption: `MIT OR (MIT AND ISC)` gives `MIT OR ISC AND MIT`, not
  `MIT`.
- No merge of a licence with its qualifier:
  `GPL-2.0-only OR GPL-2.0-or-later` stays.
- No distribution: `(MIT AND Zlib) OR (MIT AND ISC)` gives
  `ISC AND MIT OR MIT AND Zlib`.
- A `WITH` leaf is not merged with the same licence alone:
  `GPL-2.0-only WITH Classpath-exception-2.0 AND GPL-2.0-only` keeps both.

Each of these would change the structure of what the author wrote beyond
spelling. The step list records only the five passes above, so a consumer
can tell a spelling change from a decision.

## Differences from the SPDX specification

Against Annex D of SPDX Specification 3.0.1. All are in the direction of
accepting more than the Annex allows, then writing the strict form.

| Rule | Annex D | Code | Where |
| --- | --- | --- | --- |
| Operator case | all upper or all lower | accepts mixed case; writes upper | D1 |
| Brackets | parentheses | also `[]` and `{}`; writes `(`, `)` | A3, B1, D3 |
| White space | white space or parentheses round `AND`, `OR`; white space round `WITH` | any Unicode white space, a line break included; a bracket of any kind; one space written | B1, D2 |
| `LicenseRef-` prefix case | `licenseref-name` "is not a valid license identifier" | repaired to `LicenseRef-name`, category `lexical` | B4 |
| `LicenseRef-` idstring case | `LicenseRef-Name` and `LicenseRef-name` are the same identifier | kept apart; neither removed as a duplicate | B4, D5 |
| Limits | none | at most 150 operators and 150 bracket levels | B3 |
| `+` | "the current version ... or any later version" | `X+` becomes `X-or-later` when the List has it (trust `list_data`), else stays `X+` | B4 |
| `NONE`, `NOASSERTION` | not discussed | refused as licences | B5 |
| Order, duplicates, redundant brackets | not specified (only commutativity of `AND`, `OR`) | fixed order; repeats and chains removed | D3 to D5 |

None of these makes a canonical form that is invalid under Annex D: the
output uses upper-case operators, parentheses, single spaces and List
spellings. The risk runs the other way: a strict reader of the Annex would
refuse inputs this code reads, and the `LicenseRef-` case rule means two
spellings that the Annex calls the same identifier come out as two.

## Reproduce

Each example was run as:

```python
from licenseid import resolve

r = resolve("mit or isc")
r["expression"], [s["kind"] for s in r["steps"]]
# ('ISC OR MIT', ['id_case', 'id_case', 'operator_case', 'reorder'])
```

With no database, `resolve()` reads the List in the wheel; with a database
or an editable install, the newer List of the two. The outputs above do not
depend on the List version, except that `plus_to_or_later` needs the
`-or-later` ID to be listed.

[mixed-case]: ../tests/test_resolver_compound_limits.py#L25

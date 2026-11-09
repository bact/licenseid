---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# How it works

What `licenseid` does inside: the normalisation of IDs, the reading of
declared values, SPDX expressions and the matching pipeline.

- **Deprecated ID normalisation**:
  - `GPL-2.0+` → `GPL-2.0-or-later` (SPDX `+` operator, unambiguous).
  - `Apache-2+` → `Apache-2.0+` (abbreviated base canonicalised, `+` retained).
  - Bare deprecated IDs (e.g. `GPL-2.0`) resolved conservatively to `-only`
    by `detect()` when no surrounding context is available, as a guess said
    aloud: not exact, with `WARNING: input: variant not stated: GPL-2.0;
    using GPL-2.0-only`, whether the ID is an argument, `--id`, a tag or a
    manifest field; `resolve()` keeps them as written
    ([Resolve a declared value](cli.md#resolve-a-declared-value)). A List name
    without its grant (`GNU General Public License v2.0`), as a whole input
    but not yet a manifest field, is the same guess, said the same way; a
    name with a "+" (`v2.0+`), or without its version too, is no answer.
- **Declared-value resolution** (`resolve()`, and `licenseid resolve` on the
  command line): turns one declared licence value (a `license` field, a
  model card, a trove classifier) into an SPDX expression and the steps
  taken, without fuzzy matching, with or without a database. It reads loose
  IDs (`Apache2`, `GPLv3`), the List's names, a licence's own title (`CC0
  1.0 Universal`, `Mulan PSL v2`), the BSD aliases (`New BSD`, `BSD-3`),
  prose forms (`BSD 3-Clause License`), licence URLs
  (`https://www.apache.org/licenses/LICENSE-2.0`, `spdx:MIT`; a URL of
  several licences is refused),
  quote marks, trove classifiers and compounds of one-word
  operands, and refuses, with a reason, what it would read only by dropping
  a mark or a word. What it reads, rule by rule, is in
  [resolve.md](resolve.md#what-resolve-reads).
- **SPDX License Expression support** (via
  [`py-spdx-license`][py-spdx-license]):
  - Structural normalisation of `AND`/`OR` expressions, in a tag or a
    manifest field, and in a whole input `resolve()` reads (`--id` takes one
    licence): duplicate operands collapse (`MIT AND MIT` → `MIT`)
    and operands are put in a consistent order, making equivalent expressions
    compare equal. A whole input takes `resolve()`'s canonical order
    (`MirOS OR MIT`); a tag, a field and a narrowed guess keep the
    detector's own until 0.8 (`MIT OR MirOS`; `MirOS OR GPL-2.0` is
    `GPL-2.0-only OR MirOS`).
  - The flags of an expression are judged operand by operand: `AND` is
    OSI-approved (or FSF-libre) when every operand is, `OR` when any is,
    `X WITH Y` when `X` is. An operand that cannot be judged (a
    `LicenseRef-*`) leaves the flag empty (`null`), never a false "no",
    unless a judged operand decides it: `MIT OR LicenseRef-x` is
    OSI-approved, `CC-BY-4.0 AND LicenseRef-x` is not. `is_spdx` is true
    only when every licence and exception ID is on the List: a
    `LicenseRef-*` makes it false.
  - `WITH <exception>` expressions are validated and matched against the
    SPDX exception list, not just the licence list — e.g.
    `licenseid detect --id "MIT WITH Font-exception-2.0"` resolves correctly
    even though it isn't a single licence row.
  - A `SPDX-License-Identifier` tag, and the `license` field of a JSON, TOML
    or INI file, are read as whole expressions, parentheses, `LicenseRef-*`
    and all: `MIT OR (Apache-2.0 AND BSD-3-Clause)` in a file resolves to
    one answer. `--id` is narrower on purpose (see `--id` under
    [cli.md](cli.md#detect-a-licence-or-resolve-a-declared-value)). A tag or field
    names only IDs on the List, or `LicenseRef-*`: an operand that is none
    (`MIT OR Apache 2.0`) gives no answer, as `resolve()` refuses it. A
    bare "or later" after an ID is the grant (`MIT or later`, `MIT, or
    any later version` are `MIT+`); a "+" apart from its ID (`MIT +`) names no
    licence.
  - Package manifests are read for their `license` field, however small:
    `package.json` (with npm's old `license` object and `licenses` array),
    `pyproject.toml` (`license = "..."` or `license = {text = "..."}`, and
    Poetry's), `Cargo.toml` and `setup.cfg`.
- **Hybrid matching pipeline**:
  - **A whole value first**: an input that is, as a whole, one declared
    value (`MIT OR Apache-2.0`, `Apache License, Version 2.0`, `GPLv3+`) is
    read by `resolve()`, so `detect` answers its expression, or, for a bare
    split ID, the `-only` guess (see the deprecated ID item above). An
    input under 10 words that `resolve()` refuses and no licence name
    matches is not matched as text: no answer, with `WARNING: input: too
    few words for text: <reason>` (`not found: GNU GPL v2`). So is a text
    of under 30 words that `resolve()` refuses for a "+" that is no operator
    (`"MIT++"`, `MIT License++`, `Apache 2.0 +`), with the "+" reason: Tier 0
    would drop the "+" and answer the licence, exact.
  - **Tier 0 (Shortcut)**: Fast path for short inputs (names, IDs, brief
    expressions). Includes:
    - Case-insensitive exact ID match.
    - Prose-context disambiguation for bare deprecated IDs (e.g.
      `"GPL-2.0 or later version"` → `GPL-2.0-or-later`).
    - Conservative `-only` fallback when no granting context is present.
  - **Tier 0.5 (Marker detection)**: Detects `SPDX-License-Identifier` tags and
    structured markers (name fields, headings). An exact SPDX tag returns
    immediately with full confidence.
  - **Tier 1 (Recall)**: Candidate retrieval using SQLite FTS5 trigram index,
    queried with the input's first 20 words, plus its last 20 for an input
    over 200 words (at most 25 more candidates), for consistent performance.
    Comment prefixes (`//`, `#`, `*`, `;`) are stripped before querying.
  - **Tier 2 (Precision)**: Adaptive ranking with RapidFuzz. Sliding-window
    alignment for fragments; coverage-aware scoring to prefer the tightest
    match. Marker confidence boosts applied only when confidence ≥ 0.85.

[py-spdx-license]: https://github.com/JPEWdev/py-spdx-license

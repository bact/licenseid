---
Created: 2026-11-17
Last-Modified: 2026-11-17
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolved tech debt, from 2026-11-17

Items of [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md)
resolved from 2026-11-17 on, in the order they were resolved. The earlier
ones are in [`tech-debt-resolved-0-5.md`](tech-debt-resolved-0-5.md); this
part was split from it when it passed the file size limit. Item numbers are
the roadmap's.

## Items 50, 51, 54 (marks on a value, 2026-11-17)

Marks and invisible characters around a declared value. Planned and measured
on `main` 50017cb (SPDX List 3.29.0), with the owner's decisions of
2026-11-17; each one follows the rule "refuse unless the loss is measured and
the reading is safe".

- **Measured**: the PyPI sample (462 values, 10,000 projects), the registry
  inputs of `sbomminbench` (172) and the golden `value` keys (520): 642
  distinct values on four channels (value, text, tag, field). A refused value
  that one stray mark at an end would make readable: 0 real values (the
  parity corpus alone has `#MIT`, `(MIT`, `MIT*`, `Apache 2.0?`,
  `Apache 2.0!`, `GPLv3 +`, `MIT OR GPL-2.0-only+`, all refused since item 48).
  A hidden character anywhere: 3 values, all parity corpus (`MIT\x00`,
  `MIT​`, `‮MIT`), none inside quote marks. A backslash in a value:
  0. Tag lines under `~/projects` (14,743): a dash glued to a comment closer
  0; `?`, `!` or `*` glued 0; `)` glued 2 (the Markdown comment
  `[//]: # (SPDX-License-Identifier: EPL-2.0)`). No answer of the 642 values
  moves in this change (the same script before and after).
- **Item 51, decided (a): a lone stray mark stays refused.** `(MIT`, `MIT)`,
  `/MIT`, `MIT/`, `GPL-2.0+)` and the others are the head or the tail of a
  cut compound or list (`(MIT OR Apache-2.0)`, `MIT/Apache-2.0`), so reading
  them would be a guess; a lone quote or an ending (`"MIT`, `MIT,`) is read, a
  weaker answer, as before. Pinned in `tests/test_stray_marks.py` (reason of
  `resolve()`, no `detect()` answer, the tag that reads a `)`), documented in
  `docs/resolve.md`. Rejected: reading a lone trailing `)`, `]` or `/` (it
  moves `value/(MIT`, `value/MIT*`, `value/#MIT` of the golden back to an
  answer for 0 measured values).
- **Item 50, a hidden character inside quote marks (decided (a))**:
  `"MIT​"` is read as `MIT` (steps `unquote`, `trim`; `separator`),
  as `MIT​` already was. `hiddenchars.strip_plain_format` leaves off a
  format character (`Cf`) that is no bidi control; a bidi control, a control
  character (`Cc`), a NUL and one inside a word stay refused, and so do
  brackets (`(MIT​)`) and an operand's quotes. `resolver._read` judges
  `_refusal` on the value without those characters, or the trim would do
  nothing.
- **Item 50, a TOML string with escapes (decided (a))**: the reader skipped
  every basic string with a backslash and stopped an inline table's `text` at
  its first quote, so `license = "\"MIT\""` gave no value at all (the
  roadmap said the backslashes were kept; they were not read). A basic string
  is decoded as TOML 1.0 has it (`\b \t \n \f \r \" \\ \uXXXX \UXXXXXXXX`);
  any other escape (TOML 1.1's `\xHH` and `\e` included), a short `\u12` and a
  surrogate or code point past U+10FFFF is no value, as a parser refuses the
  file; a literal string is never decoded. What it decodes to goes to
  `resolve()` (`MIT\\u0041` decodes to a backslash and letters: refused). No
  `tomllib` (Python 3.10).
- **Item 54, the reference's trailing dash**: `MIT OR LicenseRef-a-` in a tag
  or a `license` field answered `MIT OR LicenseRef-a`, another reference
  (`identifiers._normalize_expression` cut each ID at its last letter or
  digit). It reads each token as `exprtokens.expression_tokens` does, a
  reference with its own dashes and dots. The roadmap said the tag only: the
  field was hit too.
- **Review found** (independent Opus pass): a hidden character between an
  inner mark and the closing quote (`"MIT.\u200b".`) got round the
  two-marks refusal, so the trim is not made when a mark also ends the value
  inside the quotes after an end mark outside (fixed, pinned); a closer glued
  to a reference's trailing dash in a tag (`MIT OR LicenseRef-a-->`, `-}`,
  `--]]`, `-#}`, `-*/`, a lone `LicenseRef-a-->` too) was read into the
  reference (main: dropped the dash); now refused (`dropguard.cut_reference`,
  pinned). Stripping foreign characters then trailing dashes was rejected.
- **Item 54, a comment closer glued to a dash in a tag: kept as is (decided
  (a))**: `MIT-*/`, `MIT-#}`, `MIT-}`, `MIT--]]` read as `MIT`. The pins of
  `tests/test_cut_tags.py` `STAYS` say so on purpose (Haskell, Lua, Jinja).
- **Item 54, reasons**: `LGPL-2 WITH Classpath-exception-2.0+` is `malformed`,
  `plus after an exception`, as `LGPL-2.1 WITH ...+` is; it was `version
  ambiguous`. `LGPLv2 or above` and `Apache-1 or above` are `not found: <value>`
  (prose), as `LGPLv2.1 or above` is: in `resolvecompound` a lower-case
  `or` drops the operands that name nothing, and now a cut operand too. A cut
  version is the reason only when it is the value's first fault. Kept: the
  cut reason beside a grant a text match would read (`LGPLv2 or (later)`):
  without that guard the reason stopped blocking the text tier and 14
  `detect()` answers appeared (`LGPL-2.0-or-later`). An 8,411-value sweep
  (R, text, tag, field) moved 861 reasons and no answer. The investigation
  was done by a read-only Opus subagent.
- **Paths rejected**: reading a lone mark by category (`separator`); trimming
  a bidi control inside quotes (the closing mark stands beyond it); a second
  escape scanner in `manifest` (`_RE_TOML_STRING` takes an escaped pair as one
  unit).

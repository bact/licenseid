---
Created: 2026-11-09
Last-Modified: 2026-11-09
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Terse output of `detect` and `resolve`

A record of the change that made `licenseid detect` and `licenseid resolve`
print the SPDX expression alone, and `-v` / `--verbose` the record they
printed before. The CLI layer only: `result.py` still writes the verbose
lines and the JSON, and the library is untouched.

## What changed

| Command line | Before | Now |
| :--- | :--- | :--- |
| `detect X` | `EXPRESSION=… METHOD=…` record per result | the expression per result, one line each |
| `detect X` (no answer) | the record, every field empty | an empty line |
| `detect -v X` | n/a | the old record |
| `detect --id-only X` | the top expression | usage error (`option: not found: --id-only`) |
| `resolve X` | `EXPRESSION CATEGORY TRUST` and `STEP`, `REASON`, `OPERAND` lines | the expression, or an empty line |
| `resolve -v X` | n/a | the old lines |
| `--json` | the whole object | the same, with or without `-v` |
| `-V` | n/a | `--version` |

Exit codes are unchanged: 0 an answer, 1 none, 2 a usage error.

## Decisions

1. **`--json` without `--verbose` stays the whole object.** JSON is for
   programs, which read a key; a minimal object would be a second shape to
   keep, and "fields are only ever appended" says the keys stay. `-v` is
   accepted and does nothing beside `--json`. `--diff` with `--json` is still
   a usage error (`option: invalid: --diff: with --json`); `--diff` with the
   terse output works, its diff on standard error, as with `--id-only`
   before. The old `--json --id-only` error is gone with the option.
2. **`--id-only` is removed**, not kept as a hidden no-op: a private alpha
   owes no compatibility, and a script that passes it learns at once, with a
   clean usage line. Its output is the default now.
3. **Several results (`detect --top N`)** print one expression per line, in
   rank order, the order of the `-v` lines.
4. **Warnings and errors are unchanged**: `WARNING:` and `ERROR:` lines on
   standard error, in both modes. A refused `resolve` prints an empty line
   and exit 1; the `REASON` is in `-v` and in `--json` only. Nothing is
   added to standard error for it: the terse mode stays terse, and the
   reason is one `-v` away.
5. **Option matrix and output pattern.** `--verbose` is an axis of
   `tests/test_option_matrix.py` (it replaces `--id-only` in the `detect`
   outputs, and the `resolve` matrix runs terse, `--verbose`, `--json`,
   `--json --verbose`). `tests/test_output_pattern.py` holds every command
   to the record pattern with `-v` and `--json`, and checks the default
   output of `detect` and `resolve` against the `-v` record.
6. **Goldens.** The CLI golden harness (`tests/harness_cli.py`) runs
   `detect` and `resolve` with `--verbose`, so every recorded row stays
   valid (`python -m tools.golden cli` showed no moved row). Cases made with
   `_terse(...)` run as written: `detect-terse`, `detect-terse-no-answer`,
   `detect-terse-top-three`, `resolve-terse`, `resolve-terse-unknown`, and
   `detect-id-only-gone` (the removed option). `detect-id-only` left the
   file. Those rows were added to `cli.jsonl` without a regeneration of the
   rest: the already listed `CLI_CHANGES` rows still stand.
7. **`tools/cli_matrix`.** The judge's output flag `id-only` is now
   `verbose`: no flag means the expression alone, `verbose` the record,
   `json` the object. Cells that passed `detect --id-only` pass `detect`;
   the `resolve` cells run terse, `--verbose` and `--json`. `baseline.txt`
   is not touched.

## How the tests keep reading the record

Hundreds of tests read the full record through `CliRunner`. Instead of
adding `-v` to each call, an autouse fixture (`verbose_cli` in
`tests/conftest.py`, the logic in `tests/cli_verbose.py`) adds it after
`detect` or `resolve`. A test of the default carries
`@pytest.mark.terse_cli`. This is a test helper, not a compatibility layer:
the product has one behaviour. A subprocess test does not get it and says
`-v` itself.

## Other commands

`is-osi`, `is-fsf`, `is-spdx`, `update` and `clear-cache` print their one
record as before and take no `-v` (a usage error). The `is-*` record is one
line already; `update` and `clear-cache` print one line per list or one
status.

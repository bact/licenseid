---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Output formats

What the commands print: the default expression, the record of `-v`, JSON
Lines, the word diff, how to read them in a shell, and the format of errors
and warnings. The commands and options are in [cli.md](cli.md).

## Default and verbose text

Default (Unix-friendly): `detect` and `resolve` print the SPDX expression
alone, one line per result, best first, and an empty line when there is
none:

```console
$ licenseid detect --top 1 LICENSE
Apache-2.0
```

With `-v` (`--verbose`), one record per result per line, best first (the
examples show the first two results):

```text
EXPRESSION=Apache-2.0	METHOD=text	EXACT=true	SCORE=1.0000	SIMILARITY=1.0000	COVERAGE=1.0000
EXPRESSION=ECL-2.0	METHOD=text	EXACT=false	SCORE=0.9584	SIMILARITY=0.9584	COVERAGE=0.9236
```

- One tab separates the fields; a key ends at the first `=`. Read them with
  `cut -f` or `awk -F'\t'`. A value is written as it is, except a tab, a
  carriage return, a line feed and a backslash, written `\t`, `\r`, `\n` and
  `\\`, and a character the locale of standard output cannot encode,
  written `\xHH`, `\uHHHH` or `\UHHHHHHHH`. `--json` is UTF-8 on every
  locale.
- `EXPRESSION` is the answer: a licence ID or an expression for `detect`
  (a tag, a field, or a whole input `resolve()` reads, in its order; a
  narrowed guess in the detector's).
- `METHOD` is how the answer was found: `tag` (an `SPDX-License-Identifier`
  tag), `field` (a manifest's `license` field), `id` (a licence ID), `name`
  (a licence name) or `text` (the licence text).
- `EXACT` is `true` when the answer was found exactly: declared (a tag, a
  field or an ID), a whole input `resolve()` reads without a guess (a name,
  `The MIT License`, a trove classifier, a loose ID, `Apache2`), a licence
  name spelt out in full (for a name a deprecated licence shares with its
  successor, only the successor), or the whole input equal to the licence
  text as the SPDX License List writes it, after case, punctuation and
  white space are normalised. A guess (`GPL-2.0` read as `GPL-2.0-only`)
  is not exact. A filled-in copyright line or an added title makes a text
  not exact, as does a name that only shares the words of the input.
  Licences with the same text (`GPL-2.0-only` and `GPL-2.0-or-later`) are
  all exact for it.
  `--exact` keeps only the exact results.
- `SCORE` is 0 to 1; `--threshold` reads it. Several results can score 1:
  the order tells them apart, and `EXACT` tells an exact one from a close
  one.
- `SIMILARITY` and `COVERAGE` are empty where nothing was measured: a tag,
  a field, an ID or a name `resolve()` reads has neither, and a name the
  name tier matches has no coverage. `COVERAGE` is the
  input's words over the licence's, so it passes 1 when the input is longer.

## JSON

JSON (the full record, with or without `-v`):

```bash
licenseid detect LICENSE.txt --json
```

Example output, in JSON Lines: one object per result per line, in the
JSON Canonicalization Scheme (RFC 8785), so equal results print equal bytes
(`jq -s .` makes an array of them):

<!-- markdownlint-disable MD013 -->

```json
{"coverage":1,"exact":true,"expression":"Apache-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"lists":[{"id":"spdx-license-list","id_authority":true,"license":"CC0-1.0","name":"SPDX License List","provides":["deprecation","ids","names","texts"],"source":"database","url":"https://github.com/spdx/license-list-data/releases/tag/v3.29.0","version":"3.29.0"}],"method":"text","score":1,"similarity":1}
{"coverage":0.9236,"exact":false,"expression":"ECL-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"lists":[{"id":"spdx-license-list","id_authority":true,"license":"CC0-1.0","name":"SPDX License List","provides":["deprecation","ids","names","texts"],"source":"database","url":"https://github.com/spdx/license-list-data/releases/tag/v3.29.0","version":"3.29.0"}],"method":"text","score":0.9584,"similarity":0.9584}
```

<!-- markdownlint-enable MD013 -->

## Word diff

Diff (visual comparison), here of an Apache-2.0 file with its copyright
line filled in:

```bash
licenseid detect -v LICENSE --diff --top 1
```

Example output (a diff is shown for the top result when it was matched as
text and is not exact, with or without `-v`, not with `--json`). The
results go to standard output and the diff to standard error, so
`2>/dev/null` keeps only the results. Here with `-v`:

```diff
EXPRESSION=Apache-2.0	METHOD=text	EXACT=false	SCORE=1.0000	SIMILARITY=0.9978	COVERAGE=0.9987

WORD DIFF:
--- DATABASE
+++ INPUT
@@ -1502,11 +1502,9 @@
 party
 archives
 copyright
-yyyy
-name
-of
-copyright
-holder
+2024
+jane
+doe
 licensed
 under
 the
```

## Reading the output

Every command prints its result in one pattern, so one reader serves them
all:

- One record per line, `KEY=VALUE` fields with an uppercase key, one tab
  between fields, and `\t`, `\r`, `\n` and `\\` for a tab, a line break
  or a backslash inside a value.
- The first key of a line names its kind: `EXPRESSION` the answer, `STEP` a
  step of `resolve`, `REASON` a refusal, `OPERAND` a licence of a list,
  `LIST` the list `update` read, `STATUS` what `clear-cache` did.
- The answer is the first line. A command with no answer still prints its
  record, every field empty: `detect` on exit 1 prints
  `EXPRESSION=` and the other keys with nothing after the `=`.
- Fields are only ever appended to a line in a later release, never
  removed, renamed or moved: read a field by its key, not its place.
- `--json` prints the same record as one RFC 8785 JSON object per line,
  with every text key in lower case (`EXPRESSION` is `expression`).
  `null` means nothing: where the text line has an empty value, and in a
  key JSON adds that holds nothing. JSON may hold more than the text line:
  `detect --json` adds the flags and the `lists` of each result, and
  `resolve --json` prints the whole result as one object, its keys mapped to
  its text lines in [resolve.md](resolve.md).

This is the output of `-v` and `--json`. The only exceptions are the
default output of `detect` and `resolve` (the expression alone, one per
line), `--version` (`-V`) and `--help`.

```bash
# The answer alone, by default
licenseid detect --top 1 LICENSE.txt                  # Apache-2.0

# The second field of the line, its value after the "="
licenseid is-osi MIT | cut -f2 | cut -d= -f2-          # true

# The answer: the first field of the line whose first key is EXPRESSION
# (resolve also prints EXPRESSION= after OPERAND= on a line of its own kind)
licenseid resolve -v "MIT ; Apache 2" | awk -F'\t' '
  $1 ~ /^EXPRESSION=/ { print substr($1, length("EXPRESSION=") + 1); exit }'

# The same with jq
licenseid detect --json LICENSE | jq -r .expression
licenseid resolve --json "GPLv2+" | jq -r '.steps[] | select(.applied) | .kind'
licenseid update --json | jq -r '"\(.status) \(.version)"'
```

## Errors and warnings

Errors and warnings go to standard error, one per line, in a fixed format:

```text
LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]
```

For example:

```text
ERROR: database: not found: /tmp/x.db; run 'licenseid update'
ERROR: option: not found: --jsn; did you mean --json
WARNING: popularity.csv: download failed: timed out; using stale cache
```

`LEVEL` is `ERROR` (the command fails) or `WARNING` (it continues).
`SUBJECT` is the thing affected, such as `database`, `input` or a cache file
name, so `cut -d: -f1-3` gives the level, subject and condition.

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

<!-- docs-example: run: licenseid detect -v LICENSE; head -->

<!-- markdownlint-disable MD013 -->

```text
EXPRESSION=Apache-2.0	METHOD=text	EXACT=true	SCORE=1.0000	SIMILARITY=1.0000	COVERAGE=1.0000	VARIANT_STATED=	SAME_TEXT=	REASON=	TEXTS=Apache-2.0
EXPRESSION=ECL-2.0	METHOD=text	EXACT=false	SCORE=0.9584	SIMILARITY=0.9584	COVERAGE=0.9236	VARIANT_STATED=	SAME_TEXT=	REASON=	TEXTS=Apache-2.0
```

<!-- markdownlint-enable MD013 -->

- One tab separates the fields; a key ends at the first `=`. Read them with
  `cut -f` or `awk -F'\t'`. A value is written as it is, except a tab, a
  carriage return, a line feed and a backslash, written `\t`, `\r`, `\n` and
  `\\`, and a character the locale of standard output cannot encode,
  written `\xHH`, `\uHHHH` or `\UHHHHHHHH`. `--json` is UTF-8 on every
  locale.
- `EXPRESSION` is the answer: a licence ID or an expression for `detect`
  (a tag, a field, or a whole input `resolve()` reads, in its order; a
  variant `--variant` chose, in the detector's).
- `METHOD` is how the answer was found: `tag` (an `SPDX-License-Identifier`
  tag), `field` (a manifest's `license` field), `id` (a licence ID), `name`
  (a licence name) or `text` (the licence text).
- `EXACT` is `true` when the answer was found exactly: declared (a tag, a
  field or an ID), a whole input `resolve()` reads where a list defines the
  reading (a listed name, a trove classifier, a licence URL, a title or
  alias of the lists licenseid keeps), a licence name spelt out in full
  (for a name a deprecated licence shares with its successor, only the
  successor), or the whole input equal to the licence text as the SPDX
  License List writes it, after case, punctuation and white space are
  normalised. A bare `GPL-2.0` kept as written is exact. A variant
  licenseid chose is not: the `-only` or `-or-later` of a text or a name,
  as the two have the same text (so `--exact` gives none for the GPL), and
  `GPL-2.0` read as `GPL-2.0-only` by `--variant only`. A filled-in
  copyright line or an added title makes a text not exact, as does a name
  that only shares the words of the input. A value that a rewrite rule read
  (`Apache License, Version 2.0`, `Apache 2`, `GPL2` as `GPL-2.0`) is not
  exact, except IDs joined by a slash (`MIT/Apache-2.0`): the `EXACT`
  column of [the category table](resolve.md#steps-and-categories) has the
  details. `--exact` keeps only the exact results.
- `SCORE` is 0 to 1, capped in the output, and `--threshold` reads it. It ranks
  the results; it is not a measure of how well the input fits the licence. For a
  text it starts from `SIMILARITY`, scaled down for a short input (a Latin text
  under 40 characters; a Han or kana character counts two). It then takes a
  penalty of up to 0.01 for a `COVERAGE` from 0.5 to 0.8, a bonus of 0.005 for
  one from 0.95 to 1.05, a bonus of up to 0.05 for a phrase that few licences
  share, and, with `--pop`, a tie-breaking term of 0.0001 for each power of ten
  of the licence's popularity. A marker of confidence 0.85 or more adds to the
  score, and a short, mixed or structural one (a notice, a heading) sets it to
  at least 0.95 of its confidence. So a short notice or a pointer can score 1
  with a `SIMILARITY` well below 1. That floor does not hold where the input is
  longer than that licence's text (`COVERAGE` above 1.05) and holds whole
  licence texts other than it: a notice in a file of several licence texts
  does not answer for the file, and a licence whose text is not among those
  found gets no result. Several results can score 1: the order tells them
  apart, and `EXACT` tells an exact one from a close one.
- `SIMILARITY` is 0 to 1: how alike the input and the text it was compared with
  are, by RapidFuzz. That text is the whole licence text, or its core (the text
  without its optional parts, such as an appendix) when the core is the closer
  one. For a fragment (a `COVERAGE` under 0.8) it is the best-aligned part of
  the text; a very long fragment is compared with the whole text. A `not`,
  `except`, `unless` or `irrevocable` that only one side holds costs a text 5%
  when its similarity is above 0.9 and below 1. A name's `SIMILARITY` is how
  alike the names are; it is not scaled for a short input.
- `COVERAGE` is the input's words over the words of the text it was compared
  with: the whole text, or the core when the core won. It has no upper
  limit. Below 0.8 the input is a fragment, such as a copyright notice, a
  header or a cut file. From 0.95 to 1.05 it is about the whole licence
  text. Well above 1 the input holds more than that licence's text, as a
  file that holds two licence texts does. `TEXTS` names the licence texts
  such a file holds; the ranking is still that of one licence.
- `SIMILARITY` and `COVERAGE` are empty (JSON `null`) where nothing was
  measured: a tag, a field, an ID or a name `resolve()` reads has neither,
  and a name the name tier matches has no coverage.
- `VARIANT_STATED` (JSON `variant_stated`) says whether the
  input states which variant of a licence is meant, where it has an `-only`
  and an `-or-later` form: `true` when words (`GPL-2.0 or later`), a "+" or
  an `-only` / `-or-later` ID state it; `false` for a guess (an `-only`
  chosen for a text, or by `--variant`) or a bare ID kept as written
  (`GPL-2.0`, `GPL-2.0-with-classpath-exception`); empty (JSON `null`) when
  no licence of the answer has a variant (`MIT`). Of a compound it is empty
  when no operand has a variant, `false` when any operand is `false`
  (`MIT OR GPL-2.0` is `GPL-2.0 OR MIT`, `false`), else `true`. A script
  tells a guessed `-only` from a stated one without reading standard error.
  The `is-*` commands have no such field: they answer a flag, not a variant.
- `SAME_TEXT` (JSON `same_text`) lists the other List IDs
  whose text is identical to the answer's after normalisation, sorted,
  separated by one space in the record (a list of strings in JSON). Some
  licences share one text, so the text alone cannot choose between them: the
  text of `MPL-2.0` is also the text of `MPL-2.0-no-copyleft-exception`, and
  both are exact. It names the answer's twins, never the answer itself, and
  stays right when licenseid chose between `-only` and `-or-later` for the
  text. It is empty (JSON `null`) when no other licence has that text, for
  any `METHOD` but `text` (a tag, a field, an ID and a name say nothing of a
  text), for a compound answer, and for a database built before
  `licenseid update` kept the groups. The `is-*` commands have no such field.
- `REASON` (JSON `reason`) is empty (JSON `null`) on an answer. On the record of
  no answer it is the one field that is not empty: `below threshold` (a
  candidate was found, but none scored `--threshold`), `not exact` (`--exact`
  removed every result; the threshold is read first) or `no match` (nothing was
  a candidate; a `WARNING` on standard error may say why, such as `too few words
  for text`; also every candidate held back because the file holds several
  licence texts and none of them was a candidate, where `--threshold 0` shows
  nothing either). It names no licence, as an ID in a record of no answer
  invites a guess; to see the nearest candidate run `licenseid detect
  --threshold 0 --top 1 -v`. The API `detect()` returns an empty list and has no
  such field. The key is a field of a `detect` line, never its kind: a line
  starting with `REASON=` is a refusal of `resolve`.
- `TEXTS` (JSON `texts`, a list of strings; the last field) lists the List IDs
  whose whole licence text, or its core (the text without its optional parts),
  the input holds, one per text, sorted, separated by one space in the record. A
  List text under 40 words is listed only when it is the whole input (an exact
  answer, whatever its length). A file with several licence texts names each:
  `BSD-2-Clause MIT Python-2.0.1` for mypy's `LICENSE`. An exact answer gives
  the answer alone. The same list is on every `--top` line. It is filled for
  `-v`, `--json` and the API; the search is skipped where it is never printed
  (the `is-*` commands, the `is_*()` functions, and `detect` without `-v` or
  `--json`), except that it runs, unprinted, where a marker's floor needs it
  (`SCORE`), so every output gives the same answer. It is empty (JSON `null`)
  when no text was found, when the top result is not a text match, in a record
  of no answer (also where the one text found was no candidate: the Saxpath
  fixture `license_text_short_tail_2000` gives `REASON=no match`, empty `TEXTS`,
  exit 1), when the input has under 40 words (a Han or kana character counts as
  one word) and its answer is not exact, and when the input is too large to
  search (the search is bounded by counts, and past one it gives no list, never
  a partial one). `exclude` and `hint` leave the search and the texts it finds
  as they are, but they change the answer: its own name follows it, its group
  wins a tie between two groups of equal fit (so, rarely, another answer gives
  another tie), and they can make the top result not a text match, so that
  `TEXTS` is empty. `only_spdx` and `only_common` do not touch it. The answer's
  own text shows as the ID of `EXPRESSION`; any other text is named as `detect`
  names a text whose variant is not stated under `--variant`: `-or-later` under
  `or-later`, else `-only`; a group of licences with the same text and neither
  form shows its shortest ID. A text of an exception (the GCC exception) is not
  in the database, so it is never listed. A notice or a pointer, such as
  Apache's "Licensed under the Apache License" header, is not a whole text:
  `TEXTS` does not hold the answer and `COVERAGE` is under 0.8. A text that is a
  close look-alike of another (two BSD-3-Clause variants that differ in a few
  words) is named only when no other text fits the same part about as well; else
  the part names nothing. A record of no answer has `TEXTS` empty; to see the
  record of a candidate use `--threshold 0 -v`.

<!-- markdownlint-disable MD013 -->

```text
$ licenseid detect -v --text "lorem ipsum dolor sit amet consectetur elit"
EXPRESSION=	METHOD=	EXACT=	SCORE=	SIMILARITY=	COVERAGE=	VARIANT_STATED=	SAME_TEXT=	REASON=no match	TEXTS=
```

<!-- markdownlint-enable MD013 -->

<!-- docs-example: skip: the long-text fixtures hold no MPL-2.0 text -->

<!-- markdownlint-disable MD013 -->

```text
$ licenseid detect -v --top 2 LICENSE
EXPRESSION=MPL-2.0	METHOD=text	EXACT=true	SCORE=1.0000	SIMILARITY=1.0000	COVERAGE=1.0000	VARIANT_STATED=	SAME_TEXT=MPL-2.0-no-copyleft-exception	REASON=	TEXTS=MPL-2.0
EXPRESSION=MPL-2.0-no-copyleft-exception	METHOD=text	EXACT=true	SCORE=1.0000	SIMILARITY=1.0000	COVERAGE=1.0000	VARIANT_STATED=	SAME_TEXT=MPL-2.0	REASON=	TEXTS=MPL-2.0
```

<!-- markdownlint-enable MD013 -->

## Which field to read

- Is there an answer? The exit code (0, or 1 for none). `--threshold` is read
  on `SCORE`, which only ranks the results.
- How well does it fit? `SIMILARITY`, from 0 to 1.
- Whole text or fragment? `COVERAGE`: under 0.8 a fragment, such as a notice
  or a pointer; from 0.95 to 1.05 about the whole text; well above 1 the
  input holds more than that text.
- Which whole texts does the file hold? `TEXTS`.

A caller that declares one licence for a file can use this rule: declare
`EXPRESSION` when `METHOD` is not `text`, or when `TEXTS` is exactly
`EXPRESSION`. Otherwise read `TEXTS`:

- empty, with `COVERAGE` under 0.8: a notice or a pointer, not a text;
- empty, with `COVERAGE` about 1 or more: a whole text that `TEXTS` could
  not confirm (a look-alike was too close, or the wording differs from the
  List's);
- one ID other than `EXPRESSION`: the answer is in doubt;
- several IDs: the file holds several texts.

Under `below threshold` the nearest candidate is not named on
purpose: no answer beats a doubtful guess. `licenseid detect --threshold 0
--top 1 -v` shows it.

## JSON

JSON (the full record, with or without `-v`):

```bash
licenseid detect LICENSE.txt --json
```

Example output, in JSON Lines: one object per result per line, in the
JSON Canonicalization Scheme (RFC 8785), so equal results print equal bytes
(`jq -s .` makes an array of them):

<!-- docs-example: run: licenseid detect --json LICENSE.txt; head -->

<!-- markdownlint-disable MD013 -->

```json
{"coverage":1,"exact":true,"expression":"Apache-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"lists":[{"id":"spdx-license-list","id_authority":true,"license":"CC0-1.0","name":"SPDX License List","provides":["deprecation","ids","names","texts"],"source":"database","url":"https://github.com/spdx/license-list-data/releases/tag/v3.29.0","version":"3.29.0"}],"method":"text","reason":null,"same_text":null,"score":1,"similarity":1,"texts":["Apache-2.0"],"variant_stated":null}
{"coverage":0.9236,"exact":false,"expression":"ECL-2.0","is_fsf_libre":true,"is_osi_approved":true,"is_spdx":true,"lists":[{"id":"spdx-license-list","id_authority":true,"license":"CC0-1.0","name":"SPDX License List","provides":["deprecation","ids","names","texts"],"source":"database","url":"https://github.com/spdx/license-list-data/releases/tag/v3.29.0","version":"3.29.0"}],"method":"text","reason":null,"same_text":null,"score":0.9584,"similarity":0.9584,"texts":["Apache-2.0"],"variant_stated":null}
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

<!-- docs-example: run: licenseid detect -v LICENSE --diff --top 1; head;
filled: 2024 Jane Doe -->

<!-- markdownlint-disable MD013 -->

```diff
EXPRESSION=Apache-2.0	METHOD=text	EXACT=false	SCORE=1.0000	SIMILARITY=0.9978	COVERAGE=0.9987	VARIANT_STATED=	SAME_TEXT=	REASON=	TEXTS=Apache-2.0

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

<!-- markdownlint-enable MD013 -->

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
  record, every field empty but `REASON`: `detect` on exit 1 prints
  `EXPRESSION=` and the other keys with nothing after the `=`, and
  `REASON=` with why (`no match`).
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

<!-- docs-example: skip: the grammar of a line, not a line -->

```text
LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]
```

For example:

<!-- docs-example: skip: failures, pinned by tests/test_cli_errors.py,
tests/test_cli_usage.py and tests/test_spdx_source.py -->

```text
ERROR: database: not found: /tmp/x.db; run 'licenseid update'
ERROR: option: not found: --jsn; did you mean --json
WARNING: popularity.csv: download failed: ConnectionError: x; using stale cache
```

`LEVEL` is `ERROR` (the command fails) or `WARNING` (it continues).
`SUBJECT` is the thing affected, such as `database`, `directory`, `input` or a cache
file name, so `cut -d: -f1-3` gives the level, subject and condition.

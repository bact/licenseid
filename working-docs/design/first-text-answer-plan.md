---
Created: 2026-11-28
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
status: plan, nothing built; for the maintainer to decide
---

# Plan: the first whole text of a file gives no answer

Roadmap item 82 ([tech-debt-roadmap.md](tech-debt-roadmap.md)), with
question 5 of
[texts-ranking-evidence-plan.md](texts-ranking-evidence-plan.md). Nothing
here is built. The measures come from a prototype kept outside the
repository (section 10).

Short answer: on 500 real licence files, 38 have no answer though the
search finds a text whole. In 12 the top row names that text under 0.85, and
all 12 are right. In 26 the first-text rule took the answer away; the first
text is right in 23 and wrong in 3, and nothing in the file tells which.
Recommended for 0.10.1: documentation only, for both kinds. An answer for
the 12 (a floor on `SCORE`, section 5.3) is measured and can follow; it adds
one wrong golden row and wrong answers on made-up files.

## 1. What was measured

- **Tree:** `main` at `998de9d` (0.10.0 with pull requests 256 and 257),
  extracted with `git archive`; the prototype is a copy of it with a switch
  read from the environment, so base and prototype ran in one process on
  one database.
- **Database:** `licenseid --db <file> update --source packaged` under a
  scratch home (List 3.29.0, no popularity file). Python 3.10, macOS,
  2026-11-28, a busy machine: read CPU seconds as ratios.
- **Real files (500):** every file named `LICEN*`, `COPYING*` or `NOTICE*`
  in a `.dist-info` folder of the Python environments of this machine and of
  Pitloom's, read in place, unique by SHA-1. They hold the 300 real files of
  the speed gate's corpus. 46 sit in a subfolder (a vendored project's own
  file).
- **Labels (weak):** the corpus labels for its 300 files; for the others the
  package's `License-Expression`, else `License`, else its trove
  classifiers, each read by `resolve()`: 409 files have one. A file in a
  subfolder carries its package's label, not its own project's. Twelve
  files with a text found and no answer had no label (`License: BSD` and
  the like); they were labelled by hand from what the project states
  (eleven `BSD-3-Clause`, one `BSD-2-Clause`).
- **Gate inputs (1,368):** `core` without its real files (568), `prose`
  (473), `many` (183), `cjk` (24), `roadmap` (120). Not `options`, `stress`,
  `damage`.
- **Fixtures:** the ten recipes of `tests/fixtures/several-texts/`, and
  `python -m tools.golden` on the prototype tree.

A label "holds" an ID when the two are equal without `-only`, `-or-later`
or `+`, as the speed gate compares them.

## 2. The eight files of item 82 on the current tree

All eight still give no answer. `COVERAGE` reads 1.0000 where 0.10.0 read
2.1059 (mdurl) to 17.9824 (ruff): pull request 257 caps it.

| File | `--top 1 -v` | `--threshold 0`, first row |
| --- | --- | --- |
| mdurl 0.1.2 | `below threshold`, `TEXTS=MIT` | `MIT` 0.6730, sim. 0.6413 |
| tqdm 4.70.1 | `below threshold`, `TEXTS=MIT` | `MIT` 0.7565, sim. 0.7248 |
| ruff 0.17.6 | `below threshold`, `TEXTS=MIT` | `MIT` 0.1624, sim. 0.1051 |
| sympy 1.14.0 | `below threshold`, two texts | `BSD-3-Clause` 0.3554 |
| numpy 2.2.6 | `several texts`, three texts | no row |
| mypy 2.4.1 | `several texts`, three texts | no row |
| librt 0.17.0 | `several texts`, three texts | no row |
| exceptiongroup 1.3.2 | `several texts`, two texts | no row |

`TEXTS` is as item 82 gives it (`BSD-3-Clause MIT` for sympy;
`BSD-3-Clause BSD-3-Clause-Open-MPI GPL-3.0-only`; `MIT Python-2.0.1
BSD-2-Clause` twice; `MIT PSF-2.0`). The second row of sympy is
`BSD-2-Clause` 0.3167; the other files of D1 have one row.

## 3. Counts

### 3.1 Real files

| Today | Files | First ID of `TEXTS` |
| --- | ---: | --- |
| An answer at 0.85 | 441 | (not asked) |
| `below threshold`, no text found | 9 | none |
| (a) `below threshold`, one ID | 7 | in the label: 7 |
| (b) `below threshold`, several IDs | 5 | in the label: 4; not: 1 |
| (c) `several texts` | 26 | in the label: 23; not: 3 |
| `no match`, no text found | 12 | none |

In (a) and (b) the first row names the first ID of `TEXTS` in all 12. No
file has a row and a first text of another licence under 0.85: the
first-text rule empties those, so they are in (c).

- **(a)** `0d190d38`, `e57d6584` (tqdm; label `MIT, MPL-2.0`), `2e9aec16`,
  `aaf1f9bb` (a `NOTICE` file), `b87bd47e` (mdurl), `e5347d3a` (ruff),
  `66db5e89` (`ISC` 0.7156). Scores 0.65 to 0.76, ruff 0.16. The text found
  starts 0 to 145 words into the file and is 6 % (ruff) to 57 % of its
  characters.
- **(b)** `50faca55`, `df1c41ca`, `9f2226b9` (`Apache-2.0` 0.6654),
  `a4bb1d83` (sympy; by hand) are right. `1503319e` is the one "not": the
  licence file of a project vendored in numpy (`Apache-2.0` 0.7784 first,
  then `BSD-3-Clause`), in a subfolder; the label is numpy's. `Apache-2.0`
  is right for that file and wrong for the package.
- **(c), right (23):** `0720f4f1`, `084d0531`, `4de80313`, `b1a7c6c0`,
  `89c88cfa`, `636eda03`, `7f801a59` (`MIT` first, then `PSF-2.0` or
  `Python-2.0.1`), `0a5d3f3c`, `eeb40992`, `51cdf110`, `8691c5c4`,
  `b1420485`, `87f0e233`, `83ca45a1`, `8610fe4d`, `ff9f62f1`, `ea824677`,
  `f787a8aa`, `b291a42f` (`BSD-3-Clause` first), `242ec6ab` (`Apache-2.0`),
  `20180a68`, `4fafe3eb` (`MIT-CMU`, then 12 and 13 others), `f8fd26ad`
  (`0BSD`, a file of two alternatives: label `0BSD, CC0-1.0`).
- **(c), wrong (3):**
  - `bf1dc4ac` (pytype `LICENSE`): a vendored `MIT` text first, the
    project's own `Apache-2.0` after it.
  - `2ca02b23` (a `NOTICE` file): third-party terms; `BSD-2-Clause` first,
    label `BSD-3-Clause`.
  - `6c8dffbc` (a `LICENSES.third-party` file): `MIT` first, the package is
    `BSD-2-Clause`, and no text of the file is the package's.

  Two of the three are told by the file's name, which only the caller
  sees. The third cannot be told (section 6).

The gate corpus alone (300 files): (a) 4, (b) 2, (c) 15.

The stated licence against `TEXTS`, in (c): the label holds exactly one ID
of `TEXTS` in 24 files, two in 1, none in 1 (`6c8dffbc`). For pytype it is
`Apache-2.0`, the right one.

### 3.2 The rule "answer the first text found" against today's answers

Of the 441 answers, the first ID of `TEXTS` is another licence in 2:
`83a1fcfd` (`LGPL-2.1-or-later` 0.9187 from a marker, `TEXTS=NCL`; the
label is `LGPL-2.1-or-later`) and `f3b34c66` (`Apache-2.0` 0.9187,
`TEXTS=BSD-3-Clause`; no label). So the rule applied to every file would
turn one right answer wrong. Applied only where there is no answer today it
changes none, by construction; the prototype confirms it: 0 answers lost
and 0 changed on the 500 real files and the 1,368 gate inputs.

### 3.3 Made-up files

- **`tests/fixtures/several-texts/` (10):** none is (a) or (b). Five are
  (c): the first text is the project's own in 2 (`mit-then-gpl3`,
  `numpy-like`), one of two alternatives in 1 (`or-file`), and wrong in 2
  (`mit-then-apache`, the pytype case; `own-not-found`, where the own terms
  are no List text).
- **`many` (texts joined, some with 2 % or 5 % of words changed; 153 with
  no answer and a text found):** the first text found is the first text of
  the file in 89 and a later one in 64. The search does not find every text
  (a changed one, a short one), so "first found" is not "first in the
  file". Of the 23 with a row under 0.85 that names the first text found, 7
  are (a) with 1 right, and 16 are (b) with 9 right.
- **`prose` (62 with no answer and a text found):** 5 READMEs that hold the
  MIT text at their end, 4,100 to 5,700 words in (the package is MIT); 15
  source files with a licence text as their header; 42 made-up files of
  texts and prose.
- **Golden:** section 7.

## 4. What the three kinds have in common

In (a) and (b) the ranking and the search agree on the licence, and only
the score is low: similarity is measured on the whole file, and the file
holds more. In (c) they disagree: the ranking's first row is not the first
text, so `firsttext` gives no result. An answer for (c) would not lift a
row; it would make one from the search alone.

## 5. Options

### 5.1 Documentation only

No result changes. The caller rule of `docs/output.md` gains the record of
no answer, and `docs/python-api.md` the same for `detect()`:

- A first result under the caller's threshold whose `texts` starts with its
  `expression`: the file holds that licence's text whole, first, and holds
  more. On the CLI: `REASON=below threshold` with `TEXTS`; the first ID is
  that licence (true in 12 of 12 real files, and by construction: section
  3.1).
- No result and `texts()` of two IDs or more (`REASON=several texts`): the
  first ID is the text the file gives first; right in 23 of 26 real files.

Gains: Pitloom can declare all 12 files of (a) and (b) and, at its own
risk, the 26 of (c), in 0.10.1, with no change to any field. Pitloom calls
`detect()` and reads the score itself, so it has the rows already.
Loses: `licenseid detect LICENSE` still prints an empty line for mdurl.

### 5.2 An answer, its similarity measured on the span found

Where the first row is a text match, not exact, and its text is the first
text found, its `SIMILARITY` and `COVERAGE` are those of the span the
search found, and `SCORE` follows. Two forms were prototyped:

- the fit the search already has (`textlocate.Fit`: the span against the
  text, its variable parts left out), no new comparison;
- `detect()` of the span alone, one more Tier 2 score.

Both change what `SIMILARITY` and `COVERAGE` mean for such a row: "the
part of the input that holds the text", the mirror of today's rule for a
fragment ("the best-aligned part of the text"). That is a change to two
result fields: ask first.

### 5.3 An answer, by a floor on the score (simpler)

Where the first row is a text match, not exact, and its text is the first
text found, its `SCORE` is at least the fit of the span found (0.95 to 1,
the number `wholetexts` already has). `SIMILARITY` and `COVERAGE` stay as
measured on the whole file. No field changes its meaning: `SCORE` "ranks"
and "is no measure of fit" today, and a marker's floor already gives a
score of 1 beside a low similarity. One place (`firsttext.settle_texts`,
which holds the row, the search and the first text), one sentence in the
docs. `wholetexts.Found` would carry the fit of the first span: an internal
type, no public name.

### 5.4 What each field reads (mdurl 0.1.2)

| Field | Today, `--threshold 0` | 5.2, fit | 5.2, span alone | 5.3 |
| --- | --- | --- | --- | --- |
| `SCORE` | 0.6730 | 1.0000 | 1.0000 | 1.0000 |
| `SIMILARITY` | 0.6413 | 1.0000 | 0.9826 | 0.6413 |
| `COVERAGE` | 1.0000 | 0.9658 | 0.9702 | 1.0000 |
| `EXACT` | false | false | false | false |
| `METHOD` | text | text | text | text |
| `REASON` | (answer row) | empty | empty | empty |

`EXACT` stays false in every form: the input is more than the text (the
span alone would read `true` for a verbatim text; the file is not). The
fit reads 1.0000 for 33 of the 38 real files, since a copyright line is a
variable part; the span alone reads 0.93 to 1.0. `REASON` is empty because
there is an answer; with 5.1 it stays `below threshold`.

### 5.5 Scope of an answer, and what it gains and loses

| Scope | Real, gained | Real, wrong | Made-up, wrong |
| --- | ---: | ---: | --- |
| One text found, the row names it | 7 | 0 | 6 `many`, 1 golden row |
| The first of any, the row names it | 12 | 0 (1 by label) | 13 `many`, 1 golden row |
| The first text, with no row (c) | 26 | 3 | 2 of 5 fixtures |

The "1 by label" is `1503319e` (right for the file). No answer is lost or
changed in any scope. The wrong ones:

- `many`, 6 and 13: a file of 2 to 15 joined texts where the search finds
  one alone, or one first, because the texts before it are changed. The
  file's own first text is another. A real file like it: own terms that
  are no List text, then one bundled text (the `own-not-found` fixture, and
  Pillow before item 64).
- Golden `short/Abstyles/tail_1500`: the last 1,500 characters of the
  `Abstyles` text hold the `Linux-man-pages-copyleft-2-para` text whole
  (roadmap item 77), so the fragment answers that licence at 0.9694 where it
  gave no answer (0.7411). A new wrong answer above the threshold.
- Other answers gained on made-up inputs are right or cannot be judged: 5
  READMEs (`MIT`), 15 source files with a text as header, 3 re-wrapped
  `CC-BY-SA-2.1-JP` texts (0.58 to 0.76 today), 10 files of two texts.

Other rows that move: the floor lifts a row that already answers (`MIT`
0.9197 to 1.0): 72 of the 441 real answers (one text; 78 with the first of
several) change `SCORE` and keep their place. A floor that only acts under
a bar would avoid it and put a threshold inside the library; not
recommended.

A guard by position ("the text starts in the first 200 words") would keep
the 12 real files (0 to 145 words) and drop the made-up wrong ones (270
words and more) and the READMEs. It is a number fitted to this count, 125
words wide: not recommended.

### 5.6 Time

One process, base first, then the prototype, the same inputs, CPU seconds:

| Set | Base | 5.3 or 5.2 with the fit |
| --- | ---: | ---: |
| Real (500) | 13.82 | 13.91 |
| `core` (568) | 17.60 | 17.78 |
| `prose` (473) | 7.77 | 7.89 |
| `many` (183) | 88.48 | 88.03 |
| `roadmap` (120) | 2.81 | 2.86 |
| `cjk` (24) | 0.42 | 0.41 |

No new search and no new alignment: the search of `firsttext` already ran
and kept the fit. The differences are noise (1 % at most, both ways; no A/A
twin was run). The span alone (5.2, second form) is one more call: 0.61 s
on the 38 real files, whose calls take 5.16 s (12 % of those, 4 % of the
set).

## 6. A vendored text that comes first

It cannot be told from the file. Measured on the three wrong files and the
23 right ones of (c):

- where the first text starts: 12 to 113 words in for the wrong, 0 to 140
  for the right;
- its share of the file: 5 % to 8 % for the wrong, 2 % to 39 % for the
  right;
- how many texts follow: 1 to 4 for the wrong, 1 to 13 for the right.

What a caller has and licenseid does not:

- the file's name: `NOTICE` and `LICENSES.third-party` are two of the
  three;
- the licence the package states: a stated licence that `TEXTS` holds is
  confirmed by the file, wherever its text stands (pytype: `Apache-2.0`,
  the second ID). The first ID alone is then only for a package that
  states nothing.

The same holds for own terms that are no List text before a bundled one:
the search sees one text, first, and nothing says that more came before
it.

## 7. What would move in the golden

- 5.1: nothing.
- 5.2 and 5.3, either scope with a row (`python -m tools.golden` on the
  prototype tree, both scopes): `long`, `mixed`, `id`, `name`, `value`,
  `several` and `cli` "as the golden"; `short` moves one row,
  `short/Abstyles/tail_1500`, from `Linux-man-pages-copyleft-2-para` 0.7411
  to 0.9694: a wrong answer, to list in `tests/harness_changes.py` with
  that reason, or the cause to cure first (item 77).
- The scope with no row (c): the five `several` rows that
  `harness_changes_firsttext.py` moved to no answer would move again, two
  of them to a wrong answer.

## 8. Tests and docs each option needs

**5.1, documentation only:**

- `docs/output.md`: the caller rule (the two bullets of 5.1), the file
  name and the stated licence of section 6, and the sentence under
  `below threshold` ("the nearest candidate is not named on purpose"):
  with `TEXTS` it is named by `TEXTS`.
- `docs/python-api.md`: the same rule for `detect()` and `texts()`.
- `tests/test_docs_examples.py`: a block for a file of the mdurl kind (a
  fixture made from the MIT text of `license-text-long` and a second
  grant, not a real file), `COUNTS` raised; `test_docs_vocabulary` as it
  is.
- One test that pins what the rule rests on (`tests/test_firsttext.py`): a
  row under 0.85 with `texts[0]` equal to its `expression`, on a database
  seeded with the near MIT texts.
- `CHANGELOG.md`: nothing (documentation only). Roadmap item 82: the count
  and the decision; item 68: closed for its four files.

**5.3, the floor (5.2 the same, with the two fields):**

- Unit rows on `settle_texts`: lifted when the row's text is the first
  found; not when it is another text of the file, when exact, when the
  method is not `text`, when nothing is found; the scores written out
  (0.6730 beside a fit of 1.0; 0.9197 beside 1.0).
- Through `detect()`, on a database with the near neighbours: the mdurl
  kind answers `MIT`; the sympy kind `BSD-3-Clause` (if that scope is
  taken); the pytype kind still gives nothing; a notice with no text found
  is not lifted; the `Abstyles` tail as a pinned `# BUG:` row or cured.
- `tests/test_option_matrix.py` runs as it is (no new option);
  `test_output_pattern` too.
- Mutants: the floor removed; applied to a row whose text is not first;
  applied to an exact row; applied to the second row; the fit of another
  span read.
- Docs: `docs/output.md` (`SCORE`: the floor of a text found whole;
  `REASON`), `docs/how-it-works.md`, `docs/python-api.md`, `CHANGELOG.md`
  "Changed", a behaviour change. For 5.2 also the definitions of
  `SIMILARITY` and `COVERAGE` and `types.Detection`'s docstring.
- Before the pull request, once: the full suite, the full `tools.golden`,
  `tools.cli_matrix --check`, the speed gate against `v0.10.0` with an A/A
  twin, one independent adversarial review with the sets of item 77.

## 9. Recommendation

**0.10.1: documentation only (5.1), for D1 and D2.**

- It gives Pitloom what it asks for D1 ("or else a documented way to read
  the same") at once, with no result changed, and 0.10.1 already carries
  two behaviour changes.
- For D2 nothing better exists: 3 of 26 first texts are wrong, the file
  does not tell which, and the caller holds the two signals that help (the
  file's name, the stated licence).
- An answer for D1 is cheap and right on every real file counted (12 of
  12), but it is a new answer rule: it adds a wrong golden answer (the
  `Abstyles` tail) and answers a bundled text where the search cannot see
  what came before it. Precision over recall: measure it on files from
  outside this machine first.

**After 0.10.1, if an answer is wanted: the floor (5.3), not 5.2.** It
changes no field's meaning and costs nothing. Scope: the first text, named
by the first row (12 files); the narrower scope saves 7 made-up wrong
answers and loses sympy and four more real files. Never an answer for (c).

**What to tell Pitloom** (with 0.10.1):

- D1: when the first result of `detect()` is under your threshold, its
  `method` is `text` and `texts[0]` is its `expression`, the file holds
  that licence's text whole and first; declare it as you declare an
  answer. All four of your files read so
  (mdurl, tqdm, ruff, sympy). No release changes the fields.
- D2: `detect()` gives no result because the ranking's first licence is
  not the first text; `texts()` gives the texts in file order. The first
  ID is the project's own in 23 of 26 files counted. Prefer the licence
  the package states when `texts()` holds it; do not read the first ID of
  a file named `NOTICE` or `*third-party*`. A vendored text first (pytype)
  cannot be told from the file.
- D4 (exception texts, item 70) is not part of this.

## 10. Where the prototype is

Outside the repository, in a scratch folder a reboot may clear:

<!-- markdownlint-disable MD013 -->

```text
/private/tmp/claude-501/-Users-arthit-projects-licenseid/94735f6a-7da4-47fd-95d1-deaec6fe3175/scratchpad
```

<!-- markdownlint-enable MD013 -->

`base/` and `proto/` are the two trees (`diff -ru base/src proto/src`: 83
lines, in `wholetexts.py` and `firsttext.py`; the switch is
`LICENSEID_PROTO=all` or `one`); `scripts/` holds the runs and counts;
`out/` their results by file key (rows and counts, no file content).

Not measured: Windows, `tools.cli_matrix`, the hold-out files, the speed
gate with an A/A twin, `--pop`, the options set.

## 11. Open questions

1. Documentation only in 0.10.1? Recommended: yes (section 9).
2. Build the floor (5.3) after 0.10.1? Recommended: yes, once a count on
   real files from outside this machine shows no wrong answer; not in
   0.10.1.
3. If the floor is built: the first text of several too (sympy), or one
   text only? Recommended: the first of several too; it is the reading the
   first-text rule already gives an answer above 0.85.
4. If the floor is built: may `SCORE` of rows that already answer rise
   (78 of 441 real answers)? Recommended: yes; a floor that acts only under
   0.85 puts the caller's threshold in the library.
5. The `Abstyles` tail (a fragment that holds a nested text whole): accept
   as a listed golden change, or cure with item 77 first? Recommended: cure
   first; it is a wrong answer above the threshold.
6. Should `SIMILARITY` ever be measured on the span (5.2)? Recommended:
   no; `TEXTS` already says the text is whole, and the field keeps one
   meaning.
7. An answer for `several texts` (D2)? Recommended: no; 3 of 26 wrong and
   not told apart.
8. Say in `docs/output.md` that a caller should prefer the stated licence
   that `TEXTS` holds, and mind the file's name? Recommended: yes; it is
   the only measured way to the pytype answer.
9. Close item 68's four files and item 82 with the documentation, or keep
   82 open for the floor? Recommended: keep 82 open, cut down to the floor
   and its hold-out count.

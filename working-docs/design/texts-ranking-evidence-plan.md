---
Created: 2026-11-28
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
status: rule (sections 1 to 6) built 2026-11-28; cap (section 7) not built
---

# Plan for 0.10.1: `TEXTS` as ranking evidence

Roadmap items 68 and 13 ([tech-debt-roadmap.md](tech-debt-roadmap.md)), with
finding 3 of item 80
([tech-debt-roadmap-reading.md](tech-debt-roadmap-reading.md)) as a separate
small step. Nothing here is built. The measures of section 3 come from a
prototype kept outside the repository.

Decided by the maintainer on 2026-11-28: a runner-up that `TEXTS` does not
name is not listed beside a text found whole, so a verbatim Apache 2.0 file
answers `Apache-2.0` alone; the public result caps `coverage` at 1.

## 1. The rule

Beside a text that the whole-text search finds alone, `detect()` lists the
licences of that text and no look-alike: the runner-ups Tier 2 scores
beside it are never listed.

"Found alone" is today's narrowing, unchanged: the search made with no
answer finds exactly one text, the guard does not hold (no other text shares
more than 1.1 times the word 3-grams the text found shares), and the filters
leave a licence of that text. "The licences of that text" are its same-text
group (`GPL-3.0-only` and `GPL-3.0-or-later`; the five `GFDL-1.3` forms).
"Runner-ups" are, as today, the first three other texts by gram score that
reach 0.1. A licence that only a marker or a hint brings in is no runner-up
and stays, as today (question 1).

The rule removes rows. It makes no answer and refuses none: since 0.10.0 a
runner-up already ranks under the text found or is left out
(`ranking.under_found`), so the first row is the same with and without the
runner-ups (measured, section 3).

## 2. Where it lives

One place, `ranking.under_found`, which gets simpler: where a member of the
group is ranked, it leaves out every runner-up, not only one that scores as
high as the group's best. Its comparison of scores goes; its signature, its
one call (`LicenseDetector._run_tier1_and_tier2`) and
`gramselect.narrowed` stay. No rule is added.

No licence is named in the code, and no pair of licences. The Apache 2.0,
`Pixar` and `ImageMagick` case is the general case of a look-alike beside a
text found whole.

A second form was measured and is not recommended as it stands (section
3.4): the runner-ups not scored at all (`narrowed` gives the group only,
`under_found` deleted). It is less code and less CPU time, but it is not the
same rule: a look-alike that a marker also names is then no runner-up, so
it comes back as a row and can rank first.

## 3. What was measured

Tree: `main` at `350e1b6` (release 0.10.0), extracted to a scratch folder,
with the rule behind a switch, so base and rule ran in one process on one
database. Database: `licenseid update --source packaged` under a scratch
home (List 3.29.0, no popularity file). Python 3.10, macOS, 2026-11-28.

Inputs:

- The speed gate's inputs (`benchmarks/speedgate`, the corpus of the 0.10.0
  work): sets `core` (868), `prose` (473), `many` (183), `cjk` (24),
  `options` (36), `roadmap` (120); 1,704 inputs. Not `stress` and `damage`.
- The texts of the golden (`long` 185, `short` 695, `mixed` 209, `several`
  10; 1,099 inputs) on the same database, every row read; and
  `python -m tools.golden` itself on the prototype tree, on its own fixture
  databases.

Two forms were measured. **Rule A** is section 1. **Rule B** is a wider
reading of the decision: whenever the answer's text is among the texts
found, drop every row whose text is not found (several texts and the guard
included, marker rows too; an exact answer is not searched, so not
touched).

### 3.1 Reproducers on the current tree

Each on `350e1b6`, the rows of today, then rule A:

- **rfc8785 0.1.4 `LICENSE` (item 13): reproduces.** `Apache-2.0` 1.0000,
  `Pixar` 0.9947, `ImageMagick` 0.9871, `ECL-2.0` 0.9792, each with
  `TEXTS=Apache-2.0`; `COVERAGE=1.0179`. Rule A: `Apache-2.0` alone.
- **List text of `Apache-2.0` (exact): reproduces.** `ECL-2.0` 0.9584,
  `Pixar` 0.936 and `ImageMagick` 0.936 under it. Rule A: alone.
- **The same without its appendix:** answers `Apache-2.0` 1.0, `Pixar`
  0.9963 second. Rule A: alone.
- **List text of `Pixar`:** answers `Pixar`, exact, `Apache-2.0` 0.9945
  second. Rule A: `Pixar` alone.
- **List text of `ImageMagick`:** answers it, exact, `ECL-2.0` 0.9018
  second. Rule A: alone.
- **List text of `ECL-2.0`:** answers it, exact, `Apache-2.0` second at a
  public score of 1.0. Rule A: alone.
- **wcwidth 0.2.13 `LICENSE` (item 68): no longer reproduces.** `MIT`
  0.9197, not `JSON`; `MIT-0` 0.8321 and `HPND-Markus-Kuhn` 0.2903 under
  it. Rule A: `MIT` alone.
- **mypy_extensions 1.1.0 `LICENSE` (item 68): no longer reproduces.**
  `MIT` 0.9641, with `JSON` 0.9637 second, a near tie. Rule A: `MIT`
  alone.

The 25 files of item 68 (the `roadmap` set holds them by name: 23 real
files, wcwidth's and mypy_extensions' among them, and 2 of Pillow), read
again:

- 17 answer the text found at 0.85 or more (`MIT`, `BSD-2-Clause`,
  `BSD-1-Clause`, `BSD-3-Clause`); none answers a look-alike of it.
- The 2 Pillow files (11.2.1, 11.3.0) have no result and no `TEXTS`; the
  rule has nothing to act on.
- 4 name the text found in the first row under 0.85, so no answer:
  `2e9aec16` (`MIT` 0.6888), `aaf1f9bb` (0.6465), `b87bd47e` (0.673),
  `e57d6584` (0.7565). Each file is about twice the MIT text (coverage 1.85
  to 2.21). The rule does not touch the score.
- 2 answer a licence a marker names, with another text found:
  `83a1fcfd` (`LGPL-2.1-or-later` 0.9187, `TEXTS=NCL`, label
  `LGPL-2.1-or-later`) and `f3b34c66` (`Apache-2.0` 0.9187,
  `TEXTS=BSD-3-Clause`, no label). The rule keeps both answers.

Of the 300 real files, 250 have one text in `TEXTS`: 244 answer it at 0.85
or more, the 4 above name it under 0.85, the 2 above answer the marker's
licence.

### 3.2 Answers gained and lost

First row at 0.85, at 0.7 and at any score, base against rule:

| Inputs | A: gained, lost, changed | B: gained, lost, changed |
| --- | --- | --- |
| Speed gate sets (1,704) | 0, 0, 0 | 0, 0, 0 |
| Golden texts (1,099) | 0, 0, 0 | 0, 0, 0 |

`python -m tools.golden` under rule A: every part (`long`, `short`,
`mixed`, `id`, `name`, `value`, `several`, `cli`) "as the golden".

One labelled file has its label only in a removed row, under both rules:
`real:01a6b4bf:LICENSE`, label `LGPL-2.0-or-later`. Its answer is
`LGPL-2.1-only` at 1.0 (`TEXTS=LGPL-2.1-only`); the rows `LGPL-2.0-only`
0.958 and `LGPL-2.0-or-later` 0.948 go. The answer does not move, but a
reader of the lower rows no longer sees the labelled licence.

Rule B loses the label's row in three more real files: `d53306ef` and
`f1c3697b` (`NOTICE`, answer `BSD-3-Clause` 0.9402, label `Apache-2.0`,
the row `Apache-2.0` 0.9025 that a marker named) and `370f6b85` (answer
`Python-2.0.1` 0.872, label `MIT`, the row `MIT` 0.1689). Rule A keeps all
three.

### 3.3 Rows removed

| Count | Gate, A | Gate, B | Golden, A | Golden, B |
| --- | ---: | ---: | ---: | ---: |
| Inputs with a row removed | 587 | 479 | 311 | 26 |
| Rows removed, all rows | 1,695 | 1,385 | 888 | 75 |
| Inputs changed under `--top 3` | 562 | 466 | 296 | 25 |
| Rows removed under `--top 3` | 1,082 | 893 | 566 | 46 |
| Inputs that lose a row at 0.85 or more | 452 | 364 | 142 | 15 |
| Answers that lose a row within 0.01 | 140 | 123 | 40 | 1 |

By set, rule A (inputs with a row removed of inputs with a result): `core`
462 of 824, `roadmap` 69 of 114, `options` 25 of 26, `prose` 22 of 218,
`cjk` 6 of 24, `many` 3 of 60; golden `long` 163 of 185, `short` 144 of
695, `mixed` 3 of 176, `several` 1 of 5.

Rows that stay beside a text found whole, rule A: on 48 gate inputs and 22
golden texts a row of another licence stays. They are the same-text groups
(`GFDL`, `OFL`) and the licences a marker reads in the text: `AGPL-3.0-only`
beside the `GPL-3.0` and `LGPL-3.0` texts (15 inputs), `GPL-2.0-only`
beside `LGPL-2.1`, `GPL-2.0-or-later` beside `EPL-2.0`, `BSD-4-Clause` beside
`BSD-Attribution-HPND-disclaimer`. On 32 gate inputs such a row scores 0.85
or more. Two stay within 0.01 of the answer, both at a public score of 1.0:
`AGPL-3.0-only` beside `GPL-3.0-only` (`long:GPL-3.0-only:distorted_01`)
and `BSD-4-Clause` beside `BSD-3-Clause-Attribution` (golden `long`).

### 3.4 Filter after the ranking against not scored

Rule A as a filter (section 2) against the runner-ups not scored, every
row of every input (score, similarity, coverage, `TEXTS`), 2,803 inputs:

- 15 inputs differ. In each, a look-alike that was a runner-up is also
  named by a marker; not scored as a runner-up, it joins as the marker's
  candidate and is never left out.
- One first row moves: golden text `short/X11/head_1000`, `MIT` 0.9617
  (base and rule A; `TEXTS=MIT`, the head of `X11` holds the MIT text) to
  `X11` 1.0. The case's own ID is `X11`, so the move is to the labelled
  answer, but by a path 0.10.0 closed on purpose (a look-alike above a
  text found).
- 14 inputs get a row back. Four at the answer's public score of 1.0:
  `Sendmail` beside `Sendmail-8.23`, `BSD-3-Clause` beside
  `BSD-3-Clause-No-Military-License` (two inputs), `BSD-2-Clause` beside
  `BSD-2-Clause-first-lines`. Others: `BSD-2-Clause` 0.9713 beside
  `BSD-2-Clause-Views` (`real:d009e5ef`), `GPL-3.0-only` 0.97 beside the
  `LGPL-3.0` text in place of `AGPL-3.0-only` 0.91.
- CPU seconds, one process, the three forms interleaved, a busy machine
  (ratios only): `core` 19.7 base, 19.4 filter, 17.5 not scored; golden
  `long` 4.08, 3.96, 2.45; `options` 0.78, 0.75, 0.54; `many` 74.3, 73.6,
  73.7. Not scoring saves about a tenth of `core`.

The same edge shows inside rule A: which marker-named look-alike stays
depends on whether it is among the three runner-ups (`AGPL-3.0-only` stays
beside the `GPL-3.0` text, as the fourth; `GPL-3.0-only` goes beside the
`LGPL-3.0` text, as the first). Question 1 is about that edge.

### 3.5 Nested texts (item 77)

Six of the thirteen pairs, each as the outer text with every fifth word of
its own part replaced and as the inner text with the 30 words that follow
it: no first row moves. Where the inner text is found alone, the outer text
leaves the lower rows (`MPL-1.1` with 30 words: `NPL-1.1` 0.9427 was fourth;
`Caldera-no-preamble` with 30 words: `Caldera` 0.9932 was second). Item 77
stays open and is not made worse in its answers; its outer text is no
longer a row to read.

### 3.6 Not measured

- The review sets of item 77 (`.claude/speed-0-10/reviews/`), the hold-out
  set, Windows, `tools.cli_matrix`.
- CPU time on a quiet machine with an A/A twin (section 3.4 is one process,
  other sessions running).
- The prototype read no popularity file: `--pop` was not exercised.

## 4. What moves

- **Golden:** nothing, by the prototype (section 3.2). The build runs the
  full `tools.golden` again; `tests/harness_changes.py` gets no entry for
  this step.
- **Pinned tests:** `tests/test_whole_text_rules.py` (the `under_found`
  cases: a runner-up under the answer is left out too),
  `tests/test_detect_options_paths.py` (an input that holds MIT whole lists
  `MIT` and three runner-ups: now `MIT`),
  `tests/test_whole_text_first.py` (JSON over MIT: `JSON` is no row).
- **Docs examples:** `docs/output.md` shows `Apache-2.0` and `ECL-2.0` as
  "the first two results" of a verbatim Apache 2.0 file, as text and as
  JSON: one row now, so the example of several rows needs another input
  (a fragment, where the selection still lists look-alikes).
- **Pitloom:** its rule "the stated licence wins a near tie" no longer
  fires for a look-alike of a text found whole (a stated `Pixar` over a
  verbatim Apache 2.0 file, a stated `JSON` over a verbatim MIT file): the
  text found answers. Members of one same-text group are still listed.

## 5. Tests and mutation checks

New or changed tests:

- Rules on made-up tables (`tests/test_whole_text_rules.py`):
  `under_found` leaves out a runner-up above, at and under the group's
  best (the scores written out: 0.99 beside 1.0, 0.30 beside 1.0); keeps
  every member of the group; keeps a candidate that is no runner-up;
  changes nothing when no member of the group is ranked.
- Through `detect()` (`tests/test_whole_text_first.py`, in
  `tests/platform_files.py` already):
  - the rfc8785 0.1.4 `LICENSE`, a verbatim Apache 2.0 file, as a fixture
    (listed in `tests/fixtures/README.md`) answers `Apache-2.0`
    and lists nothing else, with `--top 5` and in the API;
  - the Apache 2.0 text without its appendix: the same;
  - a `Pixar` text answers `Pixar` alone, an `ImageMagick` text
    `ImageMagick` alone. The database is seeded with the four real texts
    (`Apache-2.0`, `Pixar`, `ImageMagick`, `ECL-2.0`): on a database
    without the neighbours the test passes whatever the code does;
  - a same-text twin stays (`GPL-3.0-only` and `GPL-3.0-or-later`);
  - a marker's licence and a hinted licence stay beside the text found;
  - the guard: an `SSH-short` text inside an `SSH-OpenSSH` head keeps the
    rows of the selection;
  - two texts found: the rows of the selection, as today;
  - `exclude` of the text found: the selection, as today; `exclude` of a
    look-alike changes nothing.
- CLI: `detect --top 5 -v` and `--json` of the fixture print one record
  (`tests/test_output_pattern.py` runs as it is; no new option, so no new
  axis in `tests/test_option_matrix.py`).

Mutants, each to be killed (a script that asserts the old text is there,
`__pycache__` cleared between runs):

- `under_found` keeps a runner-up that scores under the best (the code of
  0.10.0);
- `under_found` keeps every runner-up;
- `under_found` leaves out the members of the group too;
- `under_found` leaves out every row outside the group (the marker and
  hint tests must fail);
- `under_found` acts when no member of the group is ranked;
- the call in `_run_tier1_and_tier2` removed.

Checks before the pull request, once, after the last clean review round:
the full suite, the full `tools.golden`, `tools.cli_matrix --check` (the
rows of `detect` change), the speed gate against the tag `v0.10.0` with an
A/A twin, `pytest --run-benchmark`. One independent adversarial review of
the finished diff, with the review sets of item 77.

## 6. Docs

- `docs/how-it-works.md`, "Where that search finds one text alone": the
  three others are scored but never listed; the results are the licences
  of that text and those a marker or hint names. The clause on the one
  "left out" goes. Step 3 of the overview ("A text found whole comes
  first") gains "and no look-alike is listed beside it".
- `docs/cli.md`, `--top`: where the input holds one licence text whole, the
  results are the licences of that text and those a marker names.
- `docs/output.md`: the example of two rows (text and JSON) on another
  input; a sentence under `TEXTS`: an answer that `TEXTS` names alone has
  no look-alike under it.
- `docs/python-api.md`: the same sentence where `detect()`'s list is
  described.
- `CHANGELOG.md`, section 0.10.1, "Changed", marked as a behaviour change:
  beside a licence text found whole, `detect` no longer lists look-alikes
  (`Pixar` under a verbatim Apache 2.0 file); the answer is unchanged.
- `working-docs/implementation/whole-text-first.md`: a section for this
  step (the rule, the measures, the paths rejected: rule B).
  `working-docs/paper-notes/results-0-10.md`: the row counts of section 3.3
  as a finding. Roadmap items 13 and 68: closed or cut down (questions 5
  and 6).
- `tests/test_docs_examples.py` `COUNTS` and `test_docs_status` follow.

## 7. Cap `coverage` at 1, a separate small step

A pull request of its own, after the rule or before it; neither needs the
other.

- **Code:** `result.public_result` gives `coverage` as it gives `score`:
  capped to 1, then rounded. One line. `RawMatch` and `InternalMatch` keep
  the raw value: `markerfloor` (above 1.05), `similarity` (the bonus from
  0.95 to 1.05) and `firsttext` read it before the public form. No key
  changes; None stays None.
- **What moves:** on the gate sets 541 of 1,226 first rows have a coverage
  above 1 (2,122 of 5,329 rows; the highest 263.8 on a first row, a
  README). Of 264 real files that answer, 184 are above 1 and 52 above
  1.05 (highest 3.68). The detect golden holds no coverage; 2 of the 118
  rows of `cli.jsonl` do and move (`CLI_CHANGES`).
- **Tests:** a unit row on `public_result` (1.0179 gives 1.0; 0.9987 stays;
  None stays; the raw match is not changed); the rfc8785 fixture prints
  `COVERAGE=1.0000` and JSON `1`; `tests/test_firsttext.py` reads a
  coverage between 1.0 and 1.05 and moves to the raw match
  (`_match_raw`). Mutants: the cap removed; the cap put on the raw match
  (the marker floor test of a file above 1.05 must fail).
- **Docs:** `docs/output.md` says `COVERAGE` "has no upper limit" and that
  "well above 1" the input holds more than the licence's text; both
  sentences go, and the reading guide ("about 1 or more") says "1".
  `docs/how-it-works.md` speaks of coverage 1.03 and 1.05 inside the
  ranking: say there that the ranking reads the value before the cap.
  `docs/python-api.md`: `coverage` is from 0 to 1. `CHANGELOG.md`: a
  behaviour change with the migration "a caller that clamped it can stop;
  a caller that read a value above 1 as 'more than one text' reads
  `texts`".

## 8. As built (2026-11-28)

The maintainer chose rule A. An independent review of the first build found
that it broke more than rows (`working-docs/implementation/whole-text-first.md`,
section 10): the steps after `under_found` read the runner-ups. As built,
a runner-up that a marker or `hint` names (either twin, by its stem) keeps
the rule of 0.10.0 and stays under the text found; every other runner-up
is left out. This answers question 1 for the runner-ups too: what the
input or the caller names stays. The counts of section 3 are the
prototype's; the built tree's are in the implementation note (1,684 rows
of 587 gate inputs, 881 of 311 golden texts, the first result equal in
every field).

## 9. Open questions

1. Do the licences a marker or a hint names stay beside a text found
   whole? Recommended: yes for 0.10.1, as today. They are what the file
   says; dropping them (rule B) loses the labelled licence's row in two
   real `NOTICE` files, and two real files answer a marker's licence above
   the text found. Cost: 32 gate inputs keep such a row at 0.85 or more,
   two of them at the answer's public score of 1.0 (section 3.3), and
   which marker-named look-alike stays depends on the three runner-ups
   (section 3.4).
2. Runner-ups scored and then dropped, or not scored? Recommended: scored
   and dropped (the form measured with no answer moved). Not scoring saves
   about a tenth of the `core` CPU time but moves one first row and gives
   14 rows back; take it only with a rule for a look-alike a marker names,
   measured first (roadmap item 78).
3. Does the rule reach an exact answer too (the List's own Apache 2.0 text
   loses its `ECL-2.0` row, and the docs example with it)? Recommended:
   yes: one rule for every text found alone; the narrowing does not ask
   whether the answer is exact.
4. Files of several texts, and inputs the guard holds, keep their rows as
   today? Recommended: yes for 0.10.1. Rule B changes 18 `many` inputs
   and 38 `prose` inputs and moves no answer, but it is a second place
   for the rule and it drops marker rows.
5. The four files that name the text found under 0.85 (a file twice the
   MIT text): leave them without an answer? Recommended for this step:
   yes, and take the question to roadmap item 82, not item 70 (item 70 is
   exception texts). Evidence added 2026-11-28, after the plan:
   - Pitloom asks for an answer there as its first priority (item 82, D1):
     mdurl 0.1.2 (`MIT` 0.6730, coverage 2.1059) and tqdm 4.70.1 (`MIT`
     0.7565, coverage 1.8529) are the files `b87bd47e` and `e57d6584` of
     section 3.1; ruff 0.17.6 (`MIT` 0.1624, coverage 17.98) and sympy
     1.14.0 (`BSD-3-Clause` 0.3554, `TEXTS=BSD-3-Clause MIT`) are new.
     D2 is the files of several texts (`REASON=several texts`: numpy,
     mypy, librt, exceptiongroup).
   - A first count for item 82, from the runs of section 3: of the 300 real
     files, 250 have one text in `TEXTS`; in 4 the first row names it under
     0.85, and the label of each of the 4 holds that licence (`MIT` three
     times, `MIT, MPL-2.0` once). No such file names a licence its label
     lacks. Files of several texts were not counted.
   - The recommendation stays, for a reason that the evidence does not
     touch: the rule of section 1 removes rows and was measured to move no
     first row; an answer for these files is a new answer, with a score to
     define (item 82: the similarity of the span found) and a count on the
     several-text files still to make. It is its own step, measured base
     against branch, and can ship in 0.10.1 beside this one if the
     maintainer decides so.
6. Close item 68 and item 13 with this step? Recommended: yes for 13 (its
   "done when" holds: Apache 2.0 alone, the file as a fixture, `Pixar`
   still `Pixar`); 68 closed with the four files of question 5 handed to
   item 82 and the two marker files (`83a1fcfd`, `f3b34c66`) to item 78.
7. Pitloom's "stated licence wins a near tie" stops firing for look-alikes
   (section 4): intended? Recommended: yes, and tell Pitloom in the
   release notes, since a stated `JSON` over a verbatim MIT text then
   reads as a conflict, not a tie.
8. The cap hides "this file holds more than the text" (184 of 264 real
   answers are above 1): still cap? Recommended: yes, as decided: `TEXTS`
   and `EXACT` say it, and the value above 1 grows with any prose in the
   file, not with licence text.
9. One pull request or two? Recommended: two (the rule; the cap), one
   release.

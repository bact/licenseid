---
Created: 2026-11-27
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Whole text first (0.10.0 task T5)"
---

## Whole text first (0.10.0 task T5)

Status: task T5 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`, sections 3.1 steps 5 to 7 and
3.5), built 2026-11-27 on the T4 tree ([word-region.md](word-region.md)),
not merged. Measurements: Apple M-series, Python 3.10, SPDX License List
3.29.0, the harness of `.claude/speed-0-10` (side `T5-1`) against layer 10
(the T4 tree, side `L10`) and the 0.9.4 baseline, and runs of the harness
sets on both trees side by side in one session.

### 1. What was built

- `textcandidates.TextCandidates`: the whole-text search of one input. Made
  once a `detect()` or `texts()` call, it holds the input's gram score table
  (looked up at its first use), cuts the List's corpus to the texts
  `gramselect.searched` names, and keeps each search it makes. Every reader
  of `wholetexts.found_texts` asks it: the narrowing of Tier 2
  (`retrieval`), `markerfloor`, `firsttext`, `textnames` and
  `LicenseDetector.texts`. It is the one owner task T6 loads stored texts
  through.
- `gramselect.searched`: the texts searched are the first 20 of the
  unfiltered table by score and every other text `is_held` (the input
  holds half of its grams, or of its core's where that is smaller; the
  core's distinct grams are counted on its codes, once a process,
  `CodedText.gram_count`, and only asked of a text that falls short alone).
- Narrowing (`retrieval._narrowed`, `gramselect.narrowed`): over the none
  bar, the search runs with no answer; where it finds exactly one text,
  Tier 2 scores the members of that text's same-text group that the filters
  leave, then the first three other filtered texts by score that reach 0.1.
  Not when `gramselect.guarded` holds (another text of the unfiltered table
  shares more than 11/10 of the grams of the group's best member), nor when
  the filters took every member out.
- `ranking.under_found`: after the ranking, a runner-up scoring as high as
  the best member of the group or higher is left out (decision Q1).
- `variants` sorts with `ranking.ranking_key` (plan 3.4), the popularity
  flag passed down (`settle_free_text(popular=...)`).
- Otherwise (no text, several, the guard, a filtered text) the selection of
  task T3, unchanged.

### 2. Decisions beyond the plan

- **A search an answer group, and one shortcut.** A search ranks the
  answer's group first among equal fits, so each answer group is a search
  of its own (`TextCandidates.found`). The search made before Tier 2 has no
  answer; it stands for the answer's when it found nothing or the answer's
  text alone (the prototype's rule). Measured: the answer's search equals
  the search with no answer on every input of six sets (section 4), several
  texts found included.
- **No search under the none bar.** Step 4 of the plan comes before step
  5: an input whose best gram score is under 0.1 has no candidate, so no
  search runs for Tier 2. `texts()` still searches it.
- **An empty set is no search.** A text held whole shares every gram with
  the input, so an input that shares none holds none: `found` gives None
  without encoding the input.
- **The guard reads the unfiltered table**, as `TEXTS` does: it judges the
  input, not the options.
- **A marker's or hint's candidate is no runner-up**: it is never left out
  by `under_found`.
- **`_rank_candidates` takes the search, not the input.** Its second
  argument is the `TextCandidates` of the input (the normalised input is
  `TextCandidates.norm_input`), so the ranking, `markerfloor` and the
  narrowing read one search and the signature keeps five arguments.

### 3. Measures

Side `T5-2` (the final tree), all sets, against 0.9.4 and layer 10. The
machine was busy through the run (load average 4 to 6, other sessions):
read the CPU seconds as ratios. Both trees run one after the other in one
session give the same-hour numbers.

| Gate (against 0.9.4) | T5-2 | Layer 10 |
| --- | --- | --- |
| Core CPU | 353.2 s to 22.4 s, 15.8 times | 23.1 s |
| Real file, median | 11.7 ms | 22.3 ms |
| Labels at 0.85 (agree, other, none) | 193, 14, 18 | 187, 20, 18 |
| Fixtures at 0.85, right and wrong | 418, 46 | 419, 45 |
| No class slower than 0.9.4 | worst 1.07 times | |
| `TEXTS` moved | 0 | |
| Memory, peak | 102 MB | |

Gates still failing, none from this task: one call (each of the eight
files 300 to 398 ms, task T6: the first search builds the corpus, about
100 ms, and the stored texts), the roadmap 68 file `f3b34c66` (219 ms, 213
on layer 10), the database size (28.1 MB, task T7), and fixtures at 0.85
by one case (the HPND fragment, section 5).

Against layer 10 (the harness, other hours): core 23.1 to 22.4 s, real
files 8.10 to 7.34 s, short 0.96 to 0.78 s; slower: many clean and
distorted 2 (32.8 to 39.5 s, 30.6 to 36.0 s: a second search for the
answer where several texts are found, section 7), `long:clean` 1.30 to
1.70 s (the search on an exact text), and one-process stress cases by
about 40 ms (the corpus built for the first search). Same hour, both trees
side by side: core 30.9 to 29.1 s, real 11.4 to 9.9 s (median 30 to 16 ms),
many 93.0 to 94.1 s, roadmap 3.27 to 3.00 s, cjk 0.58 to 0.56 s, options
1.10 to 1.23 s.

A search of a real file costs about 13 ms once the corpus is built (4.3 s
of 10.4 s profiled on the real files); the warm cost of an input that
finds nothing is unchanged.

### 4. The search reads the candidate set only

`TEXTS` from the candidate set (section 1) against `TEXTS` from a search of
the whole corpus, every input of each set, the same tree: core 847 inputs,
many 183, cjk 24, roadmap 120, prose 440, options 36; 0 differ. The
harness's own check (`TEXTS` of `many`, `cjk`, `roadmap` against layer 10)
reports 0 moved.

The shortcut of section 2 (the search with no answer stands for the
answer's when it found nothing or only the answer's group), against a
search for each answer: equal on all six sets (core: one text 1,425
searches, several 97, none 968; many: several 1,732, none 36, one 53).

### 5. Moved answers

Against layer 10 (the harness, and both trees side by side):

- **JSON over MIT: all cured.** The seven real files that answered `JSON`
  answer `MIT` (keys `752f3cb8`, `a0e4f502`, `2324a26e`, `fc82dcd3`,
  `778b25bb`, `c47bd870`, `65e8b901`; labels: MIT for five, `0BSD,
  BSD-3-Clause, CC0, MIT, Zlib` for `752f3cb8`, `MIT, PSF-2.0` for
  `a0e4f502`), and the numpy `LICENSE.md` of roadmap item 70. The text found
  is `MIT`; `JSON` scored above it as a runner-up and is left out.
- `real:0305317c` (label `BSD-3-Clause`): `BSD-3-Clause-HP` 0.9998 to
  `BSD-3-Clause` 0.9804, the text found.
- `short:HPND-sell-variant-MIT-disclaimer-rev:tail_300` (roadmap item 64):
  `HPND-sell-variant-MIT-disclaimer-rev` 1.0 (a four-way tie at 1.0) to
  `HPND-sell-variant` 0.9681. The fragment is the end of `HPND-sell-variant`'s
  core, which `TEXTS` already named on layer 10; the three that tied at 1.0
  are runner-ups at or above it and are left out. One fixture case at 0.85:
  right 419 to 418 against 0.9.4 (section 6).
- Rows under an answer: on 11 of 36 option inputs and 45 of 120 roadmap
  inputs the second and third rows change (runner-ups by gram score in
  place of the old selection); no other top answer moves there.
- `tools.golden`: no golden answer moves.

Runner-ups left out (`under_found`), counted over the sets: core 14 inputs
of 474 narrowed (the MIT and JSON files, `0305317c`, the HPND fragment),
roadmap 16 of 70 (the same files), prose 5 of 22 (READMEs scoring about
0.1, no answer), cjk 0 of 12, many 1 of 4 (`many:cores:2:1`, scores about
0.6, no answer).

### 6. Item 68 files

Real files with one text in `TEXTS`, layer 10 to this tree:

| Key | Label | Layer 10 | T5 |
| --- | --- | --- | --- |
| `752f3cb8` | 0BSD, BSD-3-Clause, CC0, MIT, Zlib | JSON 1.0 | MIT 0.9806 |
| `a0e4f502` | MIT, PSF-2.0 | JSON 0.8782 | MIT 0.8736 |
| `2324a26e` | MIT | JSON 0.9677 | MIT 0.9654 |
| `fc82dcd3` | MIT | JSON 0.9732 | MIT 0.9688 |
| `778b25bb` | MIT | JSON 1.0 | MIT 1.0 |
| `c47bd870` | MIT | JSON 0.9395 | MIT 0.9378 |
| `65e8b901` | MIT | JSON 0.8989 | MIT 0.8934 |
| `0305317c` | BSD-3-Clause | BSD-3-Clause-HP 0.9998 | BSD-3-Clause 0.9804 |
| `2e9aec16` | MIT | JSON 0.6969 | MIT 0.6888 |
| `aaf1f9bb` | MIT | JSON 0.6568 | MIT 0.6465 |
| `b87bd47e` | MIT | JSON 0.686 | MIT 0.673 |
| `e57d6584` | MIT, MPL-2.0 | JSON 0.7653 | MIT 0.7565 |
| `83a1fcfd` | (none) | LGPL-2.1-or-later 0.9187 | unchanged (guard) |
| `f3b34c66` | (none) | Apache-2.0 0.9187 | unchanged (guard) |

The four under 0.85 stay without an answer; their top row now names the
text found. `wcwidth` (`7bab96cb`) and `mypy_extensions` answer `MIT` on
both trees (0.9197 and 0.9641). No file moves against its label.

### 7. Findings left open

- **The second guard clause (decision Q6), measured, not built.** A clause
  that also fires where another text shares more grams than the group's
  best member and more than the grams it lacks: on core and roadmap it
  moves two answers back to layer 10's, `real:0305317c` (to
  `BSD-3-Clause-HP`, against its label) and the HPND fragment (to
  `HPND-sell-variant-MIT-disclaimer-rev`, the case's own ID); one gain and
  one loss, 0 `TEXTS` moved.
- **The shortcut always, measured, not built.** Reading the search with no
  answer for every answer (no second search on several texts): many 94.2 s
  to 70.2 s of CPU, 0 answers and 0 `TEXTS` moved of 183. It would undo the
  cost this task adds on several-text files (section 3).
- **UCL-1.0 distorted 10 and OLDAP-2.3 distorted 20**: no text found
  (`TEXTS` empty), so nothing here touches them (`TGPPL-1.0` 0.898; the
  `OLDAP-2.2` tie at 0.8832).
- **Golden short answers** (`Brian-Gladman-2-Clause` head 700:
  `Brian-Gladman-3-Clause-no-conversion` 0.8616; `pnmstitch` head 700:
  `BSD-1-Clause` 0.9067; `TCL` tail 1000: `SWL` 1.0, held whole; `Clips`
  tail 500: `NetCDF` 0.8742): no text found in any, so they do not move.
- **Alignment bound.** A runner-up whose fragment cannot be aligned
  (`similarity.alignment_affordable` false) is scored on the whole text and
  compared raw. Of the narrowed inputs, 27 core and 1 roadmap input had such
  a candidate; one left a runner-up out (`many:cores:2:1`, all under 0.7).
- **One call** (MIT and BSD-3-Clause files, 0.15 s): the first search of a
  process builds the corpus (about 100 ms); task T6 owns it.

### 8. Paths rejected

- Testing JSON over MIT on the packaged bundle or the long-text fixture
  database: neither holds the near MIT texts that tie with `JSON`. The test
  builds 28 IDs of the MIT family from the templates
  (`tests/template_texts.py`).
- A `Fraction` in the guard: about 2 ms an input; whole numbers instead.
- The `texts` search kept on `retrieval.Candidates`: it broke the equality
  of candidate sets; the detector keeps it.

### 9. Tests

- `tests/test_whole_text_rules.py`: the rules on made-up score tables
  (held at half, cores, the top 20, the guard at 11/10, the narrowing, the
  none bar, filters, `under_found`, `gram_count`, `variants`' order).
- `tests/test_whole_text_first.py`: through `detect()` and `texts()`: JSON
  over MIT, the guard, several texts, no text, the gram bound, the none bar,
  the shortcut, 22 texts joined (more than 20 searched), Han text. In
  `tests/platform_files.py`: it builds a database with `update` in a home
  of its own.
- Coverage of the new code: 100% of lines and branches
  (`textcandidates`, `firsttext`, `markerfloor`, `ranking`, `textnames`; the
  new lines of `gramselect`, `retrieval`, `textcorpus`, `variants`).
- Pins moved: `tests/test_detect_options_paths.py` (an input that holds
  MIT whole lists MIT and three runner-ups, `FOUND`, where it listed the
  top 3; with `only_spdx` off, Acme-MIT is the first runner-up) and
  `tests/test_option_matrix_variant.py` (one search, with no answer, where
  it found the answer's text alone).
- Mutation: 27 mutants of the new code, all killed (two survivors on the
  first run: a redundant clause of `guarded`, removed; the `!= 1` of
  `_narrowed`, killed by a test of two texts found).

### 10. Unnamed runner-ups are no results (after 0.10.0, items 13 and 68)

Built 2026-11-28 on release 0.10.0; plan and the prototype's measures in
`working-docs/design/texts-ranking-evidence-plan.md`.

- **The rule.** Where a member of the group is ranked, `ranking.under_found`
  leaves out every runner-up that nothing names, whatever it scores
  (section 1 left out only one scoring as high as the group's best). A
  verbatim Apache 2.0 file (rfc8785 0.1.4) answered `Apache-2.0` 1.0 with
  `Pixar` 0.9947 and `ImageMagick` 0.9871 beside it; it answers
  `Apache-2.0` alone. Decision Q1 of the 0.10.0 plan (a runner-up ranks
  under the text found) is replaced, for a runner-up nothing names, by the
  maintainer's decision of 2026-11-28.
- **A named runner-up keeps the rule of 0.10.0.** A runner-up whose ID a
  marker or `hint` names stays where it scores under the group's best.
  Names compare by `plusoperator.grant_stem`, case-folded, so a bare
  deprecated ID or either twin names both twins. The detector gives the
  IDs of the marker candidates and of `hint`.
- **Why (the review's findings on the first build, which left out every
  runner-up).** The steps after `under_found` read the lower rows:
  `variants` fills a bare deprecated marker row from its twins (with
  `License: GPL-1.0` above a `Dotseqn` text and `variant="as-written"`,
  the first result's similarity went from 0.5877 to 0.0), the tie-breaker
  reads a pair, and a declared licence that was one of the three runner-ups
  lost its row and its warning (`License: GPL-2.0-only` above an
  `Arphic-1999` text; `option: overridden by input` not given). Which
  declared licence stayed depended on the three slots.
- **Measured on the built tree** against the `under_found` of 0.10.0, one
  process, 1,704 speed gate inputs and 1,099 golden texts: the first
  result differs in no field on no input; no warning differs; every row
  kept is equal in every field; 587 gate inputs lose 1,684 rows and 311
  golden texts lose 881 (under `--top 3`: 1,077 and 561 rows). `tools.golden`
  moves nothing. A sweep of 125 List texts (every third, the first 125)
  under 80 shapes each (a `License:` or `Licensed under` line of eight
  IDs, hints, a grant sentence, the four `variant` values): 10,080 runs,
  6,660 lose rows, none differs in its first result, its warnings or a
  row kept.
- **Rejected: runner-ups not scored.** `narrowed` giving the group only is
  another rule: a look-alike that a marker also names then joins as the
  marker's candidate, which is never left out, at any score. 15 of 2,803
  inputs differ and one first row moves (the head of `X11`, `MIT` 0.9617
  to `X11` 1.0).
- **Rejected: every row `TEXTS` does not name.** Dropping marker rows too
  loses the labelled licence's row in three more real files.
- **Left open.** Tier 2 still scores the three runner-ups, about a tenth
  of the `core` CPU time; not scoring the unnamed ones needs the names
  before the scoring, and a measure. A look-alike the text itself names
  stays (`AGPL-3.0-only` 0.986 beside the `GPL-3.0` text, `BSD-4-Clause`
  beside `BSD-3-Clause-Attribution`).
- **Tests.** `tests/test_whole_text_alone.py` (the rfc8785 file and the
  four real texts of the Apache family, a twin, a licence the text names,
  a declared and a hinted runner-up, the CLI),
  `tests/test_whole_text_rules.py` (`under_found`). Mutants: 14, all
  killed.

---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Tier 1 from word grams (0.10.0 task T3)"
---

## Tier 1 from word grams (0.10.0 task T3)

Status: task T3 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`, sections 3.1 and 3.5), built
2026-11-27 on the T2 tree ([gram-postings.md](gram-postings.md)), not
merged. Measurements: Apple M-series, Python 3.10, SPDX License List
3.29.0, the harness of `.claude/speed-0-10` (sides `T3-1`, `T3-2`) against
the 0.9.4 baseline and its A/A twin.

### 1. What was built

- `retrieval.get_candidates` looks the word 3-grams of the input up once
  (`database.gram_scores`), the text read as before: comment prefixes off,
  then `normalize_text` on the whole input. It returns `Candidates(found,
  bounded)`.
- `gramselect` (pure, standard library and `listlookup.fold_case`):
  1. the filters (`exclude`, `only_spdx`, `only_common`) take their IDs out
     of the score table first (decision Q9), so the bar and the selection
     read only what may answer;
  2. a best score under `NONE_BAR` (0.1) gives no candidate (Q2);
  3. Tier 2 scores the first `TOP` (3) and every text within `MARGIN`
     (0.05) of the best, at most `MOST` (20); equal scores keep row order
     (`textgrams.ranked`), never a hash order. The margin edge is in, float
     rounding aside (`math.isclose`: 0.4 - 0.05 is 0.35000000000000003).
- The markers and the hinted licences join after the gram candidates, also
  when the bar left none (`retrieval.add_free_text`); `hinted_candidates`
  shares `gramselect.passes` with the score table.
- `database.candidate_rows` reads the rows of the selected IDs in one query
  (rowids from `dbcache.TableCache.index_row`), in the order given;
  `database.list_flags` reads the four flags the filters need once per cache
  generation (`TableCache.list_flags`).
- `TEXTS` and `texts()` read no filter, as before.

### 2. What was removed

- `ftsquery.py` and `database.search_candidates`: the FTS5 `MATCH` query of
  20 words, head and tail. The FTS5 table stays (task T7 drops it); no
  statement of a `detect()` call reads it
  (`tests/test_gram_candidates.py` traces them).
- The notice-free head query of `retrieval` (0.9.2, PR #239) and its helpers
  in `normalize` (`strip_copyright_notices`, `notice_free_head`): the grams
  of a whole input reach past a long copyright notice without a second
  query (`tests/test_notice_recall.py` keeps the cases of
  `test_notice_query.py`).
- The windowed search of mixed content (`detector._match_mixed_content`,
  `_match_short_text`, `candidates.license_sections`), the name search on
  its sections and the gate of five candidates that started it.
- `benchmarks/bench_fts5_recall.py`.
- `max-public-methods` in `pyproject.toml` from 15 to 14:
  `LicenseDatabase` lost `search_candidates`. No other ceiling moved.

### 3. The bound on the grams looked up

`gramselect.GRAM_LIMIT` is 50,000 distinct grams, the first in input order;
past it the candidates come from the grams read and `TEXTS` is None (never
a partial list). It equals `textlocate.MAX_INPUT_TOKENS`, so `texts()`
agrees: an input past the bound has more tokens than the whole-text search
reads.

Distinct grams of real inputs, most per set: real files 8,402; prose
11,435; many 28,454; CJK 2,583; options 4,899; roadmap 5,943; the List's
own texts 5,587 (LGPL-3.0). None reaches the bound.

CPU, best of three, the input of 100,000 distinct words: 0.9.4 0.358 s; T3
with a bound of 10,000, 20,000, 50,000, 100,000 or none: 0.337, 0.343,
0.353, 0.377, 0.375 s. At 50,000 it is 0.99 times 0.9.4, under the 1.2
the plan allows. `gram_scores` alone on 100,000 grams: 86 ms unbounded,
64 ms at 50,000; the floor is the hashing. Licence words shuffled, 1 MB:
4.53 s on 0.9.4, about 0.4 s on T3.

### 4. Measured

Every set (side `T3-2`, the machine quiet for all but `threads`): core CPU
353.2 s to 27.1 s, 13.0 times (the gate of 0.10.0 needs 12; A/A twin 0.999,
widest kind 1.10). By kind: clean 18.7, d01 13.6, d02 14.5, d05 18.3, d10
9.3, d20 6.8, real 13.2, short 19.3, mixed 10.5, notice 11.0, readme 13.5,
CJK 9.9, options 10.3 times; files of many texts 2.2 to 7.1; stress 1.0
(kana prose 300 KB) to 22. Real median 35.3 ms (0.9.4 326 ms). No kind
slower (worst 1.02). Memory peak 97 MB (0.9.4 109 MB). Threads: no
difference, no race. Damage: as the reference. Item 68: no new answer on
the HPND family. The first core run (`T3-1`, a busy machine) gave 9.2.

Gates of 0.10.0 that T3 does not meet, all owned by later tasks: real
median 15 ms, one call 150 ms (292 ms here), labels (agree 187, needs 190;
other 20, at most 16: JSON over MIT, task T5), the roadmap inputs of item 11
(3,730 ms) and the item 68 file (207 ms), database size 28.1 MB (task T7).

`texts()` moved on no input of any set. The harness reports 17 `TEXTS`
moves on `many` (and 28 on core, 225 on prose): each is a record that
gained or lost every row, never a list that changed; the CLI then prints
the `TEXTS` of `texts()`, which is the same. A file of several whole texts
now has each of them as a candidate at 1.0; when Tier 2 ranks one that is
not first in the file on top, `firsttext` (0.9.4) leaves no row, as it
should: `REASON` `several texts`. No answer at 0.85 moved in `prose`,
`many`, `cjk`, `options` or `stress`.

The harness's prose gate counts a move of the top row at any score: 309
of 473 moved, 158 at 0.5 or more, none at 0.7. Of the 158: 132 README files
that lose a row (none now); 23 notice headers and sentences whose top row,
under 0.7 and wrong in 0.9.4 too, is another wrong licence (mostly
Adobe-2006 at 0.54 to 0.59); one weak right row lost (`the Apache Licence,
Version 2.0` in a README, Apache-2.0 at 0.507); one new row (MIT at 0.537 on
MIT text followed by prose).

Roadmap inputs at 0.85, 21 moves, none against a label: the same real files
as the core set, `HPND-MIT-disclaimer` whole and `head_300` now answer
themselves (were HPND-Pbmplus and a look-alike), two numpy files answer
the text their `TEXTS` names (MIT, BSD-3-Clause-Open-MPI at 0.9647).

Core set, the same in both runs. Labels at 0.85: agree 182 to 187, other
19 to 20, none 24 to 18. Fixtures at 0.85: right 419 to 421, wrong 46 to
43; at 0.7: right 457 to 463, wrong 65 to 58; at 0.5: right 464 to 472,
wrong 86 to 68.

Moved top answers of the core set (24):

- Right now (8): 0BSD d20, Sun-PPP-2000 d20, curl d05, and five real
  files (two BSD-2-Clause, two MIT, one JSON to MIT).
- Wrong to none (3): GFDL-1.3-only d05, OpenSSL d05 and d10 (was
  SSLeay-standalone).
- JSON over MIT (expected, task T5 cures it): four real files labelled MIT,
  one unlabelled.
- Other to other (6): three unlabelled real files; three short `tail_300`
  inputs from BSD-1-Clause to AAL, each a tie at 1.0 ranked by ID.
- Wrong now (1): short OpenSSL `tail_700` to BSD-Systemics, a three-way tie
  at 1.0.
- New, no label (1): a real file to BSD-1-Clause at 1.0, as its `TEXTS`.

`tests/test_accuracy.py` with `--run-benchmark` (538 licences): verbatim
and 2% the same (top 1 94.95% and 94.77%); 5% top 1 78.92% to 84.50%,
top 3 89.01% to 96.40%, top 5 90.81% to 98.74%; names 100%. The run took
849 s on 0.9.4 and 44 s on T3.

### 5. Golden

`long`, `id` and `cli` as the golden. 131 lines moved (short 85, mixed 39,
name 1, value 6, several 1), each listed in
`tests/harness_changes_grams.py`: a row under the answer gone (65), no
row left (52), now right (7), another tie or near text (3), right to none
(1), and three new answers where the golden had none (listed below). The
module of the notice-free query's moves (`harness_changes_notice_query.py`)
went with the query: 9 of its 23 slices keep the same answer under the word
grams and moved into `harness_changes_grams.py` (reason `_KEPT`), 13 moved
again (listed there), and one (`Game-Programming-Gems` `head_900`) is back to
the golden's answer. The module lists 140 cases.

- `TCL` `tail_1000` answers SWL at 1.0: the fragment is held whole in SWL.
- `Clips` `tail_500` answers NetCDF at 0.8742: not held whole; in the
  evidence's list for T4 and T5.
- `pnmstitch` `head_700` answers BSD-1-Clause at 0.9089: not held whole,
  and not in the evidence's list. A finding against the golden gate,
  reported, not fixed here.

`several/mpl-header-notice`: Catharon 0.4961 to
MPL-2.0-no-copyleft-exception 0.7409 (item 69).

### 6. Known limits, measured

- Every third word replaced leaves no 3-gram in common: Apache-2.0 so
  distorted gets no row (0.9.4 listed it at 0.78, no answer either way).
  Every fourth word keeps it first.
- A text a filter drops no longer lets a worse one answer (section 8): the
  JSON text with `only_common` answered MIT at 0.99, as in 0.9.4, and now
  answers nothing.
- `REASON` reads `no match` where it read `below threshold`: the far rows
  that 0.9.4 listed are not candidates.

### 7. Tests

`tests/test_gramselect.py` (made-up tables, literal numbers),
`tests/test_gram_candidates.py` (the long-text fixture database: one
lookup and one connection, no `MATCH`, markers and hints after the grams,
filters before the selection, `TEXTS` unfiltered under eight option sets,
the bound, Han and kana rewrapped, adversarial prose, a hash-seed child
run; in `tests/platform_files.py`), `tests/test_notice_recall.py`.
Mutation: 26 mutants of the rules (bar, top, margin, cap, row order,
filters, bound, merge, comment strip), all killed; the `isclose` mutant
survived the first round and got two rows.

### 8. A filter and the texts under the one it removed

What: `gramselect.beyond_bar`, called by `retrieval.get_candidates` on the
filtered table for both paths (the selection, and the narrowing of a text
found whole). A row that passed the filters is no candidate when one row
the filters took out beats it on both counts: more of the input's grams
`shared` and a higher `score` (`math.isclose` keeps an equal score; an equal
`shared` stays). No row taken out: no change. `TEXTS`, `texts()` and the
guard of the narrowing read the unfiltered table, as before.

Why: a text of the List that holds the input fits it better than any other.
Take it out, and the best of the rest is only a near text, and on a short
input every long text has one. On 12,136 slices of List texts (truth: the
licences whose text holds the slice whole), with `only_common=True` the 9,579
slices held by one licence gave 2,424 right and 1,075 wrong answers at 0.85;
with the holders of each slice passed as `exclude`, 4,361 slices still got an
answer (3,360 held by one licence, 1,001 held by several), every one wrong.

Numbers (layer 12 to this rule, answer bar 0.85, the same 12,136 slices;
CPU of the `only_common` run 92.9 s to 31.8 s, of the holders-excluded run
80.6 s to 24.5 s, as fewer texts reach Tier 2):

| Slices | Layer 12 | Rule |
| - | - | - |
| no option: rows differing | | 0 of 12,136 |
| `only_common`, one holder: right / wrong / none | 2,424 / 1,075 / 6,080 | 2,427 / 41 / 7,111 |
| `only_common`, several: holder / wrong / none | 1,237 / 109 / 1,211 | 1,237 / 2 / 1,318 |
| holders excluded, one: answers (all wrong) | 3,360 | 319 |
| holders excluded, several: answers (all wrong) | 1,001 | 64 |

No right answer falls: slices move from wrong to none (1,031 and 107 under
`only_common`, 3,041 and 937 with the holders excluded) or, 3 of them, from
wrong to right. Of the 383 wrong answers left with the holders excluded, 296
come from the name tier (section below), not from the word search. On a
slice every text is longer than the input, so `score` is `shared` over the
input's grams and the two counts rank alike: the three forms below give the
same rows on all four slice runs (with the best other row excluded too:
8,289 / 25 / 3 each, as without a bar).

Whole texts tell them apart. The core set's 408 List texts (clean and
distorted 1 to 20 %), its 160 head and tail cuts and the 225 real files with
one label, each with no option, with `exclude` of each of the three rows
under its answer, of all three, and with `only_common` (truth: the fixture's
licence or the label; right / wrong / none at 0.85):

| Inputs, option | No bar | Best removed score | Best removed `shared` | Both counts |
| - | - | - | - | - |
| fixtures, `exclude` one row under | 771 / 27 / 196 | 762 / 25 / 207 | 769 / 25 / 200 | 769 / 25 / 200 |
| fixtures, `exclude` all three | 285 / 10 / 81 | 278 / 8 / 90 | 284 / 8 / 84 | 284 / 8 / 84 |
| fixtures, `only_common`, rare licence | 13 / 40 / 151 | 13 / 6 / 185 | 13 / 6 / 185 | 13 / 6 / 185 |
| real, `exclude` one row under | 557 / 37 / 8 | 546 / 40 / 16 | 503 / 42 / 57 | 556 / 37 / 9 |
| real, `exclude` all three | 191 / 14 / 4 | 183 / 14 / 12 | 143 / 13 / 53 | 190 / 14 / 5 |
| real, `only_common`, common licence | 193 / 14 / 16 | 191 / 14 / 18 | 137 / 23 / 63 | 192 / 14 / 17 |
| right answers lost (calls, inputs) | | 39, 20 | 162, 106 | 6, 3 |

Rejected: the bar at the best score removed (the first form built). The
score divides by the smaller side, so a short text held in the input scores
near 1 and more than the input's own text once that is reworded: a real
BSD-3-Clause file with `exclude=["BSD-2-Clause"]` answered nothing, with
`exclude=["BSD-1-Clause"]` answered `BSD-2-Clause`; the MIT text with
`exclude=["MIT-0"]` and its condition reworded answered nothing. It cut no
wrong answer that both counts keep. Rejected: the bar at the best `shared`
removed. A long text that holds one more gram of a real file than its own
licence (`BSD-3-Clause-OpenWebUI`, `FSL-1.1-MIT`, as copyright lines fill a
template) cut the right answer from 106 inputs. Kept: both counts. Its 3
inputs lost are a real BSD-2-Clause file that shares 171 grams with
`BSD-2-Clause-Views` and 166 with its own text, and the MIT text distorted
10 %, which shares 72 grams with `UPL-1.0` and 71 with MIT: the grams alone
cannot tell them apart. Rejected too: a margin under the bar (a text stays
if it scores within `m` of the removed text): wrong answers 34, 42, 107, 230
and 675 for margins of 0, 0.02, 0.05, 0.10 and 0.25 on the slices, with no
plateau. No number is tuned.

Decided by the maintainer: `exclude=["MIT"]` on the MIT text answers nothing
(layer 12 and 0.9.4 answered `JSON` at 0.99). `only_spdx` goes through the
same rule and takes nothing out of a database of the List alone.

Not covered, measured by hand on the real List, for a decision:

- The name tier carried the defect. A sentence of 10 to 29 words that names
  "Apache License, Version 2.0", with `exclude=["Apache-2.0"]`, answered
  `Apache-1.0` at 0.9412 (method `name`), then `Apache-1.1`: the other name
  hits that the exclusion left are near names, not names the input holds.
  `idoptions.free_text_hits` now cuts a name hit that scores under the best
  hit `exclude` took out (equal stays). Each List name in two sentences
  (1,416) and the prose set's 13 notice sentences with the named licence
  excluded: 816 answered another licence by name, none now; with the best
  other row excluded instead, no answer moved. On the slices with the
  holders excluded the wrong answers fall from 319 and 64 to 57 and 61; with
  the best other row excluded, from 25 to 2 (10 more right). Lost: the 7
  sentences naming an `-or-later` licence with it excluded, which answered
  its `-only` twin by name. `only_common` does not act on name hits at all.
- A title and prose with the title's licence excluded give no answer at
  0.85 (MIT, BSD-3-Clause, Apache-2.0, MPL-2.0, GPL-2.0-only); the rows left
  score under 0.5. But a licence text that names another licence brings it
  back as a marker, which the bar does not cut: the List text of
  GPL-3.0-only with both GPL-3.0 IDs excluded answers `AGPL-3.0-only` at
  0.9861, of LGPL-2.1-only `LGPL-2.0-only` at 0.9846, of MPL-2.0
  `AGPL-3.0-or-later` at 0.874, of EPL-2.0 `GPL-2.0-or-later` at 0.874.
  Cutting markers whose row the bar cut is no plain gain: on the whole texts
  above it would take 7 wrong answers and 5 right ones.
- A hint is the caller's own candidate, ranked on its text:
  `exclude=["MIT"], hint=["JSON"]` on the MIT text answers `JSON` at 0.9879.

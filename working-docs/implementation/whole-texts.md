---
Created: 2026-11-24
Last-Modified: 2026-11-26
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "TEXTS: the licence texts an input holds whole"
---

## TEXTS: the licence texts an input holds whole

Status: implemented on branch `detect-text-signals` (after 0.9.2), not yet
released. Measurements are from 2026-11-24: Apple M4, Python 3.10, RapidFuzz
3.14.5, SPDX License List 3.29.0 (708 texts, 442 cores).

### 1. What TEXTS is and why

`detect()` gives one answer for an input. Pitloom's handoff showed three
cases where one answer misleads a caller:

- B2: one file holds several licence texts (a bundle). Tier 1 searches the
  head (words 0 to 99) and the tail (last 20 words) only, and Tier 2
  compares a long input whole, so nothing locates a text inside a longer
  input. numpy's `LICENSE.txt` scored BSD-3-Clause 0.93 at similarity 0.06:
  the marker floor in `calculate_final_score`, not a match.
- B3: a notice (an Apache-2.0 appendix paragraph) scored as the full text:
  similarity 0.92, coverage 0.057, lifted to 1 by the marker floor.
- B5: the meaning of SCORE, SIMILARITY, COVERAGE and EXACT was not clear to
  callers.

`TEXTS` is a new last field of the `detect` record (after `REASON`), JSON
key `texts`, API `Detection.texts: list[str] | None`. It lists the IDs of the
List texts the input holds whole: sorted, space-separated as `SAME_TEXT` is,
or `null`. It is a fact about the input; it does not change the answer, the
ranking or `resolve()`.

Real files (the user's six, from the Pitloom handoff):

| File | Answer | TEXTS |
| --- | --- | --- |
| bandit | Apache-2.0 | `[Apache-2.0]` |
| cachecontrol | Apache-2.0 | null (a notice) |
| mypy 2.4.1 | Python-2.0.1 | `[BSD-2-Clause, MIT, Python-2.0.1]` |
| numpy 2.2.6 | LGPL-2.1-or-later | `[BSD-3-Clause, BSD-3-Clause-Open-MPI, GPL-3.0-only]` |
| pymdown-extensions 12.3 | MIT | `[MIT]` |
| python-dateutil 3.0.0 | Apache-2.0 | `[BSD-3-Clause]` |

B3 needs no new METHOD: a notice is "TEXTS without the answer and COVERAGE
below 0.8". B5 is answered in `docs/output.md`, "Which field to read": the
answer is the exit code or `--threshold` on SCORE (SCORE only ranks); fit is
SIMILARITY; whole or fragment is COVERAGE; the whole texts held are TEXTS.
A caller declares EXPRESSION when METHOD is not `text`, or when TEXTS is
exactly `[EXPRESSION]`. Otherwise: TEXTS empty with COVERAGE under 0.8 is a
notice or a pointer; empty with COVERAGE about 1 or more is a whole text
TEXTS could not confirm (a look-alike was too close, or the wording differs
from the List's); one ID other than EXPRESSION means the answer is in doubt;
several IDs mean several texts.

### 2. Algorithm and modules

Run only when the top result (after `settle_free_text`) is a text match and
the input has at least 40 tokens, or the answer is exact (then TEXTS is
`[answer]` whatever the length); otherwise null. It is also skipped where
TEXTS is never printed (`textnames.skipped`: the `is-*` commands, `is_*()`,
terse `detect` without `-v` or `--json`), so TEXTS is filled for `-v`,
`--json` and the API. Every result of one call
carries its own copy of the same list.

- `textcorpus.py`: codes each distinct word of the List as one code point,
  so a text of 7,244 words is a string of 7,244 characters. The corpus
  (texts, cores, same-text groups) is read lazily once per database
  generation in `dbcache.TableCache` (same invalidation as `text_parts`),
  immutable. Database build 6 stores the codes in `text_codes` (the
  vocabulary as one JSON row, the codes of each text and core as one row
  each; `TextCorpus.stored_rows`, `TextCorpus.restore`), so the first use
  reads in 20 ms instead of coding the texts (150 to 160 ms); a database of
  build 5, or a damaged table, is coded in memory and never written. A
  `check` row holds a SHA-256 of `CODING_VERSION`, the token pattern, the
  vocabulary and, per group, its name, text, core and codes (hashed from
  the rows read, so it costs about 5 ms): `restore` gives the corpus
  `build` gives or nothing. It catches codes that outlived their rows (a
  0.9.2 `update` of a build-6 file rewrites `license_index` and the cores,
  stamps build 5 and leaves `text_codes`), swapped, cut or edited bodies,
  and a coding changed with no build bump (raise `CODING_VERSION`). A row
  read as bytes (a BLOB) is no text: coded in memory. A row SQLite cannot
  decode as UTF-8 is `database: unreadable`, as any other read. Tokens: ASCII
  `split()`; non-ASCII input has one Han or kana character per token (no
  spaces in those scripts; a word-count cut would miss them, AGENTS.md).
- `textlocate.py`: indexes the input's word 5-grams. Per text short enough
  to fit the input (`can_reach`, below): a sample check of 48 evenly
  spaced 5-grams (under 30 percent found: next text, which stops most of
  the 708); votes from up to
  200 anchors give offset buckets; two neighbouring buckets with 30 percent
  of the anchors make a window, one per copy. Best first, a word-level LCS
  gate (0.80), then the matching blocks trimmed at both ends, then one
  character `fuzz.ratio` of the text against the trimmed span. A text counts
  when the ratio is at least `MIN_SIMILARITY` (0.95) and the span holds the
  same count of each `similarity.CRITICAL_TOKENS` word as the text
  (`textcorpus.COUNTED_WITH`: "neither" counts as "not", so a copy that
  swaps one for the other is not the same text), and the span misses no
  run of `MAX_GAP_CHARS` (150) characters of the text (section 4, "Gap
  guard"). A core is tried too, under the same rule.
- `wholetexts.py`: selection. Key `2 x matched - len(text)` (found less
  missing), then the answer's group, then ID. A hit overlapping a kept one
  by more than a tenth of the shorter span is dropped. Look-alike rule: a
  kept span with a fit of `SURE_SIMILARITY` (0.98) or more is named. Between
  `MIN_SIMILARITY` (0.95) and 0.98 it is named only when no text of a
  different same-text group fits an overlapping span at `NEAR_SIMILARITY`
  (0.93) or more, with the same critical words and a key of at least
  `LOOKALIKE_REACH` (0.90) of its own; else the part names nothing, and the
  span stays claimed so no third text takes it. A text refused only for its
  critical words still doubts any hit, a sure one too, when it fits at 0.95
  or more with a higher key: else a copy that lost one "except" named a
  look-alike (Apache-2.0 as ImageMagick; 92 of 1,971 such copies, now 0).
  One entry per copy;
  names are deduped after the overlap step, never before. One
  representative per same-text group is scanned. `found_rows` returns row
  IDs or None.
- `textnames.py`: the gate and the naming (below).
- Glue in `detector.py` (kept under 800 lines); `result.py` carries the
  field.

### 3. Decisions and reasons

User answers (2026-11-24): name `TEXTS`; search only when the top answer is
a text match and the input has 40 tokens or more; null past a limit, said so
in the docs, never partial; ranking unchanged here.

- Naming: the answer's same-text group shows as EXPRESSION's ID, bare
  `GPL-3.0` under `as-written` included. Any other group is named as
  `detect()` would name an unstated text of it under the variant in force:
  `-only` (`auto`, `only`, `as-written`), `-or-later` (`or-later`); a group
  with neither form shows its shortest ID. So numpy lists `GPL-3.0-only`.
- `exclude` and `hint` change neither the search nor which texts are found;
  only the answer's own name follows the answer, and they can make the top
  result not a text match, so TEXTS is empty. `only_spdx` and `only_common`
  do not touch TEXTS.
- The no-answer record has every field empty but `REASON`, TEXTS too. The
  `is-*` commands, `is_*()` and terse `detect` skip the step (nothing prints
  it).
- The nearest candidate (a text that scores below the bar) is refused: precision
  over recall. To see it, `--threshold 0 --top 1 -v`.
- No new METHOD for notices (B3), see section 1.
- Exception texts are out of scope: they are not in the database (numpy's
  GCC runtime exception is not listed).
- Skip gate: only when the answer is exact (then TEXTS is `[answer]`, even
  under 40 words: a List text under 40 words is listed only as the whole
  input). No 1.1x gate (see section 6).
- Look-alike doubt (section 5, "Look-alike rule"): precision over recall; a
  name that a near twin fits about as well is withheld.
- Text floor `MIN_WORDS` 40 kept (section 4).

### 4. Limits

Counts, never clocks, so the same input gives the same result on every
machine. Past any of them TEXTS is null ("not searched"), never partial: a
partial list names a look-alike for the parts the true text did not get to
claim (the 8-positions cap did exactly this in the study).

| Constant | Value |
| --- | ---: |
| `MAX_INPUT_CHARS` | 400,000 |
| `MAX_INPUT_TOKENS` | 50,000 |
| `MAX_VOTES` | 3,000,000 |
| `MAX_WINDOWS` | 15,000 |
| `MAX_WORD_CELLS` | 5 x 10^9 |
| `MAX_CHAR_CELLS` | 50 x 10^9 |

Gates: vote share 0.30 (a word ratio of 0.8 spread evenly leaves 0.8^5 =
0.33 of the 5-grams; a sweep of 366 inputs lost nothing at 0.3, two hits at
0.4); word gate 0.80 (lowest word ratio of a hit 0.835; 0.85 lost three).
Worst input built under the limits: about 0.4 s and 45 MB (RapidFuzz's bit
matrix, bounded by the largest List text, not the input).

Character cells (2026-11-25): a fit charges `length x size`, but
RapidFuzz's Indel with a cut-off is bit-parallel and banded: 3 to 6 ns per
1,000 cells on texts of 2,000 characters or more (up to 12 ns on 500, where
the window limit bounds the count), whatever the similarity. The old limit,
2 x 10^10 cells, was about 0.1 s of work and left long bundles unsearched:
12 common licences charge 1.2 x 10^10, the 11 GPL-family texts 1.4 x 10^10,
long licences with many look-alikes up to 2.8 x 10^10 (CPAL, NPL, CC 3.0)
and 30 copies of CC-BY-3.0 4.3 x 10^10 (0.12 s of fits, 0.32 s in all). At
5 x 10^10 the character stage costs at most about 0.3 s. Every built input
that spent more time (0.5 s at most) stopped at the word cells first; the
process peaked at 122 MB, corpus included (Indel's distance keeps one bit
row, not a matrix). A 20-text GPL-family bundle does not fit the token
limit: the 11 family texts and 2 repeats make 49,000 tokens (1.3 x 10^10
cells, listed under either limit).

Length bound: a text of `length` characters fits a span of `size` at most
at `2 x size / (length + size)`, so a text is tried while it can reach
NEAR_SIMILARITY against the whole input (a text up to 1.150 times the
input's length; a look-alike) and scored as a hit while it can reach
MIN_SIMILARITY (up to 1.105 times): `textlocate.can_reach`, in whole
percent as `Fit.reaches`. A fixed bound of 1.05 left a copy that lost a
clause to a shorter neighbour (ISC named 0BSD, MIT-open-group named
HPND-sell-variant, MIT-advertising named MIT-feh), and padding the input
changed the answer.

Gap guard (2026-11-25): a hit's span may not miss a run of
`MAX_GAP_CHARS` (150) characters of the text or more, about 25 words: the
input lacks a clause, so it holds another licence. Spread edits (OCR, a
changed word, reflow) leave short runs. The runs come from `align`'s kept
blocks (`Alignment.missing`, text word positions), measured in characters
(`textlocate.longest_gap`): a word count would make the guard 5 to 6 times
stricter on Han and kana, a token per character. A text refused by the
guard still casts doubt as a look-alike, as one refused by a critical
word: a damaged copy of it must not name a shorter neighbour. A long run at
an end of the text is looked for once more on the span widened by that run
(`wholetexts._Search._hit_span`): the alignment can tie the text's end to
a later copy of the same words (Python-2.0.1's closing disclaimer, repeated
by the 0BSD text after it in Python's `LICENSE`) and trimming then drops
that block. The second look is for a hit only (a look-alike keeps its first
span) and only where the blocks trimmed off that end matched half the run
or more (a few stray words are no copy), charged to the word cells; fits
are cached by span. Without those two conditions the step cost 5 to 12
percent more on the longest real files.

### 5. Measurements

#### Speed

The naive scan (`partial_ratio_alignment` of every text against the whole
input, on characters) costs 53 to 230 s per file; numpy was stopped after 25
minutes. Working on word codes with anchors gives the same hits in 4 to 40
ms. Corpus: 0.16 s once per process when coded (72 ms to code in the
prototype, the rest reading rows); 20 ms read from `text_codes` (build 6;
about 5 ms of it the check).

| File | Words | Naive | TEXTS step |
| --- | ---: | ---: | ---: |
| bandit | 1,413 | 53 s | 3.9 ms |
| cachecontrol | 91 | n/a | 2.2 ms |
| mypy | 1,980 | 230 s | 13 ms |
| numpy | 7,528 | not finished | 38 ms |
| pymdown | 627 | 6 s | 4.8 ms |
| dateutil | 421 | 3 s | 6.3 ms |

On the 493 real files (corpus built): median 2.8 ms, p95 9 ms, max 45 ms
(pandas, 7,779 words). Synthetic: singles median 3.6 ms; pairs median 7 ms,
max 94 ms; triples median 10 ms, max 82 ms. Threshold and floor change cost
by under 5 percent.

#### Real corpus (WP0)

493 unique `*.dist-info` licence, copying and notice files under
`~/.pyenv/versions`, under 60 KB (read only); 489 answered by method
`text`, 444 with score 0.85 or more. Setting = similarity / text floor.

| Setting | TEXTS equals [answer] | empty | answer + others | others only |
| --- | ---: | ---: | ---: | ---: |
| 0.95 / 40 | 372 | 48 | 20 | 52 |
| 0.95 / 0 | 372 | 48 | 20 | 52 |
| 0.90 / 40 | 370 | 44 | 22 | 56 |
| 0.90 / 0 | 370 | 44 | 22 | 56 |

(One more file has no answer and is empty in every row.)

- Floor 0 against 40: one file differs (wcwidth gains
  HPND-Markus-Kuhn, a right name). Kept 40: a text under 40 words is a
  sentence that can sit inside any longer licence; the evidence is one file.
- 0.90 against 0.95: 14 files, all additions. 8 right names (NCSA, MIT-CMU,
  IJG; seven sit at span 0.94 to 0.947) and 6 wrong or doubtful (MIT read as
  BSD-3-Clause-No-Military-License, BSD-3 variants such as
  BSD-3-Clause-Modification and BSD-Source-beginning-file). Not taken.
- 0.97: four files differ; drops two wrong names (BSD-3-Clause-HP,
  BSD-2-Clause-pos-unchanged), loses two right ones (MIT ratio 0.967, X11).
  0.98: 21 files, loses 0BSD and BSD-3-Clause in 11 files and makes a new
  wrong name (PSF-2.0). Kept 0.95; 0.97 is the owner's call on four files.

#### Look-alike rule (2026-11-25)

Before: a text at a fit of 0.95 or more was named. After: named for sure at
0.98 or more; between 0.95 and 0.98 named only when no text of another
licence fits the same part at 0.93 or more with the same critical words and
a key of at least 0.90 of its own; "neither" counted as "not". Measured on
the 493 real files (method: run `detect()` on each file with the code before
and after the rule, and compare the `TEXTS` of the two runs; the run files
were scratch data and are not kept):

- Removed 4 wrong names: PySocks, sphinx, sympy, torch NOTICE
  (BSD-3-Clause-HP, BSD-2-Clause-pos-unchanged); prevented jsonpointer's.
- Lost 7 right names: BSD-3-Clause copies that write REGENTS or COPYRIGHT
  OWNER (numpy 2.4.6 LICENSE, lxml 5.4.0, isodate 0.7.2, dill 0.3.1.1,
  json_flattener 0.1.9, sympy) and X11 in pillow 11.2.1. Each is a copy
  whose wording differs from the List text by a few words and sits as close
  to a near twin.

#### Gap guard (2026-11-25)

Probes on the List's own texts (the run files were scratch data and are
not kept): leave-one-out (each text as input, its own group removed from
the corpus: a licence not on the List; any name is a look-alike), the same
inputs followed by the MIT text (a bundle), `fuzz5` (2 to 20 words dropped
in one place, maybe 1 to 4 words changed; 4 per text), a drop probe (one
run of 8 to 40 words dropped; 7 per text), and the 493 real files plus the
user's six, before and after:

| Probe | Before | 120 | 150 | 180 | 1.05 bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| Leave-one-out, names | 115 | 99 | 99 | 101 | 112 |
| Same, in a bundle, names removed | | 16 | 16 | 14 | 0 |
| `fuzz5` right names lost (of 1,880) | | 101 | 6 | 1 | 263 |
| Drop probe right names lost (of 2,414) | | 844 | 534 | 291 | 423 |
| Real files changed | | 0 | 0 | 0 | |

"1.05 bound" is the alternative: a hit at most 1.05 times the input's
length, look-alikes up to 1.150 times. It removes only the three new names
(CC-SA-1.0 named CC-BY-SA-1.0, MS-PL named MS-LPL, CDDL-1.0 named
CDDL-1.1) and none in a bundle, where the input is longer than the text,
and refuses short texts that lost a few words. At 150 the guard removes
16 names, the three and 13 older ones (CC 2.0 named 2.5, CC 3.0 DE and
IGO variants, EPL-1.0 named CPL-1.0, SPL-1.0 named CUA-OPL-1.0,
LiLiQ-Rplus-1.1 named LiLiQ-R-1.1, TCL named SWL: runs of 159 to 904
characters), adds no wrong name in any probe (wrong names: `fuzz5` 5, drop
probe 26, critical-word drops 0 of 1,971, before and after; in a bundle,
LGPL-3.0-only with its own row removed gains GPL-3.0-only, which its text
holds whole), and changes no real
file: the longest run a right name misses there is 104 characters
(Python-2.0.1 in django's `LICENSE.python`), after the second look at its
end (without it, 248 in four files). 120 loses 17 times as many `fuzz5`
names for no more removed; 180 keeps TCL and LiLiQ.

Known limit, a chosen trade (precision over recall): 20 to 60 foreign
words inserted near an end of a licence text (within about one run of it)
make the alignment trim that end block, the second look widens into the
insertion, and the hit is refused as a missing clause, though every text
word is in the input in order. A long inserted paragraph near an end may
be an added clause, so the name is not given. Measured on all List texts:
40 words inserted 30 words from the end named 279 texts at the base, 97
now; 60 words at 45 from the end, 211 to 75; 60 words after the first 45
words, 238 to 84. The 493 real files are unchanged and no wrong name is
added. An insertion in the middle is still named.

Search time on the 493 real files (467 searches, two runs each, same
machine): median 3.13 to 3.16 ms before, 3.24 to 3.28 ms after; p95 10.2 to
10.7 before, 10.7 to 11.0 after; max 51 ms before, 54 ms after (pandas, 7,779
words). The adversarial inputs (48,000 to 49,000 tokens: the BSD family, 40
families, mutated or exact) cost the same, 0.14 to 0.32 s, within 0.02 s.

A text the guard refuses keeps casting doubt: when it does not, the
leave-one-out names 8 more look-alikes (Apache-2.0 as Pixar, CC-BY-SA-4.0
as CC-BY-4.0) and the drop probe 40 more.

#### Synthetic

List texts behind a copyright line, joined by a "this product bundles"
line, normalised. 708 singles, 300 pairs, 200 triples, plus 360 (150 common
pairs, 150 random pairs, 60 triples), 100 singles, 150 pairs and 50 triples
of cores. All exact at 0.95 / 40 with no noise, except one core triple
(OLDAP-1.2 core read as OLDAP-1.1, the version twins). Recall of the
prototype at 2 to 8 percent random word noise: 0 wrong up to 5 percent; at 8
percent 26 parts missed and 2 near twins read as each other (a threshold
effect). Repeats are exact: BSD-3-Clause x 10 then BSD-2-Clause; MIT x 100
then JSON.

### 6. Paths rejected

- Fingerprint hits as candidates (`find_fingerprint_hits`): 2 of 911 true
  answers lost (SHL-0.51: its 20 n-grams sit on one differing spot, and a
  near twin answers instead), and false names (AFL-2.1 core -> AFL-2.0).
  The fingerprint step stays where it is.
- Tier 1 candidates: the query is 20 words of the input, so the second and
  third licence of a bundle are missing (MIT in mypy, BSD-3-Clause in numpy
  and dateutil).
- `partial_ratio_alignment`: 3.3 s on mypy, 137 s on numpy over fingerprint
  hits; 2 to 4 times slower than matching blocks on word codes even on a
  window.
- A padded window for `fuzz.ratio`: caps a perfect copy at about 95.2, so
  the score must be taken on the trimmed span.
- D7 overlap by highest similarity ("highest score; exact tie, longer
  span"), and its epsilon variant ("longer within 1 to 2 points", 351 of
  360): replaced by the key `2 x matched - len(text)`, which keeps the
  longer of two nested whole texts (Python-2.0.1 over PSF-2.0) and the
  exact text over a longer look-alike (BSD-3-Clause over BSD-4-Clause).
- A 1.1x skip gate (skip when the input is no longer than 1.1 times the
  answer's text): GPL-3.0 followed by MIT would read as GPL-3.0 alone.
- The `WORD_MISS` prefilter (distinct-word set difference): saves at most
  2 ms, needs 20 MB; answers identical with it off.
- At most 8 positions per n-gram or 3 windows per text: wrong names on
  bundles (BSD-3-Clause x 10 then BSD-2-Clause listed BSD-3-Clause-HP).
- Naming a bare ID under `as-written` (a bare text answer would be wrong
  for a text with an `-only` and `-or-later` form).
- Look-alike rule as "key within 3 percent of the hit": refused exact
  Apache copies (Pixar's key is 0.7 percent below Apache-2.0's) and missed
  PySocks and jsonpointer. The reach 0.90 and near fit 0.93 give the same
  answers on the real files from 0.80 to 0.93.
- A length bound of 1.05 times the input for a hit, look-alikes at 1.150
  (against the gap guard): it depends on what else the input holds, so it
  misses a look-alike in a bundle, and on the text's length, so it refuses
  a short text that lost a few words (section 5, "Gap guard").
- The gap in words: 5 to 6 times stricter on Han and kana (a token per
  character) than on Latin script.
- Storing the coded texts in the database was first rejected (9 ms instead
  of 72 ms, 5.6 MB estimated, a `BUILD_VERSION` bump, "not worth it at
  0.15 s once"), then done in build 6: 3.0 MB more (21.4 to 24.4 MB), a
  first `detect` on a licence file 0.14 s faster (0.45 to 0.31 s on
  mypy's `LICENSE`).

### 7. Known limits and follow-ups

- Wrong names (before the look-alike rule): 4 files of 493, BSD look-alikes
  (appnope, PySocks, sphinx 7.4.7, sympy); the rule removes PySocks, sphinx
  and sympy (and torch's NOTICE). appnope (2-clause BSD named BSD-1-Clause)
  is unchanged by the rule: still named.
- The look-alike rule loses 7 right names (section 5); template-aware
  scoring would recover them (roadmap item 64).
- Concurrent first calls each load the text corpus (no lock): wasted work
  only (roadmap item 65).
- Six BSD-3-Clause files with "MAY NOT" wording are empty: the span ratio is
  0.97 but `not` (a critical word) occurs once more than in the List text.
  By design.
- Apache-2.0 notice-only files (about 17 to 20) are empty by design: the
  notice is not found against the core (coverage 0.06). Also four MPL-2.0
  notices, two GPL notices, a docutils fragment, a psycopg2 notice.
- Exception texts are not in the database, so a bundled exception is not
  listed.
- MIT x 280 (47,600 tokens) is under the token limit and answers; the
  adversarial inputs past a limit (same family at 49k tokens: windows;
  long licences with 1 to 4 percent noise: word cells) give null, not
  partial.
- About 12 files (2 percent) show a look-alike disagreement: `detect()`
  answers one List text and TEXTS names the right one (for example
  BSD-2-Clause answered as BSD-2-Clause-pos-unchanged, MIT as JSON). Using
  TEXTS as ranking evidence would fix them; it is a later change, because
  it changes answers.
- Not measured: Linux, Windows, coverage runs, Python 3.14; filled-in
  placeholders and re-wrapped clauses; input built to defeat the vote
  windows.

### 8. Used by the marker floor (item 67, 2026-11-25)

`markerfloor` asks the same search whether a marker's confidence floor speaks
for the whole input. A marker (a GPL notice, the BSD clauses, a `License:`
field) lifts a candidate to at least 0.95 times its confidence; in a file of
several licence texts that lifted one of them over the file (Pillow's
`LICENSE` answered `GPL-2.0-or-later`). Now, where the input's `COVERAGE` of
the marker's licence is above 1.05 and the search finds texts that are not all
of that licence's same-text group, the candidate keeps its additive boost only.
No text found keeps the floor: the rule acts on positive evidence alone.
Where a floor is taken back, every candidate whose licence is none of the
texts found (same-text group, replacement ID, exception dropped, as for the
floor) is dropped from the ranking; one of the texts found stays as scored.
Without that, a look-alike the file does not hold answered once the floor
was gone: a BSD-3-Clause text and a BSD-2-Clause text gave `Sleepycat`
0.9103, BSD-3 and BSD-4 `Sleepycat` 0.9264 (review of PR #243).

- **Direct call.** The check calls `wholetexts.found_rows`, not
  `textnames.held_texts`, which `textnames.skipped()` turns off for terse
  `detect`, `is-*` and `is_*()`: a check that depended on printing `TEXTS`
  would give those another answer than `-v`. `TEXTS` then searches again with
  the final answer; its tie preference for the answer's group can name a tie
  differently, never find other rows.
- **Once per input.** The search runs at the first candidate whose floor binds
  above coverage 1.05, with that marker's licence as the tie preference, and
  is reused for the rest (the same answers as one search per marker, on the
  plan's 233 inputs where a floor bound).
- **Changes**: 16 answers at 0.85 of 6,543 inputs, no golden row; the list
  and the rules rejected are in
  [`tech-debt-resolved-0-9.md`](tech-debt-resolved-0-9.md) (item 67).
- **Cost**: the search runs on 25 of 499 real files (45 of 4,170 short and 22
  of 1,665 long fixtures, 3 of 209 mixed), +23 ms a file on terse `detect`
  (+4.5 percent), nothing elsewhere. A first use in a process reads the corpus
  (20 ms from `text_codes`, 160 ms coded for a build-5 database).

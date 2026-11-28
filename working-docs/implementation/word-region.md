---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Tier 2 on the word region (0.10.0 task T4)"
---

## Tier 2 on the word region (0.10.0 task T4)

Status: task T4 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`, section 3.2), built 2026-11-27
on the T3 tree ([gram-candidates.md](gram-candidates.md)), not merged.
Measurements: Apple M-series, Python 3.10, SPDX License List 3.29.0, the
harness of `.claude/speed-0-10` (sides `T4-1` to `T4-3`) against side
`T3-2` and the 0.9.4 baseline, and runs of the harness sets on the T3 tree
(`base`) and this one, side by side.

### 1. What was built

Tier 2 aligns a fragment (an input shorter than four fifths of a candidate's
text) with the candidate's text: RapidFuzz's `partial_ratio_alignment`
slides it over the text, then `token_sort_ratio` scores the window it found.
Its cost grows with the characters on both sides.

- `wordregion.located` aligns the input's word codes with the text's codes
  (`textcorpus`, one code point a token, a Han or kana character a token).
  An alignment of `ACCEPT_SCORE` (60) or more gives a region: the window,
  as many tokens as the input at least where it was trimmed at an end of
  the text, padded by `PAD_WORDS` (4) tokens each side, as characters from
  the start of a token to the end of one.
- `wordregion.WordRegions` codes the input once a `detect()` call, at the
  first candidate that asks (the corpus is read then, not before), and
  gives a region only for the codes of the very text the candidate holds.
- `wordregion.best_possible`: no word alignment is made that cannot reach
  60, judged by the codes the two share (section 4).
- `regionalign` runs the character steps on the region (section 3).
- `similarity.fragment_similarity` takes a `Query` (`query_of`: the input,
  its words, its probe, the regions, the wall character); with no region
  it does what it did: the probe gate, then the whole text.
- `--diff` (`detector._diff_pair`) widens the window to whole tokens
  (`textgrams.whole_tokens`, `snap=True`); the scores are not snapped.

No region, the whole-text scan as before: a candidate whose ID the corpus
has no text of (a `LicenseRef-*` marker), a text other than the corpus's for
its ID, a weak word alignment, or an input `alignment_affordable` refuses
(which never reaches Tier 2's alignment). A corpus restored from damaged
stored codes is built again in memory (`textstore`), so its regions are
those of an `update` build (`test_word_region_detect`).

The core of a licence (`core_similarity`) is scored by `token_sort_ratio`
alone, with no alignment: nothing to locate, left as it was.

### 2. The two numbers

Decided by the plan (60 and 4), then measured on the core set (868 inputs)
against the T3 tree, all runs side by side (CPU seconds; rows: inputs whose
top 3 changed order or ID; scores: inputs where only a score moved):

| Accept | Pad | CPU | Rows | Scores |
| ------ | --- | --- | ---- | ------ |
| base | | 41.4 | | |
| 50 | 4 | 31.6 | 25 | 95 |
| 60 | 4 | 35.8 | 18 | 74 |
| 70 | 4 | 38.4 | 14 | 68 |
| 60 | 2 | 35.6 | 19 | 68 |
| 60 | 8 | 36.0 | 18 | 77 |

Every variant loses the same two right answers at 0.85 (section 6). 60 and
4 stay: 50 moves more for its time, 70 saves less, and the padding hardly
matters once a region can grow (section 3).

### 3. The character steps on a region (`regionalign`)

Given a region alone, RapidFuzz takes its cut ends for the text's ends: it
scores windows trimmed there, which the text does not offer and which can
win, and which cost time in the cube of the fragment's characters when the
fit is poor. So:

- **Walls.** Where a region cuts the text, a wall stands for the rest: a
  run, as long as the input, of a character the input lacks
  (`Query.wall`). A window may run into it, as into the text, but matches
  nothing there. So a region never scores above the whole text
  (property test, 40 seeds).
- **Held whole.** A region cut at both ends and no longer than the input
  (the input holds more: other words, a blob) needs no scan: the best
  window holds the region whole, so the score is the longest common
  subsequence over the input's length (`held_whole`; equal to the walled
  scan in a property test of 40 seeds).
- **Growth.** A window that runs into a wall says the characters align past
  where the words placed them (a distorted copy has other tokens): the
  region grows on that side by the input's length, snapped to tokens, at
  most `GROWTHS` (2) times, then the whole text is aligned. Without it,
  `Zimbra-1.3` lost its answer.

### 4. Japanese and Chinese: the bound on shared codes

Han and kana characters are one code each, so a Japanese input has nearly
as many codes as characters, and its word alignment with an English text
cost as much as the character steps it was meant to spare (31 ms a
candidate for `CC-BY-SA-2.1-JP` whole against `CC-SA-1.0`; the `cjk` set
went from 0.49 to 0.70 s, 1.46 times slower in side `T4-2`).

RapidFuzz compares the shorter string (*n* codes) whole with windows of the
longer, at most *n* long; a window of *k* codes scores 2 x LCS / (n + k),
and the LCS is at most min(k, *shared*), the codes the two hold in common
counted as a multiset. So no window scores over 2 x shared / (n + shared)
(`best_possible`), and an alignment under 60 by that bound is not made. It
is a bound, not a guess: no region changes (core, `cjk` and `roadmap` sets:
every row equal), and the `cjk` set is back to 0.46 s. The bound is
reached: 3 of 7 codes at a text's start score 60 exactly (unit row).

### 5. Measures

Harness, side `T4-3` (machine busy: read as ratios):

- Against `T3-2`: core CPU 27.1 s to 23.4 s; `long:distorted_05` and
  `_10` 1.2 times, `real` 1.3, roadmap item 11 73 times (3.94 s to
  0.05 s), `stress:prose 100 KB` 2.7; `cjk` 0.48 s to 0.50 s; no kind
  slower than 1.14 times. Two top answers at 0.85 move (section 6), every
  other set none; labels unchanged; fixtures at 0.85 right 421 to 419.
  Peak memory 98 MB against 97.
- Against 0.9.4: core CPU 353.2 s to 23.4 s, 15.1 times (target 15); by
  kind of the core set 6.8 times (`long:distorted_20`) to 21.1
  (`long:distorted_05`); fixtures at 0.85 right 419 to 419, wrong 46 to
  45.

`tests/test_accuracy.py --run-benchmark`, top 1 / 3 / 5 (T3 tree, then
this one): verbatim 94.95 / 98.38 / 99.46 on both; 2 % 94.77 / 98.20 /
99.28 on both; 5 % top 1 84.50 to 84.32 (one input), top 3 and 5 equal.

The sweep of `AGENTS.md` (3,408 slices of real texts at four offsets and
four lengths, Han and kana re-wrapped at 20 and 37 characters): two top
answers move, both ties at 1.0 of two texts that hold the slice whole
(`BSD-Inferno-Nettverk` to `BSD-3-Clause-HP`, `ISC-Veillard` to `OSSP`,
the slice's own); 22 change a score only, the right answer kept where it
was over 0.85 (six, by 0.01 at most). CPU 104 s to 71 s.

Where the time went before the bound (fragment scores of the core set, by
the region a candidate got): no region, 408 calls, 7.8 s; a region at an
end of the text, 1,228 calls, 4.4 s; a region cut at both ends, 318 calls,
0.29 s. The whole-text scan of the same calls: 20.0 s, the regions 12.7 s.
Most of what is left is the edge windows at a text's ends and the
candidates that get no region.

Roadmap item 11 (fragments among random words): an Apache-2.0 slice of
3,000 characters from 0.29 to about 0.05 s; 200 words of Apache-2.0 among
random 25-character tokens from 5.35 to 0.016 s (no answer either way).

### 6. Answers that moved

Core set, against the T3 tree: 18 inputs change a row of their top 3, 74
a score only. Two right answers at 0.85 are lost, both ties of equal-score
windows that RapidFuzz breaks by position, so the window
`token_sort_ratio` scores again differs:

- `long:UCL-1.0:distorted_10`: `TGPPL-1.0` 0.898 over `UCL-1.0` 0.8944.
  The whole text has three windows at 77.005 (characters 5,548, 5,632,
  5,641); the region's first is another of them.
- `long:OLDAP-2.3:distorted_20`: four OLDAP texts tie at 0.8832 and
  `OLDAP-2.2` ranks first by ID. Windows at 690, 709 and 722 all score
  84.67.

Golden (`python -m tools.golden`): listed with their reasons in
`tests/harness_changes_region.py`. One new wrong answer:
`short/Brian-Gladman-2-Clause/head_700` answers
`Brian-Gladman-3-Clause-no-conversion` 0.8616 (0.8247 before). The input
is the 2-Clause text, which lacks the 3-Clause's endorsement clause; the
whole-text scan's best window is trimmed at the text's start (characters 0
to 575, alignment 73.46, sorted words 78.0); the region (173 to 817)
leaves the start out and its best window (205 to 817) aligns lower (68.1)
but scores higher by sorted words (81.7). Not fixed: a rule that gives no
region when the input's codes are two thirds of the text's or more fixes
it (core CPU 38.4 s against 35.8 s, the same two ties lost; at one half,
40.7 s), but it is a new number. One wrong answer is gone:
`HPND-Pbmplus` `head_1000` (0.8557 to 0.8250).

### 7. Words of two letters or fewer

An input of short words (`"on an as is to ..."` to 100 KB or 1 MB, `"a b c
"` x 170,000) found no candidate in 0.9.4 (the FTS5 trigram index needs
three characters) and finds some from the word grams of T3. It is too long
to align, so each candidate costs one `token_sort_ratio` of the whole
input: no word region, no alignment (asserted in
`test_word_region_detect`). CPU, warm, best of three:

| Input | 0.9.4 | T3 | T4 |
| ----- | ----- | -- | -- |
| short words 100 KB | 79 ms | 325 ms | 324 ms |
| short words 1 MB | 787 ms | 3,107 ms | 3,089 ms |
| `a b c` 1 MB | 850 ms | 1,294 ms | 1,282 ms |

Above the limit of 1.2 times 0.9.4. Of 3.1 s, 2.4 s are 10 calls of
`token_sort_ratio`; the rest is normalising and gram hashing (about 0.1 s
for 100 KB, against 79 ms in 0.9.4). Not fixed here, since every cure moves
a score: a `score_cutoff` in that call (a far shorter text then scores 0,
not 0.03), a share of the input's grams a candidate must hold (task T3's
selection), or a bound returned for the score.

### 8. Paths rejected

- A region widened to the input's length at every end: the edge windows
  of a poor fit made a blob 5 s.
- Sorting the region's tokens before the alignment: 446 scores moved.
- Rescanning the whole text when the region's window touched an end, or
  under a bar: as slow as the T3 tree or slower.

### 9. For the tasks after this one

- A tie of equal windows decides which window is scored again: a change
  of haystack (a region, a wall, a stored text) moves near ties. Run
  `tools.golden` after any change to what is aligned.
- The bound of section 4 holds for any RapidFuzz `partial_ratio` call; the
  character alignment could use it too (against the characters).

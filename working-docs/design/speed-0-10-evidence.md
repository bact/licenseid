---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Evidence for the 0.10.0 speed plan

What thirteen rounds of profiling and prototyping measured, on 2026-11-26 and
2026-11-27. Input to [`speed-0-10-plan.md`](speed-0-10-plan.md); no code
changes here. Every prototype was a monkeypatch run against a frozen copy of
the source, never the checkout.

## Method

- Code: `main` at `11b89de` (build 7), copied with `git archive`. Release
  0.9.4 (`527df38`) is that code with another version string and docs, so
  "present" is 0.9.4. Rounds one to ten ran on `f050bd6`; the prototype gave
  the same top answers on both. Database: List 3.29.0, 740 licence rows, 708
  texts, 679 groups of equal text. Python 3.10; Python 3.14 where said.
- Benchmark: 868 inputs. 300 real licence files (`LICENSE`, `COPYING`,
  `NOTICE` of installed distributions, 497 unique, a fixed sample), 408 long
  fixtures (68 licences, clean and five distortion levels), 160 short
  fixtures (40 licences, head and tail of 300 and 700 characters).
- Weak labels: 225 of the real files belong to a package that declares one
  licence ID. A top answer is `agree`, `other` or `none` against it. A
  bundled third-party file may rightly differ; nine `other` files are label
  errors (a GPL file in a BSD package).
- Time is CPU seconds of `detect()`, warm, one process, unless said. The
  machine ran other sessions' work for part of both days: a figure is only
  compared with one taken beside it.
- "Present" is the code as it is. "Prototype" is prototype 6 with the
  settings of the plan, unless a row says otherwise.

## Where the time goes now

| Input | Present |
| - | - |
| Declared value (ID, expression, name, URL, tag) | 0.2 to 0.9 ms |
| Licence text, median | 270 to 450 ms |
| 868 inputs, two runs on `11b89de` | 370 and 447 s CPU (the machine busier in the second) |
| 868 inputs on `f050bd6`, alone | 501 s wall |
| Import of `licenseid.cli` | about 72 ms after 16 ms of interpreter |

- Over 90 % of a text's time is RapidFuzz character alignment of about 50
  Tier 1 candidates. SQLite FTS5 is 10 to 30 ms. A change of database
  engine cannot give more than about 10 %.
- Threads give the present code little (1.3 times with four);
  `process.cdist` needs numpy.
- Only 3 % of real licence files equal a List text after normalisation: an
  exact-hash shortcut alone gains little.
- The FTS5 query holds few of an input's words (`ftsquery`: 20), so it
  misses the true licence of some real files; the prototype's retrieval
  gained 8 answers and corrected 4 for that reason alone.

## Steps of the prototype, each measured

Wall seconds for the 868 inputs, each run alone, on `f050bd6`.

| Step added | Seconds | Against present |
| - | - | - |
| Present code | 493 to 501 | 1 |
| Word 3-gram retrieval in place of FTS5, no windowed search | 52 | 9.5 |
| Word-level locate before the character steps | 41 | 11.9 |
| No answer at once when the best gram score is under 0.3 | 33 | 15 |
| Whole text first, tight selection, postings in SQLite | 21.7 | 23 |
| Three pinned runner-up rows (maintainer's decision) | 13 % more CPU | about 20 |

That table is of the early prototypes. The final one, with the settings of
the plan, on `11b89de`, CPU seconds, present run of 370 s:

| Kind | Present | Prototype | Ratio |
| - | - | - | - |
| Real files (300) | 147.4 | 6.4 | 23 |
| Short fixtures (160) | 16.1 | 0.8 | 21 |
| Long, clean to 5 % distortion (272) | 135.8 | 8.4 | 16 |
| Long, 10 % distortion (68) | 55.1 | 4.0 | 14 |
| Long, 20 % distortion (68) | 15.9 | 2.5 | 6 |
| All 868 | 370.3 | 22.0 | 17 |

Against the busier present run (447 s) the ratio is 20. Real files: median
367 ms to 8.8 ms, ninth decile 898 ms to 24 ms. The weakest kind is the
heaviest distortion, where neither code answers much and the none bar of 0.1
lets more inputs through to Tier 2 than a bar of 0.3 would.

## Answers

| Measure | Present | Prototype |
| - | - | - |
| Labels, agree / other / none | 182 / 19 / 24 | 192 / 15 / 18 |
| Fixtures at 0.85, right / wrong / none | 427 / 38 / 103 | 428 / 36 / 104 |
| Fixtures at 0.70 | 466 / 56 / 46 | 472 / 49 / 47 |
| Fixtures at 0.50 | 473 / 77 / 18 | 482 / 59 / 27 |
| Labels at 0.50 | 182 / 31 / 12 | 195 / 16 / 14 |
| Accuracy test, verbatim, top 1 / 3 / 5 (%) | 94.95 / 98.38 / 99.46 | same |
| Accuracy test, 2 % distortion | 94.77 / 98.20 / 99.28 | same |
| Accuracy test, 5 % distortion | 78.92 / 89.01 / 90.81 | 83.96 / 96.04 / 98.74 |
| Accuracy test, run time | 770 s | 41 s |

Against the present code on the 868 inputs: 10 answers gained, 3 lost, 17
changed. The accuracy test's top-1 misses fall from 180 to 152 (32 fixed, 4
new, all at 5 % distortion: `CC-BY-NC-SA-3.0` as `CC-BY-3.0`, `OLDAP-2.0` as
`OLDAP-2.0.1`, `OLDAP-2.2.1` as `OLDAP-2.2.2`, `OSET-PL-2.1` as
`MPL-2.0-no-copyleft-exception`).

Golden harness (`tools.golden`), every part: `cli`, `id` and `long` are as
the golden. `mixed`, `several`, `name` and `value` move no answer. `short`
(588 answers) moves 17 answers, judged here against the licence the
fragment was cut from:

| Move | Count | Detail |
| - | - | - |
| None to the fixture's licence | 4 | `Apache-1.1`, `BSD-Protection`, `PHP-3.01`, `PostgreSQL` |
| Another licence to the fixture's | 3 | `IEC-Code-Components-EULA`, `SGI-B-2.0`, `ZPL-1.1` |
| Another licence to none | 3 | `HPND-Markus-Kuhn` head, `Linux-OpenIB` head, `TOSL` head |
| Another licence to a third | 3 | `GLWTPL`, `OLDAP-2.2.1`, `RHeCos-1.1` tails |
| None to another licence | 4 | See below |

The four new answers that are not the fixture's licence, each to examine
before it is accepted (precision over recall):

- `TCL` tail of 1,000 characters: `SWL` at 1.0 (was `MIT-feh` 0.63).
- `Clips` tail of 500: `NetCDF` 0.8742 (was
  `HPND-sell-variant-critical-systems` 0.8206).
- `Brian-Gladman-2-Clause` head of 700:
  `Brian-Gladman-3-Clause-no-conversion` 0.8616 (the same ID at 0.8247 now).
- `Spencer-86` head of 500: `Spencer-94` 0.8627 (the same ID at 0.8404 now).

The last two are one candidate whose score crosses 0.85 by 0.02 to 0.04.
"To none" is to no answer: the row stays, under 0.85. Of the other 113
moved lines, 6 keep their answer with another score, 48 lose a row under
0.85, 57 show another ID under 0.85 and 2 the same ID at another score.

Other languages: the top answer is the same on all 119 Japanese, Chinese,
Dutch, German and French fragments and whole texts tried.

## Findings behind each rule

### Gram retrieval and selection

- Word 2-grams to 5-grams rank the true text alike on clean text and
  fragments; larger grams lose heavy distortion (inputs whose best score is
  under 0.3: 24, 29, 35, 39 of 68).
- No one ordering wins. `shared / min(|Q|, |C|)` is right for fragments and
  distortion. `2 x shared - size` is right for whole files (true text first
  in 186 of 225 real files against 161) and fails on fragments.
- Eleven selection rules, end to end: answers hardly move (2 to 7 of 868).
  The tight rule (top 3, plus those within 0.05 of the best, at most 20)
  scores 1,570 Tier 2 rows against 2,875 and is more precise: `OpenSSL`
  distorted no longer answers `SSLeay-standalone` at 0.91.
- No answered input scored under 0.4, so a "none" bar under that moves no
  answer. Bar 0.3, 0.1, 0: CPU 22.2, 22.3, 24.4 s; no top answer or label
  moves; of 125 no-answer inputs that list low rows now, 86, 99, 122 still
  list some.

### Whole text first

- `texts()` (the word-level locator of `textlocate` and `wholetexts`) found
  exactly one text in 247 of 300 real files. On 193 labelled ones it agreed
  with the declared licence in 184; Tier 2 in 175. (Round three, on
  `f050bd6`, before PR 247 changed the search; not run again.)
- Better retrieval exposes a Tier 2 flaw the present code hides: an MIT file
  with a few extra lines scores `JSON` above `MIT` (token sort ratio 93.3
  against 93.2). Narrowing Tier 2 to the one text found cures it.
- The search over the candidates' texts equals the search over all 679 on
  every one of the 868 inputs.
- Guard: a shorter List text held whole inside a fragment (`SSH-short` in an
  `SSH-OpenSSH` head) must not narrow. Rule: no narrowing when another
  candidate shares more 3-grams than the found text, times a margin. In an
  offline lab of 11,828 inputs any margin from 1.02 to 1.25 guards no right
  narrowing: a plateau, not a tuned number.

### Runner-up rows

The CLI prints three rows by default. A text found whole would otherwise
list only its group.

| Runner-ups added | CPU s | Real median ms | Old rows back (of 938) |
| - | - | - | - |
| None | 16.0 | 5.2 | 244 |
| 1 | 16.8 | 5.6 | 446 |
| 3 | 18.1 | 5.9 | 628 |
| 5 | 22.8 | 13.9 | 689 |
| Within 0.2 of the best | 29.9 | 30.9 | 741 |

- Unpinned, a runner-up outscores the found text in 12 or 13 of 465 inputs
  and wrong answers return (labels 186 / 21 / 18). Runner-ups must rank
  under the found text.
- Ranked under it but shown with their own score, 11 of 868 inputs show a
  runner-up scoring above the answer, every one `JSON` over `MIT` (by
  0.0009 to 0.019).
- A runner-up that shares almost nothing costs a long alignment: the List's
  Japanese text took 145 to 158 ms until runner-ups under the "none" bar
  were left out (9 ms; no row at 0.85 or more lost).
- Gram order is not Tier 2 order: no order of runner-ups (four tried)
  restores every old row; `shared / min` is the cheapest.

### Many texts in one input

55 inputs of 2 to 40 fixture texts joined, clean and at 2 % and 5 %
distortion (165 in all). With a fixed 40 candidates the prototype lost TEXTS
entries: none up to 8 texts, 1 at 10 and 1 at 15, 28 of 97 at 20, 129 of
185 at 40.

Inputs of 55 whose TEXTS equal the present code's:

| Candidates beside the top 20 by score | Clean | 2 % | 5 % |
| - | - | - | - |
| Top 20 by `2 x shared - size` | 34 | 31 | 40 |
| Texts held at 0.9 or more | not run | 52 | 41 |
| Texts held at 0.7 or more | 55 | 55 | 52 |
| Texts held at 0.5 or more | 55 | 55 | 55 |

"Held at 0.5" is `shared / size >= 0.5`: half of a text's own grams are in
the input. With it the size-key half is not needed. The locator then votes
on about twice as many texts (real-file median +2.5 ms); the runner-up floor
above pays for it (22.6 s before both, 22.0 s after).

### Han and kana

Grams over space-split words break when Japanese text is wrapped at another
width. Whole texts still answer. Two re-wrapped fragments of
`CC-BY-SA-2.1-JP` lost their low row (0.81 and 0.60 now; neither code
answers). Per-character grams (`textcorpus.split_words`) give 0.8083 and
0.6104, 0.7 % more postings, the same CPU. Re-wrapped Chinese fragments
answer either way, 12 to 24 times faster than now.

### Prose that names a licence

- 300 real README texts holding the word "licens": the top answer is the
  same in all (60 answers: 47 by text, 13 by tag); 63.6 s against 7.0 s.
- The present code lists a row for all 300, the prototype for 117. The
  present code's 132 first rows between 0.5 and 0.7 agree with the package's
  declared licence in none (`Condor-1.1` for sqlalchemy, `LGPL-3.0-only` for
  typer; 101 name another licence, 31 packages declare none that
  `resolve()` reads). The prototype has no first row in that band.
- 96 short notices and 77 inputs with a text in prose, as a code header or
  beside a tag: the top answer and `texts()` are the same in all.
- So the windowed search (`_match_mixed_content`), which the prototype never
  runs, costs no answer on any probe, and the low rows it adds are noise.

## Storage, cold start and memory

| Item | Present | Prototype |
| - | - | - |
| Trigram index (`license_index_data`) | 10.3 MB | not read |
| Postings, one blob per gram | none | 3.2 MB |
| Database file (build 7) | 24.7 MB | 17.7 MB without FTS5 |
| First `detect()` of a process (round five) | 80 to 1,215 ms | 33 to 90 ms |
| Peak memory, one file / 300 / 868 | 71 / 99 / 99 MB | 55 / 86 / 91 MB |

- FTS5 `MATCH` is never called by the prototype: 0 calls on the benchmark
  and on every golden part.
- Without the FTS5 table (texts copied to a plain table, `VACUUM`) the
  file is 14.4 MB; postings and entry checks add 3.3 MB. With the FTS5
  table kept it would be 28.0 MB.
- 0.9.4 on that file: `detect`, `resolve`, `is-osi`, `update` and
  `clear-cache` each print `ERROR: database: invalid: <path>` and exit 2;
  the file's SHA-256 is the same after all five. The maintainer accepts
  this (plan, D5): no other install shares the data directory.
- Prototype 6 on a copy whose text table is plain (same name, same row
  order, an index on the ID; the shape check switched off), beside the
  same file with FTS5, two runs each, final settings: answers and `TEXTS`
  of all 868 inputs equal. CPU 26.7 and 27.0 s plain, 26.0 and 25.6 s
  FTS5; on the 568 fixtures alone 14.7 and 14.6 s plain, 15.1 and 15.1 s
  FTS5. The machine's load was 4 to 7: the difference is noise. 40 texts by
  key cost 0.4 ms from a plain table, 1.2 ms from the FTS5 one.
- Code of 0.9.4 that reads older files, which D6 removes: `schema_state`'s
  `older` state, `_ADDED_COLUMNS`, `_BUILD_COLUMNS` and `ALTER TABLE` in
  `dbschema`; `OPTIONAL_OBJECTS`; the in-memory fills of `dbcache`; the
  outdated-stamp warnings of `database`. 14 test files read these paths.
- An index built in memory costs 245 to 510 ms a process: it must be stored.
- `TextCorpus.restore` reads all 679 entries (32 to 42 ms). Vocabulary and
  the candidates' entries only: 2 to 4 ms.
- Per-entry check: a head digest (0.05 ms) and one SHA-256 per entry (0.02
  to 0.09 ms; all 679 in 12.8 ms). Nine damage cases (codes changed, text
  changed, codes deleted, vocabulary words swapped, regions changed, a
  check changed, patterns changed, no checks table, none): answers and TEXTS
  equal a full build in all.
- One call in a fresh process, minimum of 11, in ms. Round nine, on
  `f050bd6`, with prototype 5 (texts read per candidate, no per-entry
  check, three connections); prototype 6 was not timed this way:

| Input | Present | Prototype 5 | With start-up edits |
| - | - | - | - |
| MIT file | 698 | 110 | 99 |
| BSD-3-Clause file | 1,292 | 111 | 100 |
| Apache-2.0 file | 280 | 126 | 115 |
| GPL-3.0 text | 596 | 221 | 209 |
| 300-character tail | 168 | 107 | 97 |
| Distorted text | 303 | 109 | 99 |
| File with no licence | 212 | 121 | 109 |
| SBOM JSON | 413 | 135 | 125 |
| `resolve MIT` | 89 | 89 | 59 |
| `detect MIT` | 91 | 91 | 80 |
| `--version` | 86 | 86 | 50 |

- Start-up has no single offender: 121 regex compiles are 12 ms, `rapidfuzz`
  5.9, `importlib.metadata` 7.7, click 3.9. The edits: a lazy package
  `__init__`, `importlib.metadata`, `tarfile`, `gzip` imported at use,
  commands imported when named.

## Value path

`resolve()` is fast already (PyPI values mean 0.5 ms). `detect()` on 462
PyPI values: 1,371 ms to 810 ms (p90 6.5 to 3.0 ms) with four exact changes,
answers identical: `hiddenchars.space_out_hidden` returns at once for text
with no format character (it walks every character in Python: half of
`resolve()`'s time on a licence file, 2.56 to 1.41 ms); `grant_stem`
memoised; name rows under the threshold dropped by
`rapidfuzz.process.extract` before the Python loop; the whole value not
resolved a second time.

## Stress, threads, Python 3.14

- 18 large or odd inputs, one process each, final settings: the prototype
  is faster or equal on all but "100,000 distinct words" (0.58 s against
  0.47 s: one posting lookup per gram). `GPL-3.0-only` 30 times (1 MB):
  3.5 s against 15.1 s. Prose 1 MB: 0.9 s against 10.1 s. 20 texts joined:
  1.0 s against 1.5 s, the same 18 TEXTS. 100 texts joined: 5.4 s against
  5.5 s, TEXTS none in both (count limits). MIT on one line: 8 ms against
  325 ms.
- Four threads on one detector, the same work four times: present 1.3 times
  the throughput of one thread, prototype 0.8 times (its work is Python and
  SQLite under the lock). Four passes still take 19 s against 191 s.
  Answers are those of one thread in both.
- Python 3.14: the present code passes the suite (18,826 passed). The
  prototype fails the same tests as on 3.10, less the eight local SQLite
  ones. Benchmark rows and TEXTS are identical to 3.10.

## Test suite under the prototype

198 of 18,826 tests fail with the prototype loaded. None looked at loses a
right answer on the real database.

| Class | Tests |
| - | - |
| Option behaviour (`test_detect_options_paths`: option matrix 32, options shape the candidates 20, others 22) | 74 |
| Stored-codes contract, not kept by the prototype's lazy texts | 39 |
| Tests of what the design removes (`test_get_candidates`, `test_ftsquery`) | 18 |
| TEXTS call counts and low rows (three `texts` test files) | 32 |
| Variant tests (`test_option_matrix_variant`, `test_url_variant_stated`) | 16 |
| Others, one to four a file | 19 |

The variant tests and about ten on tiny seeded databases were not examined
one by one. The 74 were first read as "rows listed under the answer"; the
design review showed they pin what `exclude`, `only_spdx`, `only_common`
and `hint` do to the candidates, which the prototype changes (next
section).

## Options, and the name search on sections

Measured after the design review of 2026-11-27.

The prototype selects candidates, then filters them; the present code
filters 50 or more. Whole fixture text, rows returned:

| Call | Present | Prototype |
| - | - | - |
| MIT | `MIT`, `JSON`, and others | `MIT`, `JSON`, `FSL-1.1-MIT`, `Xnet` |
| MIT, `exclude` MIT | `JSON` 0.99 and a ranking of the rest | `JSON`, `FSL-1.1-MIT`, `Xnet` only |
| MIT, `exclude` MIT and JSON | A ranking of the rest | `FSL-1.1-MIT`, `Xnet` only |
| MIT, `only_common` | `MIT`, `MIT-0`, `X11`, `Xnet` | `MIT`, `Xnet` |
| Apache-2.0, `exclude` it | `ECL-2.0`, `SHL-0.51`, `SHL-0.5`, `Pixar` | `ECL-2.0`, `Pixar`, `ImageMagick` |

TEXTS is the same in every row (`exclude` does not touch it). The top row
is the same; the rows after it are the runner-ups of a text the caller
excluded. The plan filters before it selects.

The windowed search also runs the name tier on each section round
"licens". Kept alone, without the FTS5 windows:

| Measure | Without | With the section name search |
| - | - | - |
| Core set, CPU | 21.2 s | 33.5 s |
| Core set, top answers changed | | 0 |
| 300 READMEs, CPU | 7.0 s | 10.6 s |
| READMEs that list a row | 117 | 268 |
| READMEs, top answers changed | | 0 |

Of 238 READMEs whose rows change, a new row is the declared licence in 50,
another licence in 136, and 52 packages have no label; the new rows score
0.46 at the median and 0.55 at most. So the name search on sections makes
no answer, lists the right licence as a low row in about a quarter of
labelled READMEs, and costs half as much again.

## Inputs the roadmap names

Run on 2026-11-27 after release 0.9.4, for the open items of
[`tech-debt-roadmap.md`](tech-debt-roadmap.md) that this work touches.
Top row and seconds of CPU.

| Item and input | Present | Prototype |
| - | - | - |
| 11: 3,000 characters of Apache-2.0 | `Apache-2.0` 1.0, 10.2 s | Same, 0.10 s |
| 11: 200 words of Apache-2.0 among 120 random tokens | None, 9.6 s | None, 0.014 s |
| 61: MIT under two copyright lines | `MIT` 1.0, 0.52 s | Same, 0.012 s |
| 61: HPND under a copyright line | `HPND` 1.0, 0.16 s | Same, 0.015 s |
| 68: wcwidth `LICENSE` (MIT, then a grant) | `JSON` 0.9238 | `MIT` 0.9197 |
| 68: mypy_extensions `LICENSE` | None (`Unicode-DFS-2016` 0.77) | `MIT` 0.9641 |
| 69: certifi `LICENSE` (MPL-2.0 header) | None (`EFL-2.0` 0.51) | None (`MPL-2.0` 0.53) |
| 70: numpy `LICENSE.txt` with the GCC exception | None; three texts | Same |

Item 68 on the 300 real files of the benchmark:

- 12 files have no answer now while TEXTS names one text. The prototype
  answers 8, each with that text; 6 agree with the declared licence, 2 have
  no single label, none disagrees.
- 11 files answer now with an ID other than the one text TEXTS names. The
  prototype answers that text in 8 (all 4 with one declared licence agree;
  `JSON` to `MIT` three times) and keeps the present answer in 3, where the
  guard holds (an LGPL file in which `NCL` is found, `BSD-3-Clause-HP` at
  0.9998).
- TEXTS itself is the same on these and on Pillow's two files of 13 and 14
  texts.

So "whole text first" is item 68's idea, built. What item 68 warns of,
fragments of the HPND family that name a neighbour, is the class of the
four new answers under "Answers" above.

## More lists (issue 15), not for 0.10.0

1,667 ScanCode LicenseDB texts with no List ID, added to a scratch database
(2,375 texts).

| Measure | Present | Prototype |
| - | - | - |
| CPU | 415 s | 30.6 s |
| Labels | 160 / 42 / 23 | 192 / 15 / 18 |
| Top answers changed against SPDX only | 71 | 7 |
| Postings | FTS5 56 MB, 31 ms | 13.6 MB, 1.2 ms |

The present code breaks with more texts: the top 50 of FTS5 fill with
variants (a BSD-3-Clause file at 1.0 becomes `LicenseRef-scancode-net-snmp`
at 0.97). The prototype needs a second guard clause for look-alikes that are
sub-texts of a List text (an ISC file as `x11-acer`); with it the labels
equal SPDX only. Three answers still name a short generic text
(`robert-hubley`) in BSD tail fragments.

## Corrections made on the way

Kept so that an older note is not trusted over this one.

- "The CLI prints one row by default": it prints three (`--top` is 3).
- "`update` builds in 1.9 s": 3.1 s at `f050bd6`, 4.8 s at `11b89de` (the
  fingerprint step was left out).
- "No guard margin separates the look-alikes": only 1.0 and 1.1 had been
  tried.
- Round four's 50.8 s and 70.7 s were runs sharing the CPU (alone: 25 s and
  34 s).
- "0 top-5 misses" of the accuracy test was of its subset.
- The first notice probe was invalid: its "prose" held two licence texts.
- A "220 ms" Japanese fragment was the index build of that process (3.7 ms).

## Seen in passing, present behaviour

- A file that repeats one text (MIT 50 times, Apache-2.0 20 times) gets no
  answer in either code (score 0.11 to 0.33); TEXTS names it.
- "Licensed under the GNU Affero General Public License v3.0" answers
  `MPL-2.0` at 0.86 now; none in the prototype.

## Reviews of the plan, 2026-11-27

Design review (fourteen findings, the main ones checked in the code) and
where each went:

| Finding | In the plan |
| - | - |
| A runner-up "ranked by sort key" cannot hold: later sorts and the threshold read the score | Q1, section 3.4 |
| Postings had no validity check; stale after an older `update`; a bad blob crashes | Section 3.3, damage and versions gates, T2 |
| Options were filtered after selection; marker and hint candidates; TEXTS under filters; the 74 tests misread | Sections 3.1, 3.5, 8; Q9 |
| Dropping FTS5 collides with `dbcheck` and breaks 0.9.x on a shared directory | Decided by the maintainer (D5, D6): dropped, one shape, no reader of older files; T7 owns it, the versions gate the break |
| No checks table must not mean an in-memory build: regions are lost | Section 3.3, T6 |
| A lazily filled corpus is mutable state; `update` between reads | Section 3.3, T6 |
| T3 alone ships `JSON` over `MIT`; one build bump is not enough | Q8, tasks |
| Roadmap items 11, 61, 62, 65, 66, 68 | Section 10, gates |
| Other `found_texts` callers; gram bound and TEXTS | Sections 3.1, 3.4, 3.5 |
| The section name search goes too | Q3, measured |
| "Held at 0.5" ignores cores | Step 5, many-texts set, T5 |
| Hash sign, stored width, byte order, query size, fallback by table | Section 3.3 |
| Weak or missing gates | Section 6.2 |
| Inconsistencies of the first draft | Corrected |

Number check: about 190 figures against the result files and notes; ten
were of an older prototype or an older code state and are corrected, with
the stress run made again under the final settings.

## Where the prototype is

Scratch scripts, copied on 2026-11-27 to `.claude/speed-prototype-2026-11-27/`
in the maintainer's checkout (ignored by git; its `README.txt` maps the
files). They are dense monkeypatches, not code to merge. The benchmark of the
plan's first task replaces them.

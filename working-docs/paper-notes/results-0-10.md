---
Created: 2026-11-28
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Results for 0.10.0, the new detection engine

Measured on 2026-11-28 on one developer machine (macOS, Python 3.10, SPDX
License List 3.29.0), comparing the tree built for 0.10.0 (not released)
with release 0.9.4. Source of every figure unless another is named: the
compare report `L27-vs-0.9.4-final.txt` of the final gate run (kept outside
the repository, in the maintainer's `.claude/speed-0-10/reports/`), made
by the harness `benchmarks/speedgate` and the plan
`working-docs/design/speed-0-10-plan.md` (section 6 holds the sets and the
gates). The report names a real file only by a key such as
`real:f3b34c66:LICENSE`.

## What changed in the method

- Candidates for Tier 1 come from word 3-grams of the List texts, stored in
  SQLite as one blob of text numbers per gram, instead of an FTS5 trigram
  query (`working-docs/implementation/gram-postings.md`,
  `gram-candidates.md`).
- A text the input holds whole is looked for first, on one candidate set;
  when one is found, Tier 2 scores its group and three runner-ups only
  (`working-docs/implementation/whole-text-first.md`).
- Tier 2 aligns, by characters, the region of a text that the input's word
  codes locate, not the whole text
  (`working-docs/implementation/word-region.md`).

## Speed

CPU seconds, base over candidate, summed over each set; an A/A twin of the
base took 0.994 of the base, the widest kind differed by 1.01 times.

| Set (inputs) | 0.9.4 s | 0.10.0 s | Times |
| --- | ---: | ---: | ---: |
| Core (868) | 340.5 | 19.5 | 17.5 |
| Real licence files (300) | 140.46 | 5.81 | 24.2 |
| Long fixtures, clean (68) | 23.87 | 1.51 | 15.8 |
| Long fixtures, 20 % of characters distorted (68) | 14.31 | 2.05 | 7.0 |
| Short fixtures (160) | 15.47 | 0.72 | 21.4 |
| Many-text files, clean (55) | 71.87 | 31.20 | 2.3 |
| Many-text files, cores only (12) | 3.69 | 0.69 | 5.4 |
| CJK (24) | 3.34 | 0.39 | 8.6 |
| Options (36) | 9.53 | 0.77 | 12.4 |
| Stress, 300 KB of kana prose (1) | 0.26 | 0.27 | 0.9 |
| Stress, one MIT text on one line (1) | 0.30 | 0.01 | 35.9 |

- Real file median 329 ms to 8.7 ms. Prose (473 inputs) 11 to 16 times;
  standard headers 18 to 23 times.
- One call in a fresh process (minimum of 11, byte-code cached): a real MIT
  file 770 to 93 ms, BSD-3-Clause 1,348 to 110 ms, Apache-2.0 273 to 109 ms,
  the GPL-3.0 text 577 to 178 ms; `resolve` of an ID 88 to 63 ms; `detect`
  of an ID value 91 to 79 ms.
- Peak memory 97 MB (0.9.4: 107 MB). Database file 17.9 MB (24.7 MB;
  `working-docs/implementation/plain-text-table.md` section 2).
- Four threads over 150 items: 0 answers differ from one thread.
- Not measured by the harness: the 462 PyPI values (1.39 s to 0.84 s,
  measured earlier in the work, `working-docs/design/speed-0-10-plan.md`
  Outcome), the accuracy test and the golden (both pass in the test suite;
  no golden answer moved).

## Answers

- Labels of 225 real files with one declared ID, at 0.85: agree 182 to 193,
  other 19 to 14, none 24 to 18.
- Fixtures at 0.85: right 419 to 418, wrong 46 to 46; at 0.7 right 457 to
  460, wrong 65 to 61. The one right answer lost is the last 300 characters
  of `HPND-sell-variant-MIT-disclaimer-rev`, now `HPND-sell-variant` 0.9681
  (`working-docs/implementation/whole-text-first.md`, section 5).
- `TEXTS`: 0 of the inputs moved. Damaged stored data: 29 kinds equal their
  reference build.
- The 79 standard licence headers of the List, right / wrong / none at 0.85:
  as given 56 / 11 / 12 to 54 / 10 / 15; with placeholder lines cut 52 / 13
  / 14 to 49 / 15 / 15. The `-or-later` GFDL-1.2 header and the cut GFDL-1.3
  headers now answer `GFDL-1.1-invariants-only`: their wording equals the
  notice in the GFDL-1.1 text, so the two score almost the same, and which
  wins moves with the window Tier 2 aligns (roadmap item 71,
  `working-docs/design/tech-debt-roadmap.md`).

## Negative results worth reporting

1. A rule that passed its author and failed a reviewer. For thirteen pairs of
   List texts in which one holds the other whole, a fix (Tier 2 also scores
   the text that shares the most grams; a runner-up that holds the text found
   is kept) was measured on its author's 3,000 inputs and the project's
   harness with no loss. An independent adversarial review then found 17
   right answers turned wrong and 7 wrong answers where there was none
   before, at 0.85, for 8 gained, and up to 24 times the cost of a call.
   The rule was taken out (roadmap item 77). A rule measured on its
   author's inputs only has not been measured.
2. The tie rule for fragments that several texts hold, deferred. On 12,136
   slices of List texts (8 to 120 words), 2,557 are held by several
   licences; 0.9.4 names one holder in 1,953 and another licence in 30, the
   0.10.0 engine 1,989 and 3. A rule of no answer on a tie removes 1,963 of
   the 1,989 and moves no real file of 300, but it refuses the standard
   `GPL-3.0-or-later` header, the `BitTorrent-1.0` header and the Apache-2.0
   header without its copyright line, so it waits for item 71 (roadmap item
   72).
3. A measuring mistake. The session's environment set
   `PYTHONDONTWRITEBYTECODE=1`; the harness children inherited it and
   compiled every module again, so the one-call timing of a real MIT file
   read 152 ms where the same code with a byte-code cache, as an installed
   package has, took 93 ms. The harness now gives each child its own cache.

## Threats to validity

- One machine; the 1-minute load was about 2 during the runs, and the
  report flags the core, headers, many-text, memory, one-call, prose and
  roadmap sets as busy at its limit of 2.0, so times are read as ratios
  against the A/A twin.
- The fixtures are made from the List's own texts (a closed world), and the
  rules were chosen on the core set; the hold-out set of plan section 6.1
  (real files of another ecosystem) is not part of this run.
- 225 labelled real files, with known label errors (a declared licence is
  not the licence of every file in a package).
- Windows was not run, nor `tools.cli_matrix`, in this measurement. Both
  ran before the release: see "After the merge" below.
- Three gates failed and were accepted or deferred: fixtures right 419 to
  418 (the plan's stated exception), the real file `real:f3b34c66:LICENSE`
  at 211 ms against a limit of 200 ms (2,059 ms in 0.9.4; roadmap item 78),
  and the headers above (item 71).

## After the merge: what the release checks added

Sources: PR #249 and PR #250, their CI runs, the session of 2026-11-28
([ai-sessions-0-10.md](ai-sessions-0-10.md)).

- **A database fact that depends on the SQLite version.** An FTS5 table
  whose `data` shadow table is missing can be dropped by SQLite 3.50.4,
  3.51.0 and 3.54.1 and not by 3.46.0 (`vtable constructor failed`);
  without `config` none drops it. Measured with one script on four
  interpreters of one machine. A test of damaged files written on one
  SQLite states that SQLite's behaviour, not the package's.
- **A defect that moved out of the harness's sight.** Loading the
  expression parser at first use removed nine flags of the CLI matrix (a
  crash of the parser under `ja_JP.eucJP`, roadmap item 2) and cured
  nothing: an `AND` or `OR` value still crashes. One cell per locale now
  resolves such a value; 2,934 executions, one known flag.
- **How often a slash between two IDs is ambiguous.** Over all 547,600
  ordered pairs of the 740 List IDs of the test corpus, the value `A/B`
  reads as `A OR B` except for two pairs that the table refuses by name
  and two that are also one List ID with a dash (`HPND-doc`,
  `HPND-Intel`). The second two fail a benchmark that had failed since it
  was written, in 0.8.4 (roadmap item 63, which names one of them; the
  count over all pairs is new).
- **Published artefacts.** Wheel 1,764,211 bytes, sdist 1,763,419 bytes,
  both with List 3.29.0; a clean install builds a database of 17,879,040
  bytes with no network, and one `detect` of an MIT file takes 0.08 s of
  wall time there.
- **Hold-out set, still open.** The engine's numbers were chosen on real
  files of Python packages and on fixtures cut from the List. A separate
  benchmark project holds declared values of other ecosystems today, not
  licence files; its planned licence-text part is the hold-out set.

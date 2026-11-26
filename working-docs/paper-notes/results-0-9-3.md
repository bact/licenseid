---
Created: 2026-11-26
Last-Modified: 2026-11-26
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Results for 0.9.3, files of several licence texts, template variables

Measured on 2026-11-26 on one developer machine (macOS, Python 3.10). Part
one is the release gate of 0.9.3 (PRs #241 to #245) against v0.9.2. Part
two is the measurement behind roadmap item 59, before it was built. Sources:
`CHANGELOG.md` (0.9.3 section), session ba631669 (gates) and session
49fefc72 (item 59 plan); their reports were kept in scratch folders, not in
the repository.

## Release gate of 0.9.3

- Real corpus: 596 licence files taken from the `.dist-info` folders of
  installed PyPI packages (the corpus of whole-texts work, PR #241). It is
  rebuilt from an environment, not committed: the files belong to their
  projects.
- Golden files (2,264 rows over six parts): no answer moved. The 116 CLI
  records changed only by the new empty field (`TEXTS=`, JSON `"texts":
  null`).
- Real files: no right answer turned wrong. 7 wrong answers became no
  answer (pandas and grpcio had answered `BSD-4-Clause` from Apache-2.0's
  "4. Redistribution." heading; Pillow answered `BSD-4-Clause` or
  `Apache-2.0`, licences its file does not grant). 2 right one-licence
  answers became no answer (tensorboard, a numpy file of BSD-3-Clause and
  MIT). 10 stayed wrong: numpy and scipy answer `GPL-3.0-only`,
  scikit-learn `Apache-2.0`.
- Speed: +1.2% on the real files (A/A twin of v0.9.2: 1.000, per-file p95
  1.003), the cost of the whole-text search. Rotated order per round: during
  item 67 a run in fixed order had shown a false +15% median.
- Packaged data: the wheel and the sdist on PyPI hold the pinned SPDX
  License List 3.29.0 bundle (1,327,781 bytes, SHA-256 equal to
  `BUNDLE_SHA256`, 740 licences, 86 exceptions, 708 templates). A clean
  install builds its 24.4 MB database with no network.
- Finding: the open errors left on the real files were all one shape: a
  file that holds several licence texts.

## Files of several licence texts (item 59)

The ranker compares the whole input with each candidate licence, so in a
file that bundles texts the longest similar text tends to win.

- Real files with two or more whole List texts found: 37 of 596 (6%).
  Fixtures with two or more: 0 of 4,654. The test suite could not see the
  problem; only real files did.
- Options measured on the 37, against the release (an answer at 0.85):

  | Option | Wrong removed | Right lost | Wrong added |
  | --- | ---: | ---: | ---: |
  | No answer when several texts (A) | 13 | 8 | 0 |
  | AND of the texts (B) | 0 | 4 | 0 (9 wrong stay wrong) |
  | First text found (C1) | 0 (12 made right) | 1 | 0 |
  | Keep the answer only if its text is first (E) | 13 | 1 | 0 |

- C1 extended to every input named 5 wrong licences where the release
  had none: a third-party list, a NOTICE file, an OR file.
- E rests on a habit, not a rule: a licence file puts the project's own
  text first. Where the habit fails (pytype puts a vendored MIT first) E
  gives no answer, never another licence, because it only refuses.
- An AND of the texts found is a compliance conclusion. SPDX 2.3 (§8.6)
  lists each licence found in a file separately, and SPDX 3
  `hasDeclaredLicense` relates the artifact to each licence found; neither
  joins them with an operator. A tool cannot tell an OR file (a choice) or
  a documentation-only licence from a bundled one, and it cannot see
  exceptions that are not whole texts.
- A gate on coverage above 1.05 (the bound used for marker floors, PR
  #243) would have missed 30 of 144 made-up bundles: MIT then GPL-3.0 has
  a top coverage of about 1.03.
- Decision (maintainer, 2026-11-26): E, plus the list of texts found on
  every record of no answer.
- Threat to validity: the 39 real files with several texts (37 under a
  text answer, 2 under a declared value) were judged by the planning agent,
  one judge; the independent review rechecks them.

## Template variables in a whole-text fit (item 64)

Measured on 2026-11-26 against f050bd6 (List 3.29.0): plan of item 64
(session 001cb85d, options measured with the search monkeypatched) and its
build (worktree `template-texts`). Implementation and decisions:
`working-docs/implementation/whole-texts.md`, section 10.

Cause. A whole-text search that compares a licence text character by
character (Indel similarity, 0.95 to name, 0.98 to name past a near twin)
misses real copies that write their own copyright holder or project name
where the SPDX template lets the text vary (`<<var>>`, matching guidelines
B.3.3). In the ten known cases on 596 real files (BSD-3-Clause in sympy,
numpy, lxml, prettytable, nodeenv, isodate, dill, json_flattener; MIT-CMU
and X11 in Pillow) every difference but two typos and one word sits in a
var; the fill costs 2 to 5 points, so the copy fits under 0.98 and a twin
whose fixed text shares the filled words (BSD-3-Clause-HP: "the author")
doubts it (8 cases), or fits under 0.95 (2). Since rule E (item 59) a missed
own text also lets a bundled one become the first text found.

Options (search-only replay; "LOO" counts texts that name something with
their own group removed from the corpus, a proxy for false names):

| Option | Real names gained | Holder-filled own (324) | Plain LOO (679) |
| --- | ---: | ---: | ---: |
| Base (plain fit) | | 211 | 99 |
| Normalise vars only, no storage (T) | wrong twins | 229 | 108 |
| Vars left out, key credits vars (A) | | 272 | 123 |
| Vars left out, key capped (AK) | 24 | 274 | 122 |
| AK, fill checked by its pattern (AKG) | 22 | 274 | 116 |
| AKG, look-alike rule dropped (AKGD) | | 276 | 129 |
| AKG, masked fit only at 0.98 (AKGR) | 21 | 271 | 104 |

Findings worth reporting:

- Leaving the vars out changes what a key means, and three formulas fail
  before one holds. Crediting the text's var characters ranks BSD-3-Clause
  above an exact copy of BSD-3-Clause-HP (5 plain List texts lost their own
  name). Capping the key at the text's length lets a long holder line key
  both a text and its longer twin at their own lengths, so the twin wins
  (OLDAP-2.2 copies answered OLDAP-2.2.1). Putting the List's words back
  for each fill credits a twin with words the input lacks
  (Cornell-Lossless-JPEG lost to PostgreSQL's core; 14 long and 13 short
  fixtures). What holds: found less missing, a fill found up to the length
  of its List words, its lack counted once.
- An open var (`.*`, `.+`, `.{0,5000}`) absorbs a clause unless the fill is
  bounded: a bound of 150 characters over the List words keeps every real
  holder line and refuses a 170-character restrictive clause.
- Every bound that masking adds must also be read where it removes a
  rival, not only where it names a text. A length pre-filter on the whole
  text dropped a PostgreSQL copy with short fills before its fit was taken,
  so a shorter look-alike inside it was named; the fill bound (150
  characters) kept a longer text with an injected clause from doubting a
  shorter one inside it (MIT inside X11, 4 such cases of 1,223). Filtering
  on the fixed text only and fitting rivals with no fill bound removed all 8
  wrong names the masking had added on the review's sweep and lost no right
  one.
- Two texts that differ only in their vars (the cores of OLDAP-1.1 and
  NBPL-1.0) both fit any copy exactly once the vars are left out; only a
  tie rule (keys within 2 percent, as close a fit) keeps the corpus order
  from naming one.
- The `match` patterns of the List are written for raw text. Read on
  normalised words they must treat white space and marks as optional; read
  literally (`\s*` before `.+`) one pattern backtracks for 0.15 s on 3,000
  characters, as one optional space the worst of the 142 takes 0.07 ms.
- List numbers are vars (9,407 of 10,384 in 3.29.0); normalisation drops
  them only at a line start, so a sentinel written inline left 5,949 of
  9,611 vars unmapped.
- Masking does not make the near-twin rule redundant: the 0.95 tolerance on
  the fixed text still lets version twins and family neighbours through
  (HPND-DEC as HPND at 0.951, OLDAP-2.5 as OLDAP-2.6 at 0.982); a strict
  template match would refuse each.

Built (AKG, with the review's fixes) on 596 real files: 22 names gained in
20 files, all right, none lost, no answer at 0.85 moved; the first text
changes in 4 files, each to the file's own licence.
Cost: 0.34 MB of database (regions and the 142 distinct patterns, not the
5.1 MB of templates), about 24 to 48 ms to read the corpus once per process,
and `detect()` per input within noise of the base (906 inputs, three
interleaved passes, best of three: total x1.013, max x1.38).

---
Created: 2026-11-26
Last-Modified: 2026-11-26
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Results for 0.9.3, and files of several licence texts

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

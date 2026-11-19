---
Created: 2026-11-18
Last-Modified: 2026-11-18
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Results for 0.9.0

Measured on 2026-11-18 on one developer machine (macOS, Python 3.10),
comparing the 0.9.0 candidate with v0.8.4 and with `main` before the
release work (PRs #223 to #227). Sources: `CHANGELOG.md` (0.9.0 section),
`working-docs/implementation/pre-release-review.md` (record of 0.9.0),
`tests/harness_changes_*.py`, the gate tools `tools/golden`.

## Accuracy gate

- No answer that was right in v0.8.4 turned wrong (right-to-wrong: 0) over
  the golden files, the character snapshots and a real-value probe.
- Some right answers became "no answer" by design (precision over recall):
  `OSL-2`, `EUPL-1`, `CDDL-1`, `LGPLv2` forms that name a cut version.
- Finding: refusing is cheap to measure and rarely wrong; a guess is
  expensive to find. Each maintainer decision (whitespace in names, hidden
  characters, grant followed by an operator) was settled by asking what the
  mechanical rule loses first.

## Speed gate

Method: A/A twin of v0.8.4 beside the candidate, alternating order per
round, 8 rounds, medians, noise floor from the twin (3% or twice the MAD).

- The twin stayed within 1.5% on every case, so the differences are real.
- Slower than v0.8.4: hints +36% to +45%, tags (1000 values) +57%,
  full-text search +12%, `resolve()`-first on a long text +10%, short
  texts +17%, cold start +4%.
- Faster: name tier -26%, a 60,000-character word -93%.
- Most of the slowness was already on `main` before the 0.9.0 layers:
  each reading rule adds a check. The maintainer accepted it for 0.9.0.
- Threat to validity: macOS background tasks raised the load to 18 during
  one case, and one case (long text) did not run; the gate waits for load
  under 4 and repeats noisy cases.

## Review yield

Three review rounds plus a diff-only check after each fix batch. Fixes of
one round caused regressions found in the next (a tag dropped its second
operand after a grant; a mark glued to a grant); see
`working-docs/implementation/pre-release-review.md`.

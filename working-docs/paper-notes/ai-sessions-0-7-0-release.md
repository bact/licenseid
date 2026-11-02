---
Created: 2026-10-30
Last-Modified: 2026-10-30
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted release 0.7.0: the command line, a circular dependency and the freeze

The work of 2026-10-29 and 2026-10-30 after `ai-sessions-0-7-0.md`: the
`detect`/`match` rename, the `licenseid match` command, one output pattern
for every command, an interim Pitloom release forced by a circular
dependency, small resolver fixes, and the move from per-change review to a
whole-release review with an API freeze. Sources: licenseid PRs #133 to
#139, Pitloom PRs #400 and the 0.21.2 release, `../design/resolver-0-7-review.md`
(decisions P91 to P137), `../implementation/pre-release-review.md`,
`../implementation/release-process.md`, and the lead agent's session
record. Labels as in the other notes: **[observation]** is checkable in the
sources; the rest is the author's reading. The release itself is not
covered: this note stops before the tag (state on 2026-10-30, below).

## Process

- Same shape as before: one lead agent (Opus), an author agent per task, an
  independent reviewer given the brief and the diff, never the author's
  conclusions; the lead re-ran the check list and probed by hand; the
  maintainer opened and merged every PR. **[observation]**
- Agent sizing became an explicit rule (maintainer, 2026-10-30): "use
  cheaper agents and lower efforts for simpler tasks. use more expensive
  agents and higher efforts for planning and complex tasks, matters that may
  not have answers in advanced, or sensitive tasks". In practice: Opus at
  high effort for the CLI command (T10b), the contract batch, and every
  review; Sonnet at medium for docs, the small resolver fixes and the
  implementation note; mechanical edits (pins, links, renumbering) by the
  lead directly.
- The maintainer redirected scope several times mid-task (the output format,
  "all commands", JSON always RFC 8785); each redirection went to the
  running author by message rather than a new agent, so the author kept its
  context. **[observation]** (session record)

## Pull requests

| PR | Content |
| --- | --- |
| #133 | Docs sweep for 0.7.0 |
| #134 | T10a: `resolve()` becomes `match()`, the old matcher `detect()` (`LicenseDetector`, `Detection`), CLI `match` becomes `detect`; no aliases |
| #135 | Release pins: Pitloom 0.21.2 with licenseid 0.6.0; `build-system` floor raised |
| #136 | 0.7.0 implementation note; locale workaround points to the upstream fix |
| #137 | The pre-release review process (`pre-release-review.md`) |
| #138 | T10b: `licenseid match VALUE`, `--version`, one tab-separated `KEY=VALUE` pattern for every command, UTF-8 JCS JSON, `\n` line ends on every platform |
| #139 | Four small resolver fixes and their review fixes; the API freeze rule |

## The rename: one break instead of two

- `resolve` was "difficult to type and remember" (maintainer). The CLI's
  `match` (text detection) became `detect`, and the declared-value reader
  `resolve()` became `match()`, in the same release that broke the result
  shape, "so downstream API user will only need to update their code one
  time". **[observation]** (#127, #134)
- Proof of a pure rename: 2,595 CLI runs and 521 Python results by the
  author, 6,557 CLI and 1,042 Python cases by the reviewer, byte-identical
  except the help listing. **[observation]** (session record, #134)

## A circular dependency between two of the developer's own packages

- licenseid's build runs Pitloom's hook (to embed an SBOM); Pitloom imports
  licenseid. Pitloom 0.21 required `licenseid>=0.6.0` with no upper bound,
  so the rename would break every Pitloom 0.21 install, and with it
  licenseid's own isolated build, the moment 0.7.0 reached PyPI. CI on #134
  failed at exactly this: `ImportError: cannot import name
  'AggregatedLicenseMatcher'`. **[observation]**
- Resolution: an interim Pitloom 0.21.2 cut from the `v0.21.1` tag (not from
  `main`, which had moved on), only capping `licenseid<0.7`; a maintenance
  branch `maint-0.21`; licenseid then pinned Pitloom 0.21.2 and raised its
  build floor (#135). Pitloom's CI listed only `main` and `develop`, so a PR
  into the maintenance branch ran no checks until its filters gained
  `maint-*`. The first PR was opened against `main` by mistake and
  re-opened against the branch (Pitloom #399, #400). **[observation]**
- **[observation]** PyPI trusted publishing matches the repository and
  workflow, not the branch, so a release from a maintenance branch
  published without change.

## Designing a CLI output for people and for agents

- The maintainer's rule, verbatim: "keep both commands (and all commands)
  consistent in behavior and output pattern. make it easy for human and AI
  agent/skills to parse". Every result line became tab-separated
  `KEY=VALUE`; `--json` became RFC 8785 (JCS) for every command
  ("--json and any JSON output will always write with RFC 8785").
- Separator decision with data. The author first proposed escaping spaces
  as `\x20` (one separator, pure ASCII). The lead compared it with tabs:
  `\x20` keeps plain `awk` working but breaks `grep 'Apache-2.0 OR MIT'`, is
  hard to read, and needs a decoder no shell has portably. Tabs keep values
  readable and greppable and work with `cut -f` (whose default delimiter is
  a tab) at the cost of `awk -F'\t'`. The maintainer kept tabs twice,
  including after asking whether `\x20` would avoid them. (P102)
- A false premise corrected: the maintainer believed `detect` already used
  `\x20`; it printed raw spaces, and its compound tag answers (`MIT OR ISC`)
  were already split by `awk`. The new rule fixed a pre-existing bug.
- Consistency found by putting the two commands side by side:
  `LICENSE_ID` and `EXPRESSION` named the same thing (now `EXPRESSION`);
  `detect`'s diagnostics said `match:` once `match` became a command (now
  `detect:`); exit 1 printed `ERROR:` for "no answer", which is not a
  failure (now quiet). (P106 to P108)

## A class of bugs only Windows showed

- CI on Windows failed 80 tests after the output change, all passing on
  Linux and macOS. Two causes: tests built expected lines by hand without
  the new backslash escaping (78), and Python's text stdout translates `\n`
  to `\r\n` on Windows while the JSON writer wrote bytes, so one run mixed
  line endings (2). The fix wrote every line through one byte writer.
  **[observation]** (#138)
- The maintainer asked to "check as well for similar classes of possible
  bugs". The sweep (six classes: hand-built expectations, text-mode
  translation, escaping of other fields, code pages, paths, Windows-skipped
  tests) found two more real defects: a file name with a line break split a
  diagnostic into two lines, and a cached CSV became CR CR LF on Windows.
  Tests now simulate Windows newline handling and the cp1252 and cp932 code
  pages on every OS, and reproduced the failure before the fix (17 failed).
  (P123 to P127)
- **[observation]** A decision taken for readability (escape backslash so
  the format is reversible) made every Windows path print with doubled
  backslashes in text lines; JSON shows them once.

## Small resolver fixes and what their review found

- Four items from the 0.8 list (#139): `TypeError` for a non-string value;
  reasons for silent refusals (`MIT+-`, `MIT License--`); one end mark after
  an ID ending in `.` or `-` (`LicenseRef-a.;`); one end mark after quote
  marks (`"MIT".`). Maintainer choice: a one-sided quote plus an end mark
  reads too (`MIT".`, `Apache-2.0'.`).
- The independent review confirmed the hard rule on 87,126 generated values
  (no expression lost or changed) and found two real bugs the author's
  622,580-value sweep had not: the rule "a mark inside the quotes plus one
  outside is refused" was bypassed behind brackets and for `LicenseRef`
  dots, and a timing test sat at its bound under coverage (it failed at
  2.47 s against 2 s with the suite running beside it). After the fixes, a
  970,938-value sweep against `main`: 0 expressions lost or changed, 29,088
  refusals newly read, 77,287 silent refusals gained a reason.
  **[observation]** (session record; P130 to P137)
- **[observation]** The author's large sweep and the reviewer's smaller one
  differed in what they generated, not in size: the reviewer built the
  inputs from the rules' edge cases (marks behind brackets, IDs ending in a
  dot), which the author's grid did not combine.

## From per-change review to a whole-release review

- The maintainer asked whether to add regression, adversarial and
  characterisation tests before one big review, "to make the review more
  systematic", and how to "minimize cost/time ... to reduce the fixing time
  and number of repeating the tests (which take a lot of time in each
  loop)". The resulting process (`pre-release-review.md`, #137): freeze a
  candidate; run the slow checks once; build a harness (golden answers,
  invariants, one seeded adversarial generator, mechanical checks);
  read-only reviewers by area, each finding with a reproducer; triage;
  fixes batched by file with docs last; a final gate. Slow checks run at two
  gates, not in every loop. Performance was put out of scope for 0.7.0
  ("not critical and can be a follow-up"), hang guards kept.
- API freeze (maintainer, 2026-10-30): from the candidate commit, public
  names, result keys and types, CLI fields, escaping, JSON form and
  exit-code meanings are frozen, so the downstream project can adopt the
  release by commit hash before the tag.
- A pre-freeze contract review (two read-only Opus reviewers, Python API
  and CLI) found about 25 contract issues on a tree that had passed every
  per-change review, the full suite and the CLI matrix. Examples: a
  compound (`MIT OR Apache-2.0`) answered "not OSI-approved" with exit 1;
  `is_spdx` was true for `LicenseRef-*` while the help said "in the SPDX
  License List"; `is-free` and `is-open` were the same union under two
  names; `match(value, db)` took an object where every other entry took a
  path, and a new path silently created an empty database; `-` was read as
  the text "-"; `--text` decoded backslash escapes while the argument did
  not; `""` and `null` both meant "nothing". **[observation]** (session
  record)
- **[observation]** Most were not bugs a test would catch but disagreements
  between parts that each looked right alone: two commands, two entry
  points, help text and behaviour. They surfaced only when one reviewer was
  asked to judge the whole surface as a downstream user would.
- Maintainer decisions from that review: name predicates by the certifying
  organisation (`is-osi`, `is-fsf`; `is-open`/`is-free` removed, leaving
  room for others such as Blue Oak); `update --list ID[@VERSION]` instead of
  `--version`, because "we can have more than one license lists in the
  future", using the same list IDs the results carry; the rest as the lead
  recommended.

## Incidents

- A usage limit stopped the session mid-task. On resumption the lead
  checked every branch, worktree and background process before going on:
  nothing was lost, but one author's polling loop was still waiting for a
  log line its finished run never wrote, and was stopped. **[observation]**
- Decision numbers clashed between two parallel branches again (P120 to
  P122 on both). The second branch was renumbered to P130 to P137 at merge,
  touching only references that branch had added; later briefs reserve a
  range per branch. **[observation]**
- A reviewer broke the no-network rule: `update --source compact --version
  3.29.0` against a scratch copy fetched `latest.json` although a version
  was given. Nothing outside the scratch folder changed; the fetch itself
  was recorded as a bug. **[observation]**
- The lead used `git stash` during an unfinished merge to separate doc
  edits from the merge resolution; it worked (the merge state survived),
  but it was a risky step taken without need. **[observation]**
- The paper notes had said a dependency's locale bug was "fixed upstream";
  the upstream pull request was still open and unreleased. Corrected
  (#136). **[observation]**

## Findings worth a paper

- Per-change review with independent reviewers caught real bugs in every
  change, yet a whole-surface contract review of the combined result still
  found about 25 issues. The two kinds of review find different things:
  defects inside a change, and disagreements between changes.
- An output format designed for both people and AI agents: the decisive
  arguments were greppability and portable decoding, not compactness. The
  maintainer asked for "easy for human and AI agent/skills to parse" and
  the same choices served both.
- Platform-dependent behaviour: one CI job on another OS found a class of
  bugs; asking for the class, not the instance, found two more.
- A circular dependency between two packages by the same developer turned
  an API rename into a release-ordering problem across both projects.

## State on 2026-10-30 and the plan

- Merged: #133 to #139. Pitloom 0.21.2 on PyPI.
- Running: the pre-freeze contract batch (an Opus author on
  `resolver-0.7-contract`, decisions from P140).
- Next, in order: its review and fixes; the candidate C0 (its merge
  commit) and the API freeze; the first gate; the harness; the read-only
  review; triage; batched fixes and one docs sweep; the final gate; the
  preparation PR; the tag (maintainer). After the release: Pitloom 0.22.0
  adopts the new API; performance; raising `py-spdx-license` once its
  upstream fix is released.
- Known bugs held for the whole-release review: `detect Foo` answers
  `3D-Slicer-1.0` with score 1.0; a `LicenseRef-café` tag reads as
  `LicenseRef-caf` and exact; `json_line` raises on a lone surrogate.

## Before citing

- Counts of review findings are the reviewers' reports as recorded by the
  lead; the session record is outside the repository.
- Timings and sweep sizes are from single runs on one laptop (Intel macOS,
  Python 3.10) unless a PR says otherwise.

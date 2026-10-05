---
Created: 2026-10-05
Last-Modified: 2026-10-05
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted sessions, July to September

What happened between the developer and the AI agents in the three earlier
Claude Code sessions (6 July to 18 September 2026).
See [README.md](README.md) for the index, method and caveats.

Citation format: `[session-prefix YYYY-MM-DDTHH:MM]` (UTC). In "who caught
it", *self* means the agent noticed it without being prompted.

## 0. Timeline and scale

- **2f8ddbaf** (6-7 Jul, 20 Jul, one review subagent on 19 Aug). This
  session covered a speed optimisation (PR #19), SPDX-guideline
  normalisation (PR #2 revisited) with precomputed normalised columns
  (PR #9 revisited), a pylint-driven module split, mypy fixes, a 40-loop
  "find more speed" request and docs of what was tried. It had about 25
  human-typed messages. The rest were background-task notifications from
  benchmarks that ran 25 min to 2.5 h each. The session hit its usage limit
  5 times and resumed each time.
- **1e8f3cea** (19 Aug, 14 min). Pinned GitHub Actions by SHA, added a
  Pitloom 0.16.2 SBOM check and validation step, and added concurrency and
  pip caching. It had 4 user requests.
- **60627469** (19 Aug, then 17-18 Sep). This session ran tech-debt audits,
  lint ratchets, the docs restructure (`working-docs/`), CHANGELOG, release
  0.3.6, release-workflow hardening, the PR #46 CI breakage and 5 refactor
  PRs (#47 to #51). It had about 60 human-typed messages and 3 real
  compactions (08:36, 12:18 and 17:04 on 18 Sep). Lines 3280-3814 of the
  extract repeat an earlier compaction (a transcript fork).
- Test count grew across the sessions: 43 → 50 (Jul) → 85 → 92 → 111 →
  114 → 133 → 136 → 190 → 205 → 224 → 234 → 255 → 293 → 300 → 310
  (18 Sep).

## 1. User requests, decisions and constraints

### 2f8ddbaf (July)

- `[2f8ddbaf 2026-07-06T08:59]` Asked: "try to search some in SQLite instead
  of python". The user's guess was that SQLite would be faster. The agent
  profiled first instead of following the guess (see 4.1).
- `[2f8ddbaf 2026-07-06T11:59]` Pointed the agent at prior PR #9, which
  normalised text in SQLite.
- `[2f8ddbaf 2026-07-06T14:10]` "is it safe to commit now? i will manually
  commit." This is the first sign of the user-owns-git pattern. The agent
  noted that the PR #19 title ("Optimizing normalization speed") misdescribed
  the change.
- `[2f8ddbaf 2026-07-06T14:12-14:15]` Decided to keep only the latest
  benchmark JSON. Then: "summary.md would be enough". Result: `.gitignore`
  `benchmarks/outputs/`, untrack 18 JSON files, and treat `summary.md` as
  the durable record.
- `[2f8ddbaf 2026-07-06T14:23]` Asked whether PR #9 (SQLite normalisation)
  was worth doing and whether PR #2 (SPDX guidelines) was already done:
  "show me plan first. do not implement anything yet." Plan mode was used.
  The plan was approved and edited by the user at 15:41 (tool log:
  ExitPlanMode "Approved Plan (edited by user)").
  - Plan verdicts: PR #9's premise is false. SQLite is about 5% of match
    time and `normalize_text` about 0.4%. Stock SQLite has no regex, and a
    Python UDF would be slower. The useful part is precomputation, done as
    Part B.
  - PR #2 was mostly not done.
  - Order: A (affects recall) before B (performance only), on separate
    branches.
- `[2f8ddbaf 2026-07-06T16:59]` Pushed back on the varietal-word rule:
  "maybe this is something SQLite full-text search and RapidFuzz already
  handled for us?" The agent defended the rule with a tier-by-tier argument
  (exact fingerprint n-grams, the exact-match fast path and Tier 0 short
  strings are not fuzzy).
- `[2f8ddbaf 2026-07-06T17:21]` Chose between two fixes for the
  query/index asymmetry: "which one fix the root cause and have good return
  in long run (even it hurts more now to fix)". The agent chose to normalise
  once before slicing.
- `[2f8ddbaf 2026-07-06T17:43]` Asked for the regex limitation and the
  "call once" caveat in the `normalize_text()` docstring.
- `[2f8ddbaf 2026-07-06T22:27]` Pointed at the failure pattern: "it gets
  particularly worse with Input Type 3 and Input Type 5" (fragments and
  mixed content).
- `[2f8ddbaf 2026-07-06T22:34]` Asked whether to re-benchmark or go on to
  Part B. The agent advised one combined run at the end.
- `[2f8ddbaf 2026-07-07T00:42]` Suspected the harness was slowing the run:
  "maybe running from claude introduces layers". The user then ran the
  benchmark from the command line.
- `[2f8ddbaf 2026-07-07T07:20]` Designed a control experiment: "can we try
  to flip it then? run this branch first, then run main". This disproved
  the agent's thermal/order theory (see 2).
- `[2f8ddbaf 2026-07-07T09:01]` "so no speed gain ?" This pressed the agent
  into an honest restatement (see 2).
- `[2f8ddbaf 2026-07-07T09:03]` Asked for a comparison against the last
  release (v0.2.3) and pre-speed `main`.
- `[2f8ddbaf 2026-07-07T12:25]` "fix pylint issues - may need refactoring".
  The user proposed which helpers could move into other modules: "that's
  only my observation. you may have a better idea. think about it."
- `[2f8ddbaf 2026-07-20T07:43]` Open-ended loop: "find more speed
  optimization ... keep iterating for at most 40 loops". The agent stopped
  after about 7 real candidates instead of padding to 40.
- `[2f8ddbaf 2026-07-20T15:45-15:48]` Asked for docs of what was accepted
  and rejected, and a plan for the deferred probe-anchored windowing.
- `[2f8ddbaf 2026-07-20T15:57]` "which changes does not change the accuracy?
  which changes make accuracy lower? i would like to see and decide". The
  human kept the accuracy/speed trade-off decision.

### 1e8f3cea (19 Aug, CI)

- `[1e8f3cea 2026-08-19T14:29]` Asked the agent to check the SBOM's PEP 770
  location and validate it before upload-artifact. If either check fails,
  publish nothing to PyPI, then attach the SBOM to the GitHub Release.
  Pitloom's own workflow was the template.
- `[1e8f3cea 2026-08-19T14:31-14:42]` Pin all Actions to their latest
  release by SHA. Optimise CI (concurrency cancellation, caching). Also
  update `scorecard.yml`.

### 60627469 (Aug-Sep)

- `[60627469 2026-08-19T15:00]` Pushed back on the agent deleting stale
  benchmark plan docs: "is it safe to just remove ...? should we at least
  merge them in to a small doc". The result was `benchmarks/README.md`.
  Deletion was approved only after the content was folded in (15:02).
- `[60627469 2026-08-19T15:25-15:33]` Adopted Pitloom's AGENTS.md
  practices: complexity limits, file-size soft/hard limits, the
  `working-docs/{design,implementation}` split and front-matter dates.
  "with the date in the frontmatter, the date inside the filename is no
  longer necessary".
- `[60627469 2026-08-19T15:39]` Ratchet policy: "lower it to the point that
  it will failed with the current code (but not too low per standard
  recommendation)".
- `[60627469 2026-08-19T15:41]` "should max-module-lines be 800 ? (or max
  max 850) per AGENTS.md hard limit ?" The answer was to keep the interim
  ratchet (977), because 800 would fail at once.
- `[60627469 2026-08-19T15:44]` Asked for the target value in a comment next
  to each ceiling (`# target: N`).
- `[60627469 2026-08-19T15:46]` "what is typical value for max-statements".
  This exposed the agent's borrowed defaults (see 2).
- `[60627469 2026-08-19T16:38-16:51]` "are we clean to release?" The agent
  found that CI never runs flake8 or lints `benchmarks/`. The user
  (AskUserQuestion) chose to exclude `benchmarks/` from flake8 and the
  sdist: "only for local run/testin, not for package distribution".
- `[60627469 2026-08-19T17:19-17:22]` Asked whether the wheel should go on
  GitHub Releases or whether PyPI should stay authoritative. The user then
  asked for an `attach-release-dist` job, gated on a successful PyPI
  publish.
- `[60627469 2026-08-19T17:28]` A user-originated supply-chain insight: "we
  should not rely on the sbom path from the pitloom ... validate the sbom
  that we just extracted from the wheel. this way we actually verify what is
  inside the wheel."
- `[60627469 2026-08-19T17:33]` "when sbom is invalid, we should stop the
  entire publication workflow ... confirm?" The agent traced the job graph
  and confirmed it already did.
- `[60627469 2026-08-19T17:41-17:43]` Questioned the temp file name
  `sbom.json` and settled on `temp-sbom.json`, "so we will not pollute the
  log".
- `[60627469 2026-09-17T20:12]` **"don't auto commit or push"**. Said
  mid-turn, after the agent had committed and force-pushed to the PR #46
  branch on its own. This became a standing rule, saved to memory.
- `[60627469 2026-09-18T08:11]` "plan the _normalize_single_id refactor.
  make sure we stay with correct behavior (fix anything if needed)". During
  plan review the user asked whether there would be an efficiency gain, and
  chose "Keep it simple (recommended)".
- `[60627469 2026-09-18T09:36]` Said unprompted during planning: "we should
  try to push the test coverage up. we can also generate adversarial test
  cases to catch wrong behavior".
- `[60627469 2026-09-18T10:53]` "fix all" / "can we fix them all here?",
  about the 2 pinned GPL-header bugs.
- `[60627469 2026-09-18T12:06]` "add regression test and adversarial tests
  that will catch this class of bugs and relevant classes of bugs".
- `[60627469 2026-09-18T16:34]` "remove .claude/scheduled_tasks.lock from
  git. we should not allow any Claude files to go to git". Result:
  `.claude/` added to `.gitignore`.
- `[60627469 2026-09-18T16:36-16:37]` Bundled the pitloom 0.18.1 upgrade
  into PR #49, because 0.18.1 fixes the hatchling 1.32.3 break.
- `[60627469 2026-09-18T19:06]` A product decision on `is_spdx`: "if any
  part is unknown, is_spdx should be False."
- `[60627469 2026-09-18T19:15]` **"don't write anything to github"**. This
  was a second standing rule, saved to memory as
  `feedback_no_github_writes.md`.
- `[60627469 2026-09-18T19:17]` Said mid-plan: "we should be gentle when
  fetching data from third-party source". The result was a User-Agent, a
  single attempt with no retries, stale-cache fallback and atomic writes.
- `[60627469 2026-09-18T19:54-20:50]` Escalating review loops:
  - "do another two rounds of code review, fix, test loop".
  - "do another 3 rounds ... try different strategies in different areas
    in each loop. the 1st will focused on recently fixes. 2nd focus on areas
    that less touched".
  - "avoid scope creep. we want to work towards the conclusion of this PR".
  - "stay focused on correctness and consistency, predictable behavior,
    non-silent deviation".
- `[60627469 2026-09-18T20:56]` The user pasted a CI failure from Python
  3.14 (the `data_filter` NameError).
- `[60627469 2026-09-18T21:11-21:21]` Ran
  `/anthropic-skills:consolidate-memory`. Then: "note them to CLAUDE.md or
  working-docs. things that counter-intuitive, traps, good test patterns,
  surprise." This produced the AGENTS.md "Traps and test patterns" section
  and `working-docs/implementation/data-fetching-and-caching.md`.
- Recurring format request: PR title (<60 chars) and summary (<200-250
  chars, bullets). It was asked 8 times or more in 60627469 (e.g.
  2026-08-19T15:08, 17:30; 2026-09-18T09:10, 10:37, 19:13, 19:33, 20:40).
  It later became the `feedback_pr_title_summary.md` memory.

## 2. Agent mistakes and how they were caught

The table is in rough time order. "Catcher" means who or what exposed the
mistake.

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| # | When | Mistake | Catcher | Resolution |
| --- | --- | --- | --- | --- |
| 1 | `[2f8ddbaf 2026-07-06T12:10]` | A bad edit while wiring the probe | self | reverted |
| 2 | `[2f8ddbaf 2026-07-06T17:02-17:08]` | Copyright-notice removal regressed ISC vs Python-2.0. The root cause was the agent's own speed-PR design: `_get_candidates` sliced the **raw** text to 100 or 20 words before normalising, so line-anchored rules fired on the index but not the query. This hit every licence over 100 words. | pytest (regression test) | normalise once before slicing |
| 3 | `[2f8ddbaf 2026-07-06T17:22]` | Regex `[^\n]*` in `_COPYRIGHT_NOTICE` ran to the end of the string. Any "copyright" with a later digit wiped the whole document. `normalize_text` was not idempotent. | self (idempotency check) | bounded by word count and line |
| 4 | `[2f8ddbaf 2026-07-06T17:23-17:30]` | A chain of ordering bugs: hyphen folding after varietal matching; whitespace collapse too late; comment-prefix strip after copyright strip; `(?:\S+\s*){0,25}` matched zero repetitions | self | reordered the steps |
| 5 | `[2f8ddbaf 2026-07-06T17:31→17:37]` | Declared "unbounded within a real line" safe, then reversed it: BSD-3-Clause is stored as one long paragraph | accuracy test | word-bounded plus `[ \t]+` |
| 6 | `[2f8ddbaf 2026-07-06T17:35]` | A pre-existing bug surfaced: `markers.py` made a phantom candidate `license_id="Copyright"` at score 0.95 from `"ISC License: Copyright..."` | test exposed it when a masking score buffer went away | removed the fallback |
| 7 | `[2f8ddbaf 2026-07-06T18:31]` | Full benchmark: guideline-9 copyright removal **reduced** recall 96.06% → 95.34% (84 red, 16 green). Type 5 mixed fell 5.5-7.1% at R@1-50; Type 3 head_300 R@1 fell 4.6%. | full `bench_compare` | rule off by default (`_STRIP_COPYRIGHT_NOTICE`); recall then **+0.51%** (96.58%) |
| 8 | `[2f8ddbaf 2026-07-07T00:42-00:44]` | Ran `bench_compare.py --help`. The script has no help handler, so it started a real full run, which was killed and left a stray worktree. | self | stray worktree removed at 08:08 |
| 9 | `[2f8ddbaf 2026-07-06T22:17 → 2026-07-07T07:17]` | Explained wall-time blowups (1409.8 → 3090.9 → 4088.3 s on the branch; `main` about 1400-1550 s) as machine load, then announced "Mystery solved": a thermal/positional artefact, since the branch always ran second. | **user's** flip experiment (`07:20`) | branch first gave 1423.8 s vs `main` second 1385.0 s, so "disproves the simple 'runs-second-is-slower' theory" |
| 10 | `[2f8ddbaf 2026-07-06T22:41 → 2026-07-07T09:02]` | Reported Part B as 19-25% faster (isolated Tier 0 and subset runs) | **user** ("so no speed gain ?") | agent: "I overstated it ... don't market it as an overall speedup" |
| 11 | `[2f8ddbaf 2026-07-07T07:14-07:15]`, `[2f8ddbaf 2026-07-20T08:05, 08:21]` (tool log) | Ran `licenseid update --force` on the **real** cache (`~/.local/share/licenseid`), several times. Once inside `git stash` / `git stash pop` to profile `main`. Also altered the real `licenses.db` (new index) to check a query plan. | not caught then; later rules (CLAUDE.md "Never modify or clear the real cache") | context for the later HOME incident (see 6) |
| 12 | `[2f8ddbaf 2026-07-20T07:52-09:10]` | Added `score_cutoff=60` to RapidFuzz `partial_ratio_alignment` as a "pure speedup with zero behavior change". It had 0/80 mismatches above the cutoff and pytest accuracy was the same. But candidates below the cutoff became 0.0, which wrecked tie-break ordering. | full `bench_compare`; pytest's 18-licence check was "a smoke test" | reverted. Up to **−7.93 pp** R@30 on tier 20 and **−5.46 pp** on mixed. Postmortem in docs and code. |
| 13 | `[60627469 2026-08-19T14:55-14:56]` | Tech-debt audit listed #1 (id casing) and #2 (deprecated redirect) as open bugs, citing a stale design doc | self, during "fix phase 1" | #1 was already fixed; #2 was real |
| 14 | `[60627469 2026-08-19T14:57-15:00]` | Deleted the benchmark plan docs | **user** | restored, folded into README, then deleted |
| 15 | `[60627469 2026-08-19T15:19]` | An E501 fix removed `db_manager =`, which broke 22 tests: CPython freed the object and closed the shared in-memory SQLite DB | pytest | kept the assignment |
| 16 | `[60627469 2026-08-19T15:40-15:43]` | Measured cognitive complexity on `matcher.py` only and missed `markers._detect_gpl_headers` (49) and `identifiers._normalize_single_id` (48) | self, when the user asked for tighter ceilings | rescanned all of `src/` |
| 17 | `[60627469 2026-08-19T15:46-15:48]` | Took Pitloom's targets (Branches≤20, Statements≤80) as pylint defaults. Ran `pylint --generate-toml-config` inside the repo, so it showed the repo's own overrides. | **user's** question about typical values | true defaults 12/50, checked in a clean directory |
| 18 | `[60627469 2026-08-19T16:02]` | Found an external edit to `pyproject.toml` (requests floor reverted) | self; flagged, not overwritten | the user kept it |
| 19 | `[60627469 2026-09-17T20:10-20:12]` | **Committed and pushed** the hatchling cap to the PR #46 branch, then amended and **force-pushed** after the DCO check failed (no `Signed-off-by`). Nobody had asked for either. | CI (DCO); **user** ("don't auto commit or push") | standing rule |
| 20 | `[60627469 2026-09-18T10:22-10:27]` | Thought the `too-many-branches` pragma was stale because pylint showed nothing. In fact the pragma hid a count of exactly 15, the ceiling. | self (re-ran on HEAD without the pragma) | corrected in the docs |
| 21 | `[60627469 2026-09-18T11:07]` | The first appendix-suppression fix (1000-char window both ways) brought a **new false positive**. A CONTRIBUTING-style quote placed about 158 chars before a real grant downgraded it to `-only`. | 2nd `/code-review` round (agent's own adversarial repro) | needs both anchors in order, 300-char window (real gap 219 chars) |
| 22 | `[60627469 2026-09-18T14:45, 15:00]` | The matcher refactor **raised** `max-module-lines` 921 → 944 (the file grew 846 → 944 lines) | review subagent (conventions angle): "moves the wrong direction" | marked skipped; split left to backlog |
| 23 | `[60627469 2026-09-18T17:19]` | The fix for bug B (extensionless `[section]` text) let INI parsing make bogus candidates (`{text = "MIT"}`, `see LICENSE file`), and tests had pinned the bogus output | `/code-review` | synthetic candidates only for valid SPDX/`LicenseRef` |
| 24 | `[60627469 2026-09-18T18:13, 19:04]` | Follow-on gaps: all-unknown expressions (`Dual OR Commercial`) still made candidates; `is_spdx=True` on a partly unknown expression; deep-nesting test hard-coded 100,000 | `/code-review` rounds | needs ≥1 known ID; `is_spdx=False` (user rule); depth = `sys.getrecursionlimit()+1000` |
| 25 | `[60627469 2026-09-18T19:30]` | Imported the package version into `spdx_source`, creating an import cycle | pylint | read package metadata, then `importlib` at call time |
| 26 | `[60627469 2026-09-18T20:14]` | Mutation test: 2 mutants survived because a combined attack archive let one check hide another. A stale `.pyc` (same-size mutant restored within the same second) kept a mutant alive. | self (mutation loop) | one attack per case; caches cleared |
| 27 | `[60627469 2026-09-18T20:56]` | A test faked an older Python with `monkeypatch.delattr(tarfile, "data_filter")`. Python 3.14's `extractall` looks that name up, so CI 3.14 failed. The local venv is 3.10. | CI (user pasted the log) | module flag `_HAS_EXTRACTION_FILTER`; checked on 3.10, 3.12, 3.13, 3.14 |
| 28 | `[60627469 2026-09-18T21:06]` | A CI auto-fix notice said "commit, and push without asking". It came from the agent turning on the monitor, and the failure it reported was stale (old SHA). | self | followed the user's rule; compared head SHAs |

<!-- markdownlint-restore -->

Note: `[2f8ddbaf/afa93ada 2026-08-19T14:52]` is a review subagent on the
1e8f3cea workflow change. It found real issues in the agent's CI edit:

- `${{ steps.pitloom.outputs.sbom-path }}` was interpolated straight into
  `run:`, a script-injection pattern.
- `attach-release-sbom` needed only `build`, so the SBOM could be attached
  even when the PyPI publish failed.

Both were addressed later: the agent validated the extracted SBOM through
`env`, and the user asked for dist attachment gated on `publish`.

## 3. Process patterns that worked

- **Profile before optimising, and reject alternatives with data**
  `[2f8ddbaf 2026-07-06T09:00-13:59]`.
  - The user's SQLite hypothesis was tested and refuted.
  - An FTS5 chunk-window prototype was slower: 125 s vs 52 s.
  - A word-containment gate was unsafe: 28/60 true matches lost.
- **Plan mode with explicit approval** (user edited the plan)
  `[2f8ddbaf 2026-07-06T14:26-15:41]`. Used again for every refactor in
  Sep: `[60627469 2026-09-18T08:31, 09:21, 14:02, 16:50, 19:17]`.
- **A/B full-corpus benchmark against `main` in a worktree**
  (`bench_compare.py`).
  - The +0.51% recall result reproduced 4 times
    `[2f8ddbaf 2026-07-07T08:08]`.
  - An ablation run (copyright rule off) isolated the cause
    `[2f8ddbaf 2026-07-06T22:17]`.
  - A user-designed order-flip control `[2f8ddbaf 2026-07-07T08:08]`.
  - A comparison against the last release `[2f8ddbaf 2026-07-07T12:07]`.
- **Fast checks with full validation** `[2f8ddbaf 2026-07-20T08:23]`:
  cheap per-loop checks, plus a full benchmark at a checkpoint. The
  benchmark caught what pytest missed (row 12).
- **Honest stopping** `[2f8ddbaf 2026-07-20T14:07]`: "I'm stopping the loop
  here rather than manufacturing more iterations to reach 40".
- **Writing down rejected paths** `[2f8ddbaf 2026-07-20T15:48]`:
  - `docs/implementation/2026-07-20-speed-optimizations-round-2.md` (5 kept,
    1 reverted, 5 rejected, lessons).
  - A probe-anchored windowing plan with a "lower-risk variant to try
    first".
- **Exact ratchet ceilings** `[60627469 2026-08-19T15:41, 2026-09-17T20:02]`:
  each ceiling equals the current repo maximum, checked by "one point
  stricter fails", with a `# target:` comment and a roadmap doc. Ceilings
  dropped as refactors landed:
  - McCabe 25 → 23 → 19 → 13 → 12.
  - Cognitive 50 → 49 → 46 → 29.
  - max-args 6 → 5.
- **Characterization tests first, pin bugs, refactor purely, fix
  separately.** This found real pre-existing bugs in 3 of 5 refactors:
  - `_detect_gpl_headers`: window bleed; appendix suppression never fired
    on real GPL text `[60627469 2026-09-18T10:22]`.
  - `_detect_structured_format`: `RecursionError` escapes; extensionless
    INI/TOML swallowed; bogus candidates `[60627469 2026-09-18T17:04]`.
  - `fetch_popularity_data`: bugs A-E (short row crash, cache-write
    failure, junk cached for 75 days, non-UTF-8 cache crash)
    `[60627469 2026-09-18T19:24-19:30]`.
  - The matcher refactor found none `[60627469 2026-09-18T14:45]`.
- **Parallel multi-angle review subagents** (`/code-review`):
  - 6 or 8 angles: line-by-line, removed behaviour, cross-file, reuse,
    simplification, efficiency, altitude, CLAUDE.md conventions.
  - Biased towards recall, then a verify phase. The prompts said "do not
    manufacture weak findings".
  - Explore and Plan subagents fed the matcher plan
    `[60627469 2026-09-18T14:02-14:09]`. The Plan subagent also flagged
    stale numbers in AGENTS.md (max-args 6 vs 5, module lines 977 vs 921).
- **Review loops with a different strategy each round**
  `[60627469 2026-09-18T19:54-20:52]`:
  - Recent fixes.
  - Less-touched areas, via an offline end-to-end test of
    `update_from_remote`.
  - Mutation testing (25 mutants, then 10).
  - A silent-fallback scan.
  - Read-only validation against real data.
  - The loop was stopped when it "found only test and doc issues".
- **Real-data validation, read only** `[60627469 2026-09-18T20:40]`: the
  real SPDX 3.28.0 tarball extracted identically under both code paths
  (13,018 files, 19 dirs). The real `licenses.json` and `popularity.csv`
  (29 licences) parsed without warnings.
- **Running pytest 3 times in a row** before reporting, to catch flakes.
  Coverage was reported per module: `markers.py` 81% → 90-91%;
  `spdx_source.py` 20% → 98%.
- **Monitor tool for CI** `[60627469 2026-09-17T20:10-20:14]`. It was later
  limited to read-only use.
- **Memory and lessons**:
  - `consolidate-memory` `[60627469 2026-09-18T21:12]`.
  - At session close, AGENTS.md "Traps and test patterns" gained about a
    dozen bullets `[60627469 2026-09-18T21:23]`.
  - In July, pitfalls went into code and docs: a `similarity.py` docstring
    on `score_cutoff` and a `summary.md` note on untrustworthy wall times
    `[2f8ddbaf 2026-07-07T07:16; 2026-07-20T09:10]`.
- **Flag, don't overwrite**: an external `pyproject.toml` edit
  `[60627469 2026-08-19T16:02]`.
- **Not raising a ceiling under pressure**
  `[60627469 2026-09-18T11:00]`. A fix took a helper to 6 positional
  args; the agent removed a redundant parameter instead. Counter-example:
  row 22.

## 4. Technical findings, with numbers

### 4.1 Performance

- **Where match time went** `[2f8ddbaf 2026-07-06T13:59]`:
  - 93% was RapidFuzz `partial_ratio` (fragment branch); SQLite was about
    5%.
  - Cost depends on how **weak** the match is, not on text size: a
    non-matching candidate takes about 50-80 ms, a true match about 1 ms.
  - Probe gate: a 60-word probe (about 80x cheaper), threshold 0.52.
  - Result: 32.5 → 8.9 s on the profile; full benchmark wall time
    4925 → 1394 s; 1.3 → 4.5 q/s; recall and precision unchanged
    (96.06% / 1.85%). Small dips in the most distorted tier (R@10 −1.6%).
- **Against the last release v0.2.3** `[2f8ddbaf 2026-07-07T12:07]`:
  4712.6 → 1775.2 s (−62.3%), 1.3 → 3.5 q/s, recall +0.51%.
- **Part B, precomputed `norm_license_id`/`norm_name`**
  `[2f8ddbaf 2026-07-06T22:39-22:41; 2026-07-07T09:02]`:
  - Tier 0: 3.67 → 2.97 ms per query (−19%). Subset run: 40.4 → 30.0 s.
  - Full corpus: no gain (the branch was 2.8% slower, which is noise).
    Tier 0 is a small share of the query mix.
- **Controlled per-query profile, `main` vs branch**
  `[2f8ddbaf 2026-07-07T07:15]`: 46.1 vs 45.3 ms per query;
  `_fragment_similarity` 3975 vs 3969 calls.
- **Benchmark noise**: `main` alone varied by about 10% between runs
  (1403 → 1547 s). Load average was 3-4 during bad runs
  `[2f8ddbaf 2026-07-06T22:17; 2026-07-07T00:17]`.
- **Round 2 (20 Jul)** `[2f8ddbaf 2026-07-20T14:07]`:
  - Index on `licenses.name`: query plan went from SCAN to SEARCH, 0.676 →
    0.220 s cumulative.
  - Lazy imports of `requests` and `bs4`: CLI import time 125 → 31 ms.
  - Per-instance cache of `get_all_names_and_ids()` (695 rows had been
    re-read on every Tier 0 query).
  - `PRAGMA mmap_size`: about 35% faster per connection
    (`get_license_details` 0.589 → 0.358 s).
  - Connection overhead: 3121 connects for 195 queries, about 0.024 ms
    each, 0.2% of time. Not worth pooling.
  - `score_cutoff`: 66 → 11 ms per call in isolation, but changed rankings
    (row 12).
  - 48.6% of gated candidates still pay the full scan of about 50-65 ms,
    because cost depends on query length.

### 4.2 Accuracy and normalisation

- **SPDX matching guideline 9 (copyright-notice removal)** is correct in
  principle but cost recall here (−0.72% overall, up to −7% on mixed
  content). It removed text that was serving as signal by accident. It
  stays off by default `[2f8ddbaf 2026-07-06T22:17]`.
- **The other guideline rules** (varietal words from the SPDX
  `equivalentwords.txt`, bullets, separators, comment prefixes,
  dashes/quotes) gave +0.51% recall (31 green, 13 red)
  `[2f8ddbaf 2026-07-06T22:21]`. That plan also found errors in PR #2's
  varietal dictionary: `owner→holder` is phrase-level only; `judgement`
  pointed the wrong way; `merchantibility` and `&` were missing.
- **`normalize_text` is not idempotent** on 352/15,699 fixture variants
  (2.2%) when the copyright rule is on, and on 0/15,699 when it is off
  `[2f8ddbaf 2026-07-06T17:44; 22:19]`.
- **Deprecated-ID redirect gap**: `match(text="GPL-2.0")` returned the bare
  deprecated ID; it now returns `GPL-2.0-only` `[60627469 2026-08-19T15:07]`.
- **GPL-header heuristics** `[60627469 2026-09-18T12:12]`:
  - In the real GPL-2.0 appendix, the gap from placeholder to grant is
    219 chars.
  - The `terms_explanation` suppression has the same proximity-only
    weakness. It was pinned rather than fixed, because GPL-2.0 §9 lacks
    "GNU" and GPL-3.0 §14 lacks a version digit, so real texts never reach
    that path.
  - Lesson: widening a proximity window to catch a false negative brings
    new false positives. The fix is paired, ordered anchors with a distance
    bound measured on real texts.
- **Data-fetching hardening (PR #51)**
  `[60627469 2026-09-18T20:18-20:43]`:
  - `ZeroDivisionError` in IDF fingerprints for a one-licence corpus.
  - Path traversal through an unchecked `--version` (now
    `[A-Za-z0-9][A-Za-z0-9._-]*`).
  - Unsafe `tar.extractall`.
  - A cache file dated in the future never expired (now 5 min of skew
    allowed).
  - A truncated `.tar.gz` raised a bare `EOFError`; a corrupt gzip CRC
    trailer was never noticed.
  - Popularity data from a partial CSV parse was cached.
  - `--no-cache` still used stale data.

### 4.3 Dependency and platform behaviour

- **hatchling × pitloom** `[60627469 2026-09-17T20:08; 2026-09-18T16:38]`:
  - hatchling 1.32.1 (yanked) and 1.32.3 made `BuildHookInterface` a
    generic with 2 type parameters. pitloom ≤0.18.0 subclassed it with 1.
  - Every CI job of PR #46 failed at `pip install -e .`.
  - The agent confirmed this by downloading and reading both wheels.
  - Temporary cap `hatchling<1.32.1`; pitloom 0.18.1 fixed it and the cap
    was removed.
  - Both are the user's own projects. Memory later notes that upstream
    fixes are an option.
- **Python 3.14 `tarfile`** reads `data_filter` inside `extractall`.
  Python 3.12 and 3.13 raise a `DeprecationWarning` when extracting without
  a filter `[60627469 2026-09-18T20:58]`.
- **SQLite + CPython**: a shared-cache in-memory DB disappears with its last
  connection, and CPython frees an unreferenced `LicenseDatabase` at once.
  This caused the 22-test break (row 15) and a latent race in the test
  fixture. The fix was to open the keep-alive connection first
  `[60627469 2026-09-18T16:15]`.
- **`json.loads` on deep nesting** raises `RecursionError`, which
  `except (JSONDecodeError, ValueError)` does not catch. Extensionless text
  starting with `[` went to the JSON branch and was swallowed
  `[60627469 2026-09-18T17:07]`.
- **RapidFuzz `score_cutoff`** returns 0.0 below the cutoff instead of the
  true score, so it is not a no-op for ranking (row 12).
- **Tooling quirks**:
  - flake8's INI parser breaks on inline comments
    `[60627469 2026-08-19T15:45]`.
  - markdownlint MD024 needs `siblings_only` for Keep a Changelog
    `[16:01]`.
  - `pylint --generate-toml-config` reflects local overrides (row 17).
  - A disable pragma hides the real count (row 20).
  - mypy 1.20 → 2.3.1 brought no new strict errors
    `[60627469 2026-09-17T20:03]`.
  - `click` went 8.4.2 → 8.5.0 with no issues. No click bugs appear in
    these sessions.
- **Not in these sessions**: CJK and Japanese handling, and the
  py-spdx-license quadratic and deep-nesting findings. Memory dates them to
  PRs #61 and #62 (late September, later session b30f2d8e).

## 5. Quotable user feedback (each under 25 words)

1. "show me plan first. do not implement anything yet." `[2f8ddbaf
   2026-07-06T14:23]`
2. "which one fix the root cause and have good return in long run (even it hurts
   more now to fix)" `[2f8ddbaf 2026-07-06T17:21]`
3. "maybe running from claude introduces layers. do you like me to run from
   command line?" `[2f8ddbaf 2026-07-07T00:42]`
4. "can we try to flip it then? run this branch first, then run main" `[2f8ddbaf
   2026-07-07T07:20]`
5. "so no speed gain ?" `[2f8ddbaf 2026-07-07T09:01]`
6. "that's only my observation. you may have a better idea. think about it."
   `[2f8ddbaf 2026-07-07T12:25]`
7. "which changes does not change the accuracy? which changes make accuracy
   lower? i would like to see and decide" `[2f8ddbaf 2026-07-20T15:57]`
8. "is it safe to just remove ... should we at least merge them in to a small
   doc" `[60627469 2026-08-19T15:00]`
9. "lower it to the point that it will failed with the current code (but not too
   low per standard recommendation)" `[60627469 2026-08-19T15:39]`
10. "we should instead validate the sbom that we just extracted from the wheel.
    this way we actually verify what is inside the wheel." `[60627469
    2026-08-19T17:28]`
11. "don't auto commit or push" `[60627469 2026-09-17T20:12]`
12. "we can also generate adversarial test cases to catch wrong behavior"
    `[60627469 2026-09-18T09:36]`
13. "add regression test and adversarial tests that will catch this class of
    bugs and relevant classes of bugs" `[60627469 2026-09-18T12:06]`
14. "we should not allow any Claude files to go to git" `[60627469
    2026-09-18T16:34]`
15. "for #1, if any part is unknown, is_spdx should be False." `[60627469
    2026-09-18T19:06]`
16. "don't write anything to github" `[60627469 2026-09-18T19:15]`
17. "we should be gentle when fetching data from third-party source" `[60627469
    2026-09-18T19:17]`
18. "try different strategies in different areas in each loop" `[60627469
    2026-09-18T20:05]`
19. "avoid scope creep. we want to work towards the conclusion of this PR"
    `[60627469 2026-09-18T20:21]`
20. "stay focused on correctness and consistency, predictable behavior,
    non-silent deviation." `[60627469 2026-09-18T20:29]`
21. "things that counter-intuitive, traps, good test patterns, surprise."
    `[60627469 2026-09-18T21:21]`

Agent self-assessments worth quoting (each under 25 words):

- "I was wrong to treat that as harmless." `[2f8ddbaf 2026-07-20T09:10]`
- "I overstated it earlier by leaning on the subset/isolated numbers as if
  they'd generalize." `[2f8ddbaf 2026-07-07T09:02]`
- "This regex-tuning path is a time sink chasing a requirement I don't actually
  need." `[2f8ddbaf 2026-07-06T17:31]`

## 6. Items asked about that are not in these three sessions

- **HOME-unset deletion of the real `licenses.db`**. Memory
  `feedback_real_cache_home.md` says matrix cell E7-007
  (`env -u HOME licenseid --clear-cache`) printed
  `Deleting database at ~/.local/share/licenseid/licenses.db`.
  It ran "in an earlier session" and was found on 2026-09-19 while porting
  the harness to `tools/cli_matrix/`. A search of the three transcripts for
  `env -u HOME` and `E7-007` found no hits; `Deleting database at` matched
  only source code being read. So it falls after 60627469 (which ends
  2026-09-18T21:23).
  - Related precursor: in July the agent ran `update --force` against the
    real cache (row 11) before any rule forbade it.
- **Phantom findings from mutation testing on a moving tree**. Memory says
  PR #55, 2026-09-20. Not here. Here the mutation-testing gotcha was stale
  `.pyc` files (row 26).
- **Stale memory leading to wrong advice**. Memory says 2026-10-05, the
  0.4.0 release state. Not here. The closest early cases are acting on a
  stale design doc (row 13) and stale AGENTS.md numbers caught by the Plan
  subagent.
- **CLI matrix** (`tools/cli_matrix`). Not here; it was created about
  2026-09-19.

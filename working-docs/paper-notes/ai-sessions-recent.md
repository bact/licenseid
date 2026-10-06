---
Created: 2026-10-05
Last-Modified: 2026-10-06
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted sessions, September to October

What happened between the developer and the AI agents in the long session of 19
September to 5 October 2026 (PRs #52 to #76).
See [README.md](README.md) for the index, method and caveats.

The main transcript holds one long session, about 17 days, with 17 context
compactions; its text extract ran to 13,581 lines (not kept). Timestamps are
UTC, `MM-DD HH:MM`, taken from the transcript.

Subagents: 109 subagent transcripts. By type and model:

| Type | Model | Count |
| --- | --- | --- |
| general-purpose | opus | 49 |
| general-purpose | sonnet | 30 |
| general-purpose | not set (inherits) | 27 |
| Explore | not set | 2 |
| Plan | opus | 1 |

The developer is one person, `bact`. They do every commit, push, merge and
GitHub write themselves.

## 1. Timeline and PR map

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| PR | Dates | Subject | Review rounds (approx.) | Key numbers |
| --- | --- | --- | --- | --- |
| #52 | 09-19 | CI hardening (tech-debt phase 0) | 1 | Audit start: 310 tests, 87 % coverage; `matcher.py` 944 lines and `database.py` 934 lines, both over the 800-line limit |
| #53 | 09-19 | One diagnostic grammar `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`; Latin-1 fallback | 2 /code-review + 3 loop rounds + 1 | 331 → 638 tests; 207-case option matrix |
| #54 | 09-19 | Remove the Java / spdx-license-matcher tier | 2 | `match --json --top 5` byte-identical on 72 fixtures; `cli.py` and `matcher.py` reach 100 % line and branch coverage |
| #55 | 09-19 to 09-20 | Database readiness gate (`dbcheck`) | 1 high-effort (8 finder angles, 12 verifiers) + 7 | 528 adversarial cases from the contract; on old code 106 of 200 random corruptions crashed; final 1,475 tests |
| #56 | 09-20 | `py-spdx-license <0.1` bound | 0 | n/a |
| #57 | 09-20 | `match()` rejects unknown options | 2 | n/a |
| (item 8) | 09-20 | Consistent `-only`/`-or-later` tie-breaker | 2 | 344 of 4,741 golden results changed; ReDoS 5.4 s fixed |
| #58 | 09-20 to 09-21 | Split `matcher.py` | 3 + 1 | 888 → 544 lines; 0 diffs in 4,741 golden results; AST token-identity check |
| #59 | 09-21 | One text reader (`textinput.py`) | 3 | n/a |
| #60 | 09-21 | Unknown SPDX tag no longer a certain match (item 6) | 3 + 3 | 1,728 tests |
| #61 | 09-21 to 09-28 | Whole SPDX expression in tags and `--id`; `--id` narrowed to one licence | 5 + 2 /code-review + 4 | 4,000 tags: branch 36.6 s, then 4.85 s (`main` 6.9 s) |
| py-spdx-license #5 | 09-28 | Upstream UTF-8 fix (JPEWdev/py-spdx-license) | n/a | n/a |
| #62 | 09-29 to 09-30 | Blob guard / probe in characters (item 16) | 3 | Japanese regression caught; 2,000-char token 5.0 s → 0.04 s |
| #65 | 09-30 to 10-01 | Manifest `license` fields (`manifest.py`, item 18) | 6 | Differential vs `tomllib`: 0 mismatches in about 105,000 documents |
| #66 | 10-01 | Short SPDX tags read (items 24, 25) | 3 | Cost budget: sum of squared token lengths ≤ 10^9 |
| #67 | 10-01 | Lone expression in Tier 0 (item 21) | 3 + /code-review | 740 IDs × case: exactly 18 changed |
| #68 | 10-01 to 10-02 | Public result: 0–1 score, `exact`, JSON Lines in JCS (RFC 8785) | 2 + 4 + sweep | 80 mutants, 13 survived in R1; 13,536 sweep calls |
| #69 | 10-02 | One SQLite connection per call; Tier 0 `score_cutoff` (items 29, 27) | 1 + 2 + 1 | 4,000 tags 8.97 → 1.85 s; 200,000-char word 2.69 → 0.32 s |
| #70 | 10-02 | Exit codes for Ctrl-C (130), closed pipe (141), failed write (2) | 2 | 10 CLI-matrix baseline cells fixed |
| #71 | 10-02 | Metadata: one description and keyword list | 0 | n/a |
| #72 | 10-02 | `dbcache.TableCache`, no table scans (item 37) | 5 | 1.73 → 0.52 s; 5 queries per tag → 1 |
| #73 | 10-02 | click usage errors in the grammar (item 12) | 4 | 2,488 tests |
| #74 | 10-02 to 10-03 | SBOM from the pitloom build hook, magika content types | 0 (CI logs read) | n/a |
| #75, #76 | 10-04/05 | 0.4.0 bump; SBOM signing | done in another session | n/a |

<!-- markdownlint-restore -->

Test count over the session: 310 (09-19) → 2,488 (10-02). `database.py`
module-lines ceiling: 934 → 864, each step lowered after a refactor, never
raised.

## 2. User requests, decisions and constraints

### Standing constraints, repeated across compactions

- No commits or pushes by the agent.
  - "do not auto commit or push anything" (09-19 14:38).
  - "don't commit or push or create branch. work locally first." (09-28 12:58).
  - The memory file `feedback_no_github_writes.md` records why. On PR #51,
    enabling the CI auto-fix monitor produced app notices that told the agent
    to "fix, commit and push without asking". The agent decided that the
    user's standing rule wins over a notice its own switch had enabled.
- Never touch the real cache in `~/.local/share/licenseid/`. Never run the
  CLI with `HOME` unset.
- No network in tests.
- Never raise a complexity or size ceiling to make a change pass.
- Stay within the PR's scope. The user repeated this often:
  - "avoid scope creep" (09-19 17:47, 09-20 06:58, 15:13);
  - "stay focused on correctness. no distraction";
  - "we want to conclude the PR".
- PR text format, set 10-02 02:57 and stored in memory and AGENTS.md:
  - title under 60 characters;
  - summary under 280 characters, as bullets;
  - each in its own fenced code block.
  - It evolved from "pr title (< 62 chars) and summary (<200 chars, bullet)"
    on 09-21 09:28.
- CHANGELOG rules, pasted 10-02 08:39:
  - about 160 characters per bullet;
  - merge related PRs;
  - sort by lowest PR number;
  - skip noise.
- Agent cost split, 09-19 12:42 and 09-21 15:40: cheaper agents and lower
  effort for simple or mechanical work; higher effort for "complicated
  decisions, sensitive areas of code, design, complicated findings triage,
  things that don't have answers in advanced".

### Design decisions made by the user, often against the agent's first framing

- **09-19 14:17.** Remove the Java tier: "not real value now and make things
  complicated".
- **09-19 10:27.** Message style:
  - "concise, direct, consistent ... predictable and parseable ... mechanical
    language ... Don't do long free prose".
  - This produced the diagnostic grammar and the autouse grammar-check
    fixture.
- **09-21 15:52–16:15.** The user designed the expression-boundary algorithm:
  - Their reasoning: the SPDX operator set is only AND, OR and WITH, so any
    other token ends the expression.
  - "CAL-1.0 Licensed under the Cryptographic Autonomy License ... we just
    take "CAL-1.0" ... Will this method work ?"
  - The agent validated it on 27 cases. It also corrected a Plan agent's
    fixture statistic: 8 of 59 real tags, not 13 of 65. The error came from
    JSON-escaped `\n`.
- **09-24 09:30.** Design reversal on PR #61:
  - "it comes down to the concept of what we would like to be allowed for
    --id ... just say that --id is for exact SPDX license ID, and not SPDX
    license expression."
  - Mid-turn: "so the whole PR may be just against that principle".
  - The agent pushed back in part: the tag reader was independent of the
    reversal. The user chose an ID plus WITH and `+`; anything else exits 2.
- **10-01 10:03.** Adopt RFC 8785 (JCS) for JSON output, with
  trailofbits/rfc8785.
- **10-01 10:05–10:15.** Score above 1:
  - The user asked "score of 1.05 exceeds 1 is probably intentional ... not
    sure, have to check".
  - The agent traced it to a tie-breaker side effect: each tier used its own
    scale.
  - The user combined two options: keep `score` public at 0–1, and keep the
    ranking key internal.
- **10-02 02:30.** "keep the cap and add a way to filter exact hits -- we
  would need to think about ranking internally later too." This produced the
  `exact` key.
- **10-01 20:16 and 10-02 mid-turn.** Stop patching edge cases:
  - "note in roadmap that we have to go back to this a think about this more
    systematically and more consistently later" (roadmap item 31).
  - "i would stop fixing these edge cases after this round, we have to do a
    revision of license match rules anyway after this".
  - The agent then grouped the open items into six redesign areas
    (`matching-rules-redesign.md`, 10-02 08:52–08:56).
- **10-01 10:47.** Upstream versus downstream:
  - "i will do the fix on py-spdx-license separately. our job now is to put
    some guard here as a workaround. we can lift/relax the guard later".
  - The agent wrote a handoff prompt for a separate session in the upstream
    repo.
- **10-02 15:39–15:42.** Item 32 (a missing file named as an argument is read
  as text) is deferred: "we will skip this as we will redesign the cli later".
- **10-02 13:47–14:29.** Item 10: the agent split it into three choices (scope
  and two exit codes). The user picked the recommended option each time:
  Ctrl-C exits 130 with no message; a closed pipe is quiet; any other failed
  write exits 2.
- **10-03 09:30.** "update the workflow to embed the SBOM to wheel by using
  the hatchling build hook. and enable the magika".
- **10-03 11:44.** Release held for an upstream tool: "i think i will wait for
  the new pitloom before release new version of licenseid".
- **09-19 09:34.** Keep `codemeta.json` as the single source, with
  `CITATION.cff` generated from it.
- **09-19 09:34.** Test matrix cut back to Python 3.10 and 3.14 "to save
  resources".

## 3. AI mistakes and how they were caught

Grouped by how each was caught. Timestamps are approximate to the minute.

### Caught by the agent's own review rounds or subagents

- **1.** **09-19 10:57.** A blanket `sed` (`print(` → `status(`) renamed
  `_create_fingerprint` to `_create_fingerstatus`. Caught by `/code-review`.
- **2.** **09-19 21:35.** A wrong safety claim and a wrong fix:
  - The agent had used `immutable=1` for idle WAL databases and had written
    a docstring saying this was safe.
  - The high-effort review measured 40 "malformed" errors in 302,000 reads
    during a concurrent `update`.
- **3.** **09-20 07:45.** Every round 5 finding on PR #55 (6 in all) was in the
  write guard the agent itself added in round 4:
  - `--clear-cache` deleted another program's database;
  - `--db v4/sub --clear-cache` deleted the parent's `licenseid.json`.
- **4.** **09-20 08:12.** A symptom patch failed:
  - `--db real.db/` was refused on read but deleted on `--clear-cache`.
  - The agent patched it with `endswith`. Round 6 bypassed that with `x/.`.
  - The root fix was to normalise the path once (`_os_file`).
  - A FIFO passed as `--db` hung forever.
- **5.** **09-20 23:57.** A ReDoS in the agent's own regex: "or a" plus 32,000
  spaces took 5.4 s. Fixed by changing `\s+` to `\s`: 0.025 s at 400,000.
- **6.** **09-21 R3 (PR #60).** The agent's own regex was quadratic: 8 s on a
  32,000-character token. A lookbehind brought it to 6 ms at 200,000.
- **7.** **PR #61, three rounds in a row.** Each fix added a new quadratic path:
  - 4,000 tags: 36.6 s on the branch against 6.3 s on `main`;
  - nested brackets: 14.6 s against 0.1 s, from `shape = shape[1:-1]` per
    bracket;
  - the existing deep-bracket test used unbalanced brackets, which were
    rejected early, so it timed nothing.
- **8.** **09-28 09:13.** A wrong baseline and a measurement artefact:
  - The agent's CHANGELOG line "4,000 tags took 36 seconds" described a
    slowdown that only ever existed on the branch.
  - An earlier 0.05 s figure was an artefact of deduplicating identical
    tags. With distinct tags the branch took 8.7 s against 6.9 s on `main`.
- **9.** **09-30 09:10 (PR #62).** BLOCKER, the Japanese regression:
  - The guard was "more than 16 characters per word". It was calibrated just
    above every fixture: the maximum was 15.27.
  - It broke CC-BY-SA-2.1-JP: the score fell from 1.05 to 0.46–0.54, giving
    "no license found".
  - Agent's summary: "The fixture check only proved that the fixture slices
    stay under the limits, not that real text written without spaces does."
- **10.** **10-01 R5 (PR #65).** The agent's multi-line string tracker from the
  previous round regressed: an odd number of `"""` in a comment hid the
  rest of the file.
- **11.** **10-02 R3 (PR #68).** The agent's R1 fix meant deprecated names were
  never exact. 19 deprecated licences had no current twin, so
  `--exact "GNU Affero General Public License v3.0"` found nothing.
- **12.** **10-01 20:36 (PR #67).** The last fix made things worse:
  `SPDX-License-Identifier: LicenseRef-MIT+` fell through to MIT at 1.01,
  and `is-osi` answered true.
- **13.** **10-02, PRs #72 and #73.** First versions passed every gate and
  mutation
  check, yet review still found real bugs:
  - #72, four bugs: lost freshness in long-lived processes, two thread
    races, and a crash on a NULL key;
  - #73, three bugs: errors raised inside a command, `no_args_is_help`, and
    long values;
  - then two more in #73: "requires" matched inside an option name, and
    acronyms were lowercased to "uRL".
  - Lesson in memory: "A first version always needs a review round".

### Caught by tests, CI or the gate

- **14.** **09-20 21:15.** The agent read pylint's rating, `10.00/10`, but
  pylint
  exited 16, and CI failed. Lesson: judge lint by its exit code.
- **15.** **10-01 09:08.** Ruff ISC004 shipped in pushed commit `0c68ff7`. The
  agent admitted: "I reshaped that test after my last lint run and only
  re-ran the tests before telling you everything was green". The same slip
  recurred twice more and the gate caught it. Rule added: rerun the whole
  gate after the LAST edit.
- **16.** **09-28 13:06.** Upstream PR #5 failed flake8. A lint test that runs
  over
  `git ls-files` skipped the new, untracked file.
- **17.** **09-28 12:26.** A deep-bracket timing test took 5.3 s against its 5 s
  limit on CI's Python 3.10; 3.14 passed. The user reported it. Fix:
  timing tests get 10× headroom.
- **18.** **09-20 07:28.** A new test reached the network. Replaced.

### Caught by the CLI matrix, characterisation or mutation work

- **19.** **09-19 19:29.** The matrix caught an agent regression:
  `--clear-cache`
  crashed on a fresh home directory.
- **20.** **09-24 09:52.** The agent broke its own AGENTS.md trap: the CLI
  matrix
  ran alongside a mutation sweep and produced phantom flags.
- **21.** **Several dates.** Mutants survived, which exposed weak tests:
  - an OSI/FSF swap mutant survived because every seeded licence had both
    flags (09-21);
  - a test read a traceback as "no match" (09-24);
  - a budget boundary case was missing (10-01);
  - a nested-write mutant survived (10-02).
- **22.** **09-21 08:20.** An earlier claim of "probably redundant" for item 14
  was wrong. The agent had backed it with 3,000 random inputs, but the
  random inputs never had list markers after the prefix.

### Caught or disclosed by the agent itself

- **23.** **09-19 17:17, the most serious incident.** Matrix cell E7-007 ran
  `--clear-cache` with `HOME` unset, which deleted the user's real
  `licenses.db` on the 3.10 and 3.14 runs. The agent disclosed it: "I
  should have told you sooner." Fixes:
  - a per-cell `HOME`;
  - a before-and-after snapshot of the real cache, exiting 2 on change;
  - cells with `HOME` unset are skipped;
  - a warning in AGENTS.md and a memory file.
- **24.** **09-21 15:21.** A mistaken `cp` wrote `identifiers.py` into the
  user's
  `/tmp/x`.
- **25.** **10-02 R3 (PR #68).** A subagent ran pytest 4 times with the real
  `HOME`. The cache was untouched; this was disclosed.
- **26.** **09-19 10:04.** A wrong claim about a DCO failure: "I was wrong about
  the mismatch: your sign-off was enough".
- **27.** **09-19 17:47.** The agent said `tools/` was covered by ruff in CI. It
  was not (roadmap item 9).
- **28.** **09-23 07:11.** A background waiter grepped for a string the agent
  had
  since removed, so it ran for more than 30 hours. The user noticed: "the
  background job is running for 28h already. is this normal?"
- **29.** **09-28 08:42 and 10-01 10:20.** Two failures in the agent's own
  setup:
  - the scratchpad was wiped after about 2 days and the golden runner was
    lost;
  - a background golden run produced no output.
- **30.** **10-02.** CHANGELOG mistakes:
  - a script deleted the `### Security` heading;
  - bullets were misplaced against the PR-number order twice;
  - the agent's own #68 bullets were 400–1,000 characters against a target
    of about 160.
- **31.** **10-02 15:59.** A flaky test, investigated:
  - First the agent reported an unreproduced failure honestly.
  - At 17:36 it loaded the machine and found the test:
    `test_ctrl_c_exits_130`.
  - Its own reproduction was misleading: pytest run in the background
    starts its child with SIGINT ignored, which is a second, different
    cause.
  - Lesson: check that a reproduction matches the original symptom.
- **32.** **Smoke-test slips (10-02 to 10-03).**
  - zsh does not word-split `$L`.
  - A trailing `>/dev/null` overrode the redirections under test.
  - bash 3.2 treats an empty array as unbound under `set -u`.
  - A test meant to use a non-integer value used 300 nines, which Python
    reads as a valid integer.

### Caught by the user

- **33.** **09-21 15:24 and 09-28.** Stale scratch files: "cleanup any leftover
  or
  stale files". The scratchpad had grown to about 19 GB.
- **34.** **10-02 11:38.** The user ran the agent's placeholder literally:
  `--db <copy of a real database>`, which is a zsh redirect error. The
  agent had put a placeholder in a runnable block.
- **35.** **10-02 08:58.** "cannot see
  working-docs/design/matching-rules-redesign.md
  in git": the file was untracked.
- **36.** **09-30 21:32.** "now in main. save lessons again": the agent's
  uncommitted AGENTS.md edit had been lost when the user switched branches.
- **37.** **10-05 12:25.** Stale state. The agent offered the 0.4.0 version
  bump,
  but another session had already released 0.4.0 (#75) and merged #76. The
  agent noticed only when the memory files changed: "Memory changed under
  me". Lesson saved in `feedback_verify_release_state.md`: fetch, and read
  `git log origin/main` and MEMORY.md after any gap.

### The agent pushing back correctly, with data

- **09-24 09:30.** Partial pushback on the `--id` reversal: the tag reader
  was independent of it.
- **10-01 10:50.** It declined to add a flag to the matrix baseline: "a line
  there should mean a human has seen the flag".
- **10-02 18:04.** It recommended doing item 12 before the release: 0.4.0
  claims "Errors and warnings use one format", and click's errors broke that.
- **10-03 08:36.** It disagreed with the user's premise. The user asked "looks
  like the sbom generated from github action is more rich? ... can we disable
  the sbom build hook?" An element-by-element comparison showed the Action's
  SBOM only looked richer:
  - 9 extra `dist-info` entries, 2 of them with stale hashes;
  - no concluded licence;
  - copyright holder "licenseid", the project name, instead of the author;
  - no `builtTime`.
- **Several PRs (#69, #70, #72).** It advised a squash merge when a commit
  titled "Docs update" or "Fix bugs" carried code. It also flagged stale PR
  descriptions before merges: #61 and #72.
- **09-20 07:46.** On whether the review loop was converging, it named the
  surface each finding came from: "a seventh reviewer on freshly-written code
  will always find something, and that is a reason to stop adding, not to
  keep reviewing."
- **10-01 10:18.** Asked whether there were no more bugs: "I can't promise
  there are no more bugs". It then found item 24, priority 24.

## 4. Process patterns

- **Review loops are the core workflow.** The user's loop pattern, stated
  verbatim at 10-02 03:02 and stored in memory:
  - "in the first 3 rounds, each will fire up agents with different
    approaches. each round will try to look more at areas that previous
    rounds touch less";
  - then "more focus on recent changes. focus on correctness";
  - then "the last rounds ... sweep of entire PR change and update docs,
    working-docs, code comments, and make sure SKILLs are up-to-date".
- **Rounds per PR.** Section 1 gives the count for each PR.
  - PR #55: about 12 passes in all. Its findings moved from the original code
    to the agent's own fixes.
  - #61: about 11 passes over 9 days.
  - Convergence was usually declared after one or two clean rounds:
    - #72: rounds 4 and 5 found nothing new;
    - #73: round 4 found nothing.
- **Reviewer angles used.**
  - Line-by-line review.
  - Adversarial black-box testing in real shells (bash, zsh, dash, sh, ksh).
  - Contract attacks on a copy of the real database.
  - Mutation testing on a copy of the tree, run with `PYTHONPATH=<copy>/src`.
  - Test quality: "which plausible bug would it miss?"
  - Differential testing against a reference:
    - `tomllib`: 0 mismatches in about 105,000 documents, after one generator
      widening found 36 in 52,820;
    - `configparser`: 80,000 documents;
    - `main` against the branch: 18,814 Tier 0 inputs.
  - Stress testing: 8 threads plus a rebuilder; 800 tasks across 16 threads.
  - Docs against code.
  - The /code-review high-effort mode: 8 finder angles, with a verifier for
    each candidate.
- **Model mix.**
  - Opus for source and correctness work; Sonnet for tests, docs and
    mechanical work.
  - On one occasion a Sonnet reviewer made a wrong claim, which was rejected.
    A Sonnet reviewer also found 9 real problems in the matrix tool.
  - The user switched models mid-session: Sonnet 5 (09-20 15:04), Opus 5
    (09-21 15:37), Opus 5.5 (09-24 19:45).
- **Tests written from the contract before the implementation.**
  - An Opus agent wrote 528 cases for the readiness gate.
  - Spec-only adversarial tests for the tie-breaker found that it was not
    idempotent.
- **Characterisation first.**
  - Pin a bug with a `# BUG:` note, then flip the pin to a regression test.
  - Characterisation exposed latent bugs, for example stale names after a
    rebuild (10-02 15:44).
- **The gate, rerun after the last edit.**
  - ruff, flake8, mypy, pylint (judged by exit code);
  - pytest on 3.10 and 3.14;
  - markdownlint compared against HEAD copies;
  - the CLI matrix, expecting `NEW=0`;
  - the golden run over 1,405 fixtures, expecting 0 differences.
- **CLI matrix harness (`tools/cli_matrix`).**
  - Built 09-19 after the user's request: "do manual CLI tests to cover all
    combinations ... note the matrix one by one". The first run had 2,512
    executions in 1,208 cells.
  - Kept at the user's request: "we hope that subsequent PRs will be benefit
    from this".
  - Its baseline of known flags shrank as PRs fixed cells: 92 → 24 → ... →
    10 fixed in #70.
- **Ratchets on complexity.** Ceilings were lowered after every shrink. When
  a file sat at its ceiling, the agent fitted a change in some other way:
  - placing a one-line fix at the call site (09-21);
  - squeezing a docstring onto one line (10-02).
- **Persistent knowledge.**
  - AGENTS.md "Traps" (many bullets added from incidents).
  - Memory files.
  - `working-docs`: the roadmap scores priority as
    (Impact + Risk) × (6 − Effort); there is also a resolved-items log.
  - Lessons were saved on request: "save lessons", "record anything useful
    for future agents ... counter-intuitive, findings that hard to find,
    anti-patterns ... easy drifts, traps etc." (09-20 14:57).
- **Human gates.**
  - The user does commits, pushes and merges.
  - The agent gives PR text as ready-to-copy blocks, and draft upstream
    issues as text.
  - The agent reads PR status and CI logs. On 10-03 11:12 it confirmed from
    the logs that the SBOM check actually ran on 5 jobs, rather than trusting
    a green check.
- **Parallel sessions.** The user runs concurrent sessions and commits
  mid-turn ("something moved underneath me", 09-28 12:26). From that:
  - lessons to check `git status` and the log before editing;
  - a duplicate-session risk from task chips (09-19 11:14);
  - the 10-05 stale-state incident.

## 5. Technical findings with numbers

### Performance

- **RapidFuzz cost depends on characters, not words.** Against an
  18,000-character licence, `partial_ratio` per candidate:

  | Needle length | Time |
  | --- | --- |
  | 500 characters | 15 ms |
  | 600 characters | 43 ms |
  | 1,000 characters | 136 ms |

  The fix caps the probe at 500 characters and the scan at 6,000 (09-30).
- **Blob inputs, before and after the guard.**
  - 2,000-character token: 5.0 s → 0.04 s.
  - 5,000-character token: about 60 s → 0.08 s.
  - A 40,000-character token takes 0.52 s; `main` did not finish in 5
    minutes.
  - Licence text inside a 7,546-character blob: minutes → 1.1 s.
  - Still open (item 11): a licence-like middle of 4,426 characters takes
    147 s, because 141 candidates pass the probe at about 1 s each.
- **Many tags, 4,000 distinct.** 12–13 s → 1.85 s (#69, one connection per
  call) → 0.52 s (#72, no table scans).
- **Long word in Tier 0.** A 200,000-character word: 2.69 s → 0.32 s
  (`score_cutoff`; the cutoff changes no result).
- **Quadratic regex and parser paths found.**
  - `\s+[\s/*#]*`: 5 s at 32,000 spaces.
  - configparser on 3.10: `[project]\nlicense` plus 50,000 spaces took 8.6 s;
    fixed to 2 ms.
  - The upstream py-spdx-license tokenizer (`t.value += c`,
    `tokens.pop(0)`): 6.8 s on a 1,000,000-character value.
  - Guard against it: the sum of squared token lengths must not exceed 10^9
    (about 8 ms).
- **Timing differs by Python version.** One test took 5.3 s on CI's 3.10
  against about 1 s locally; deep-parse failures are slow on 3.10. Rule:
  10× headroom.

### Correctness

- **The score cap merges answers.** About 30 % of licence names and 13 % of
  full texts put a second licence at 1.0 after capping (10-02). Hence the
  `exact` key.
- **Short phrases score 1.0.** Any 2–3-word phrase that appears verbatim in a
  licence scores 1.0, for example "license identifier" → CAL-1.0 (item 28).
- **A missing file is read as text** (item 32).

  | Argument (no such file) | Answer |
  | --- | --- |
  | `LICENSE.txt` | APL-1.0, score 1, exit 0 |
  | `COPYING` | GFDL-1.1-invariants-only |
  | `LICENSE` | 0BSD |

  `is-osi LICENSE.txt` answered true.
- **Exit codes before #70.**
  - Ctrl-C gave "Aborted!" and exit 1, so `is-osi` read an interrupt as "not
    OSI".
  - A failing stderr turned every exit status into 120.
  - After #70: 130, 141 and 2 respectively.
- **Readiness gate (#55).**
  - With `immutable=1`, a concurrent update produced 40 "malformed" errors in
    302,000 reads.
  - `PRAGMA quick_check` was rejected: about 200 ms on a 46 MB database,
    twice per command.
  - `file::memory:NAME` is backed by a file.
  - A FIFO passed as `--db` blocks a read-only open.
- **Tie-breaker (09-20).**
  - 344 of 4,741 golden results changed.
  - 182 GFDL slices moved to `-or-later`.
  - Licence fixtures: 1,949 → 1,948 correct top answers (30 lost, 29 gained).
- **Manifest reading (#65).** 22 golden answers changed. In 10 of them `main`
  had the wrong top answer, for example an Apache-2.0 fixture answered as
  Apache-1.0.
- **Upstream encoding bug.** py-spdx-license read its data with the locale
  encoding: it crashed under eucJP and garbled 7 names under cp1252
  ("QuÃ©bec"). Fixed upstream in PR #5.

### Supply chain and SBOM (10-02 to 10-05)

- **pitloom 0.19.0 `embed-wheel`.**
  - Hashes:
    - `RECORD`'s hash is stale, because embedding rewrites `RECORD`;
    - the SBOM lists its own hash, which no file can hold correctly;
    - 30 hashes match and 2 are stale.
  - `spdx3-validate` checks structure only, so it passes.
  - The dependency versions come from the CI environment: rapidfuzz 3.14.5
    in one build, 3.14.6 in the other.
- **The hook's SBOM.**
  - With pitloom 0.19.0: 26–27 files, all hashes match.
  - With pitloom 0.20.0 (10-05):
    - `RECORD`: 0 mismatches;
    - 27 files, all hashes match;
    - Apache-2.0 both declared and concluded;
    - `builtTime` in UTC with `Z`.
  - pitloom #271 fixed the stale-hash bug upstream.

### Verification scale

- Golden set: 1,405 fixture files, sometimes extended to 4,741 results with
  popularity off and on.
- Mutation testing:
  - each PR killed 7–25 mutants;
  - R1 on #68 found 13 of 80 mutants surviving;
  - an audit on #58 killed 83 of 138, revealing 43 test gaps.

## 6. Quotable user feedback (under 25 words each)

- "Don't do long free prose" (09-19 10:27).
- "make sure we are not enforcing wrong behavior in tests. if not sure, do
  not hallucinate" (09-19 15:26).
- "do manual CLI tests to cover all combinations of subcommands and flags ...
  note the matrix one by one, so you are not missing it" (09-19 15:37).
- "we have time. let's do the clean up now. we hope that subsequent PRs will
  be benefit from this." (09-19 16:36).
- "do you think we are converging to a stable PR now? or each new round of
  reviews always find something new?" (09-20 07:46).
- "make sure we are doing reuse correctly. reuse is a good strategy to
  prevent future drift" (09-21 09:04).
- "correctness, consistency, no-silent deviation, and no undocumented
  surprise are important as always." (09-21 19:25).
- "which one is less of user surprise?" (09-21, design question).
- "the background job is running for 28h already. is this normal?"
  (09-23 07:11).
- "I think it will be easier to just say that --id is for exact SPDX license
  ID, and not SPDX license expression." (09-24 09:30).
- "our job now is to put some guard here as a workaround. we can lift/relax
  the guard later" (10-01 10:47).
- "i would stop fixing these edge cases after this round, we have to do a
  revision of license match rules anyway" (10-02).
- "keep the cap and add a way to filter exact hits -- we would need to think
  about ranking internally later too." (10-02 02:30).
- "are we ready here or need more rounds of code review or decisions?"
  (10-02 11:18).
- "looks like the sbom generated from github action is more rich?"
  (10-03 08:36). The premise was refuted with data.
- "i think i will wait for the new pitloom before release new version of
  licenseid" (10-03 11:44).

## 6b. Addendum, 2026-10-06 (PR #77; no transcript prefix kept)

- User request: "do the same for licenseid" as PR 462. The agent compared
  first and reported that the signing order was already in place, then
  changed only the gaps, instead of rewriting a working workflow.
- Mistakes caught by the agent's second review round, before the user saw
  them: `SECURITY.md` said 0.4.0 had no SBOM, signatures or attestations
  (0.4.0 signs the wheel and sdist, and attaches an unsigned SBOM); a
  changelog "Added" entry said the SBOM was now attached (it already was;
  only its signature was new). Both came from not reading the earlier
  workflow before writing prose about history. **[observation]**
- A recommendation weakened by one user question: the agent proposed
  allowing a public issue for dependency CVEs. Asked "is this safe?", it
  reversed to private-by-default with a narrow exception, naming the
  risk (exposure of how licenseid reaches the flaw; a "public" CVE that is
  not yet public). The first answer had optimised for reporter convenience.
- Scope error corrected by evidence: the user asked for a "CI failed" fix;
  the agent traced the Windows `pwd` failure to the user's own new Windows
  job, not to the SBOM change, and blocked `pwd`/`pty`/`termios` to show no
  other module failed at import. It said that run-time failures could not
  be known without CI.
- Tool-use pattern: the agent tested claims in a scratch copy (a venv in
  the scratchpad; the first attempt put the venv inside the tree and broke
  `python -m build` with an absolute symlink in the sdist).
- A pending question the user answered tersely: "minimal fashion, follow
  github recommendation", for the vulnerability section; GitHub's private
  reporting was off on the repository, which the agent checked with
  `gh api` before writing.

## 7. Memory files (state on 10-05), one line each

- `feedback_no_github_writes.md`: the user does all git and GitHub writes. A
  CI-monitor notice saying "commit and push" does not override that.
- `feedback_real_cache_home.md`: the E7-007 incident. Never run the CLI with
  `HOME` unset.
- `feedback_refactor_workflow.md` (130 lines): the review loop, plus these
  lessons:
  - judge lint by exit code;
  - never run mutation testing while another agent edits;
  - judge convergence by surface, not by round;
  - attack your own "no fixture changes" claim;
  - prototype in the scratchpad;
  - rerun the gate after the last edit;
  - a first version always needs a review round;
  - check that a flake reproduction matches the original;
  - check CHANGELOG placement;
  - the agent effort split.
- `perf-regression-checks.md`:
  - compare with `main`;
  - time with distinct values;
  - fixture-calibrated limits prove little;
  - sweep Japanese and Chinese text;
  - give timing tests 10× headroom for CI's 3.10.
- `perf-probe-gate.md`: about 93 % of match time was RapidFuzz. The probe
  gate gave 3.5×: 4,925 s → 1,394 s on the benchmark. Character caps were
  added in #62.
- `feedback_verify_release_state.md`: check tags, releases and
  `origin/main` before stating release state. Two misses on 10-05.
- `pitloom-workflow-sync.md` and `feedback_sibling_repo_copy.md`: mirror the
  sibling repo's release workflow. Report the gaps first, then copy, test,
  and add a source-link comment.
- `project_release_0_4_0.md`: 0.4.0 was released on 10-05, before #76. Its
  SBOM is unsigned, and the next release is the first run of SBOM signing.

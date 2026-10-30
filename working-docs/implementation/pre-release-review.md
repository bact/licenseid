---
Created: 2026-10-30
Last-Modified: 2026-10-30
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Pre-release review

How a release with many merged changes is reviewed as a whole before the
tag, after each change had its own review. Adopted by the maintainer for
0.7.0 (2026-10-30). It runs before step 2 of
[release-process.md](release-process.md) (the preparation PR).

Per-change reviews each see one diff; the bugs they miss sit where changes
meet. Rerunning every slow check in each review and fix loop costs most of
the time. This process builds the tests first, freezes the tree, and runs
the slow checks only twice.

## Principles

- Snapshot every public answer once (golden files), so a regression shows
  as a diff, not as a test someone has to think of.
- Rules become invariants and a generator; every finding arrives with a
  reproducer that drops into them.
- Slow checks (full `pytest tests/`, `--run-benchmark`, the full accuracy
  run, Python 3.14, `tools/cli_matrix --check`, the sdist and wheel dry run)
  run at two gates only. In between, a fix runs its targeted tests, the
  golden diff and the invariants.
- Reviewers read only: they get the code, their area and the first gate's
  report, never an earlier reviewer's findings.
- Fixes are batched by file, output-changing ones first and docs last, so
  one docs sweep describes the final outputs.
- Agents are sized to the work: Opus at high effort for planning, design,
  open questions and sensitive areas (the public contract, release,
  data); Sonnet at medium for bounded work; Haiku at low for mechanical
  checks.
- Performance is out of scope unless the release is about it; guards
  against hangs on hostile input are correctness and stay.

## API freeze at the candidate

From the candidate commit on, the public contract is frozen, so a
downstream project (Pitloom) can adopt the release from that commit before
the tag. Frozen: every public name (functions, classes, modules named in the
user docs), every result key and its type, the CLI's field names, separator
and escaping, the JSON form, and what each exit code means. Allowed: values
for edge inputs (a refusal that gains a reason, an `unresolved` value that
now reads), additions, and fixes that keep the contract. A finding that
needs a frozen item changed goes to the maintainer first; the default is the
next release. A change after the freeze that touches a field the downstream
project reads is flagged to its session.

## Phases

1. **Finish in-flight work.** Merge every change meant for the release.
   Anything merged after the freeze churns the golden files.
2. **Freeze and gate once.** The release candidate is a commit on `main`.
   Run every slow check once and keep the outputs as a report for the
   reviewers.
3. **Build the harness** (one PR, parallel agents):
   - golden snapshot: the resolver's answer on every corpus value, the
     detector's on the text fixtures, every CLI command's text and `--json`
     output; split fixtures under 800 lines; a diff test that accepts only
     listed changes, as `EXPECTED_CHANGES` does; also diffed against the last
     release, to show every intended change;
   - invariants: never raises on a string; packaged and database answers
     agree; an answer read again gives itself; the text line reads back to
     the JSON fields; the exit code agrees with the answer; JSON bytes are
     canonical (RFC 8785);
   - one seeded, grammar-based adversarial generator (IDs and names with
     quote marks, end marks, operators, `+`, "or later", white space,
     Unicode), shared by tests, reviewers and fixers;
   - mechanical health first: file sizes, complexity ceilings re-measured,
     names left over from a rename, lint, links.
   Run the harness on the candidate before merging it: its failures are
   the first findings.
4. **Review** (read-only, parallel, on the candidate and the harness):
   public API and result contract; CLI contract across every command;
   resolver rules as a whole (how they interact); packaging and release;
   caches, threads, files and Windows; user docs; a downstream trial (an
   agent that reads only the user docs, writes code against the release
   and runs it). Every finding has a severity and a reproducer.
5. **Triage.** Reproduce each finding; drop what does not reproduce; sort
   the rest into release blockers, cheap fixes for this release, and the
   next release.
6. **Fix in batches by file.** Per batch: targeted tests, golden diff,
   invariants, then CI on the PR. Decision numbers continue after the last
   one in use, never in parallel ranges that can clash.
7. **Final gate.** The same checks as the first gate (benchmarks must pass,
   no comparison unless the release is about speed), then the preparation
   PR of [release-process.md](release-process.md).

## Record

- 0.7.0 (2026-10-30): adopted before the tag; performance deferred to after
  the release; API frozen at the candidate (maintainer, 2026-10-30), commit
  recorded here when it is cut.

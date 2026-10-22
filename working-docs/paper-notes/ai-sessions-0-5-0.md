---
Created: 2026-10-22
Last-Modified: 2026-10-22
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted session, release 0.5.0

One Claude Code session (transcript `e712561b-8fdd-4066-b0a4-a4ad42306dbd`,
repository `licenseid`, ending 2026-10-22; resumed after context
compaction) took 0.5.0 from the plan to PyPI. Sources: the transcript, PRs
#85, #86, #90 to #95, commit `9e789d1`, `CHANGELOG.md`. Labels as in the
other notes: **[observation]** is checkable in the sources; the rest is the
author's reading.

## What was built

- `update` works where only `raw.githubusercontent.com` is reachable: a 1 MB
  bundle on an orphan `data` branch, SPDX's tarball, and a bundle shipped in
  the wheel by a Hatch build hook; three sources named `compact`, `upstream`
  and `packaged` (#85, #86, #90, `9e789d1`, #91; details in
  `../implementation/data-fetching-and-caching.md`). **[observation]**
- Two review rounds on `main` before the release (#92, #93), the second with
  an Opus subagent; every finding was fixed or closed on purpose.
  **[observation]**
- Two roadmap items closed after (#94): a named-pipe test that could hang the
  suite, and a lone surrogate that raised `UnicodeEncodeError`. **[observation]**

## Decisions that came from the human

- Licence texts need no licence of their own, and test fixtures (sample
  models, wheels) are not shipped in the wheel or the sdist.
- The `data` branch is pushed first, by hand, so build CI has something to
  download; the optional "relax the build when it is missing" branch was
  dropped.
- The weekly cron, not daily (Tuesday 22:19 UTC).
- Terms for the sources, chosen after the release notes read as confusing:
  `compact`, `upstream`, `packaged`, with "bundle" kept for the file format
  (#95). The agent had first proposed keeping the old names and renaming
  only prose; the human asked for the CLI values to change too, while nothing
  was public.
- A PR merged before the tag belongs in the open release section, not in a new
  `[Unreleased]` (the human corrected the placement).
- The agent never committed or pushed; the human did all git and GitHub
  writes, as in the earlier sessions.

## Mistakes the agent made, and what caught them

- A decorator ended up above the wrong test after an insertion: pytest
  reported a missing fixture (`required`). Collection error, fixed at once.
- A scripted edit matched an earlier copy of its anchor and duplicated about
  25 test functions: flake8 `F811` and pylint `E0102` showed it. Restored from
  git and redone from the anchor's position.
- A local ruff older than CI's missed import order (I001); CI failed on #93.
- A guessed PR number went into the changelog, and was removed before it was
  read as fact.
- The roadmap text for item 41 was wrong ("the CLI cannot send one"); running
  the CLI with an invalid-UTF-8 argument showed a traceback and exit 1, and
  the fix covers both entry points.
- A release-note sentence ("shrink an existing database") was flagged as
  unverified when drafted; the `VACUUM` in `database.py` supports it, but it
  was not tested on an old database.

## Verification used as evidence

- Behind a proxy that tunnelled only `raw.githubusercontent.com`, `update`
  built the database. **[observation]**
- `uv build` of the wheel and the sdist, install in a clean venv, and
  `update --source packaged` offline: database built. **[observation]**
- Database from the compact bundle: 17.4 MB, against 24.6 MB before XML was
  dropped (changelog: "about 7 MB smaller").
- Full suite at the end: 3,103 passed, 25 skipped; CI on the merge commit
  green except Scorecard, which failed on a GitHub GraphQL error.

## Process notes for the write-up

- Reviews found real bugs (a redirect to plain http in the build hook, a
  scratch directory left after a failed download) but also cost a PR each
  (#92, #93) before one release.
- The terms problem is a vocabulary one: the same bytes had two names by
  origin. It was found by reading the draft release notes, not by tests.

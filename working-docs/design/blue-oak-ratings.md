---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Blue Oak Council ratings as extra licence information

Status: idea, not planned for a release. Recorded on 2026-10-28 so that a
later release can weigh it; nothing is built.

See also: [`resolver-0-7-plan.md`](resolver-0-7-plan.md) (the `lists`
entries of a resolution).

## What the list is

The Blue Oak Council License List rates permissive open source licences by
how well they are drafted. It is small, curated and keyed by SPDX ID, so it
could add one fact per licence beside the OSI and FSF flags that licenseid
already reports (`is-osi`, `is-fsf`).

The ratings, best first (the council's own names):

| Rating | Licences | Meaning, in short |
| - | - | - |
| Model | 1 | The council's own Blue Oak Model License 1.0.0 |
| Gold | 1 | Addresses patents, robust wording, simple notice only |
| Silver | 30 | Robust wording, but no explicit patent terms or more than simple notice |
| Bronze | 121 | Lacks important but nonessential elements, or adds requirements |
| Lead | 72 | Lacks essential elements or imposes unusually burdensome terms |

Counts are from version 16 of `list.json`, fetched on 2026-10-28.

Examples: `BSD-2-Clause-Patent` is Gold; `MIT`, `Apache-2.0`, `ISC` and
`BSD-2-Clause` are Silver; `BSD-3-Clause`, `0BSD`, `Unlicense`, `Zlib` and
`PSF-2.0` are Bronze.

## The data

- `https://blueoakcouncil.org/list.json`: top-level `version` (`"16"`) and
  `ratings`, an array of `{name, notes, licenses}`; each licence is
  `{name, id, url}`, and `id` is an SPDX ID.
- The npm package `@blueoak/list` carries the same data. Its npm metadata
  states `CC0-1.0`, but its latest version (15.0.0) lags the website (16).
  The website itself shows a copyright notice and no licence for the list.
- Checked against SPDX 3.29.0: all 225 IDs are in the SPDX list. Four are
  deprecated there: `BSD-2-Clause-FreeBSD`, `BSD-2-Clause-NetBSD` (both
  Silver), `bzip2-1.0.5` and `Net-SNMP` (both Bronze).

## Possible uses

- A flag beside `is_osi_approved` and `is_fsf_libre`: the rating of a
  matched or resolved licence, for example `BLUEOAK=silver` in the text
  output and a `blueoak` key in `--json`.
- A further entry in `lists` of `resolve()`, as the plan adds one for the
  PyPI trove classifiers: `id_authority: false`, providing ratings only. It
  would never decide an ID, only describe one.
- For a consumer such as Pitloom, a licence-quality note in an SBOM, with
  the list version recorded.
- Evidence for a Model Openness Framework assessment (next section).

## Model Openness Framework

The Model Openness Framework (MOF) of the LF AI & Data Generative AI
Commons ranks a machine learning model in three classes: Class III Open
Model, Class II Open Tooling and Class I Open Science (the most complete).
Each class names the components a model must release and the licences they
must carry; its `MOF.JSON` records each licence as an SPDX ID. An AIBOM
generator such as Pitloom could read those IDs through licenseid and help
fill in an assessment.

What Blue Oak can and cannot add there:

- Code components (architecture, training, inference and evaluation code)
  need an OSI-approved licence. Blue Oak does not decide that: `is-osi`
  does. A Blue Oak rating could describe how well an accepted permissive
  code licence is drafted, as extra information, never as a pass or fail.
- MOF prefers `CDLA-Permissive-2.0` for model parameters and metadata, and
  `CDLA-Permissive-2.0` or `CC-BY-4.0` for data and documentation. Blue Oak
  rates neither: of the data and content licences, version 16 rates only
  `CC0-1.0` and `OGL-Canada-2.0` (both Bronze). For those components a
  missing rating says nothing.
- MOF itself does not rate licence quality and does not mention Blue Oak.
  Any use of the ratings in an assessment is our addition and must be
  labelled as such.

The MOF check that licenseid could support directly is simpler: is each
declared component licence a valid SPDX ID, and is it OSI-approved, or one
of the data and content licences the framework names. That is a table of
MOF's own, with its version, separate from the Blue Oak data.

## Rules if it is built

- Absent is not a rating. The list covers permissive licences only:
  `GPL-3.0-only` has no rating because it is out of scope, not because it is
  poor. Say "not rated", never a default.
- A rating belongs to the ID as the list writes it. Do not carry it to a
  successor (`BSD-2-Clause-FreeBSD` is deprecated in SPDX) or to a
  look-alike ID; the council rated that text, not the other.
- A compound expression has no rating of its own: report each operand's.
- Record the list version beside every rating; ratings can change between
  versions.
- Keep the data apart from the SPDX bundle, with its own source, version
  and staleness warning in the diagnostic grammar of `AGENTS.md`.

## Open questions

1. The licence of the list data: confirm with the council before shipping
   a copy (website version 16 states none; the npm package states CC0-1.0).
2. Where the data comes from: the website JSON, the npm package, or a copy
   on the `data` branch beside the compact bundle.
3. Whether the rating goes into the database (a column, a build-version
   bump) or stays a separate small table read at run time.
4. Command-line shape: a key on the existing result line, or an
   `is-blueoak` command in the style of `is-osi`.

## Sources

Blue Oak Council. "License List." Version 16. Accessed October 28, 2026.
<https://blueoakcouncil.org/list>.

Blue Oak Council. "list.json." Version 16. Accessed October 28, 2026.
<https://blueoakcouncil.org/list.json>.

White, Matt, Ibrahim Haddad, Cailean Osborne, Xiao-Yang Yanglet Liu, et
al. "The Model Openness Framework: Promoting Completeness and Openness for
Reproducibility, Transparency, and Usability in Artificial Intelligence."
arXiv:2403.13784v6, October 18, 2024. <https://arxiv.org/abs/2403.13784>.

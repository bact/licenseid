---
Created: 2026-11-05
Last-Modified: 2026-11-05
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Collection criteria of the licence value corpus

What the corpus of `dataset-licence-values.md` samples, from where, and
why, so the methods section of the paper can state its population and a
reader can fetch the same packages again. Built by `tools/licence_sample/`
(see its `README.md`). **Proposed** marks a criterion the maintainer has not
yet decided.

## Unit and population

- **Unit.** One package at one release: the latest release that
  ecosyste.ms lists on the frame date, pinned (a version; a commit for a
  Hugging Face model). Each licence string its metadata declares is one
  value (a POM with two licences gives two names and their URLs). Licence
  files are out of scope: they are text, not declared values.
- **Channels.** PyPI, npm, crates.io, Maven Central, NuGet and Hugging
  Face models: the package channels SBOM generators read most. **Proposed:**
  Hugging Face datasets as a seventh.
- **Population.** Every package of the channel's registry as ecosyste.ms
  indexes it on the frame date. ecosyste.ms gives one ranking for all six;
  the values come from each registry itself (POM, `.nuspec`, `package.json`,
  PyPI JSON, model card metadata), as written. crates.io is the exception:
  its crawler policy allows one request a second and its index holds no
  licence, so its `Cargo.toml` `license` is the value ecosyste.ms lists.

## Strata

- **Head (built).** The top N packages by usage: 30-day downloads for
  PyPI, npm, crates.io, NuGet and Hugging Face; dependent packages for
  Maven Central, whose downloads ecosyste.ms does not report. Why: these
  are the values most consumers meet, and a share weighted by downloads
  says how often a reader faces each form.
- **Tail (follow-up, decided 2026-11-05).** To take once the head is
  fetched, not beside it: ecosyste.ms was already the bottleneck of the
  head (five rankings still paging after the sixth was half fetched), and
  the tail needs either its deep pages or each registry's whole list of
  names. A uniform random sample of the whole registry,
  seeded. Why: the head is biased towards maintained packages that state an
  SPDX ID; a tool also meets the long tail, whose values are expected to
  be messier (to measure, not to assume). Paging ecosyste.ms by `id` reaches
  deep pages in 50 to 70 s each, and npm's deepest pages fail (HTTP 500,
  measured 2026-11-05), so a random sample needs each registry's own list
  of names (PyPI's simple index, npm's replication feed, the crates.io
  database dump, the Maven Central index, the NuGet catalogue, the Hugging
  Face listing API).

## Size

- **Proposed:** N = 1,000 per channel and stratum. A share measured on
  1,000 packages has a 95% margin of error of at most 3.1 percentage
  points, and the distinct values (a few hundred per channel) stay few
  enough for two annotators to read every one.

## What is recorded, not dropped

- A package with no release, a 404 or 410 reply, or a private or gated
  model: kept, with no value and its reply recorded as missing.
- A value over 200 characters or on several lines: kept, counted as
  licence text, not as a declared value.
- Copies: Hugging Face fine-tunes often copy their base model's card, and
  Maven artifacts inherit their parent POM's licences (recorded as
  `parent:name`, `parent:url`). Distinct values are annotated once; the
  per-package counts keep the weight.

## Reproducibility

- A frame file states its criteria on its first line (channel, registry,
  ranking, count, when and from where it was taken, the population in
  words), then one package a line with its rank and pinned version.
- A sample file holds, per package, each reply read (URL and SHA-256) and
  when, so a later fetch of the same frame shows which replies changed.
- **Proposed:** keep the frames and samples with the paper's data deposit
  (Zenodo), with the tool commit, the SPDX License List version and the
  licenseid version that answered. The raw replies are larger; keep them in
  the deposit too if their licences allow it.
- **To check:** the terms of ecosyste.ms data and of each registry's API
  before redistributing rankings or replies.

## First frame: a pilot of the top 50

Taken 2026-11-05 14:58 UTC, head stratum. The run for N = 1,000 stopped
part way:

- **Ranking.** The crates.io and Hugging Face frames are complete. Maven,
  npm, NuGet and PyPI hold 300 to 600 packages: a failed ecosyste.ms page
  ended `rank` as if the registry had ended (fixed: it now refuses).
- **Fetching.** Every PyPI, npm, NuGet and Maven reply of that run failed
  (1,211 packages) and was recorded as stating no licence (fixed: a failed
  reply is now recorded as failed). Those samples are unusable.

The pilot is the top 50 of each frame (`cut`, `cut_from: 1000`). crates.io
and Hugging Face are kept from the run; the four others were fetched again
from the same frames, at the same pinned versions, with no reply failed.
It serves to start the work, not as a result: 50 packages give a 95% margin
of error of up to 14 percentage points. The corpus is the later run of
1,000 for the head and 1,000 for the tail, with its own frame date.

| Channel | Value | URL | Unresolved (values) |
| --- | --- | --- | --- |
| PyPI | 50 | 0 | 6: trove `BSD License` (3), `Apache Software License` (2) |
| npm | 50 | 1 | 0 |
| crates.io | 50 | 0 | 1: `MIT/Apache-2.0` |
| Maven | 48 | 48 | 10: `The Apache Software License, Version 2.0` (6) |
| NuGet | 50 | 50 | 0 (9 packages state only a `fwlink` URL) |
| Hugging Face | 47 | 9 | 8: `other` (4), model licences off the List |

Columns: packages that state a value, packages that state a URL, and the
values `resolve()` refuses (URLs apart). Every other value resolves: as
written (`exact`), or as a valid expression put in canonical order or an
ID in another case (`lexical`: 42 of 50 crates, `MIT OR Apache-2.0` as
`Apache-2.0 OR MIT`; 43 of 51 model values, `apache-2.0`). The trove names
are refused by design (no version).

What it shows for a URL reader:

- Maven: 29 of 50 URLs match no `seeAlso` URL, 22 of them
  `apache.org/licenses/LICENSE-2.0.txt`: the List has the page without
  `.txt`. One URL (`gnu.org/.../lgpl-2.1.html`) names two IDs (`-only`,
  `-or-later`).
- NuGet: 41 of 50 URLs are `licenses.nuget.org/<expression>`, an
  expression in the path, beside the same `license:expression`; 9 are
  `go.microsoft.com/fwlink`, which name no licence without a redirect.
- Hugging Face: links to a model's own `LICENSE` file, no List URL.

Files: `scratchpad` run of 2026-11-05, `ls/2026-11-05-top50/` (frames,
samples, `analysis.txt`); to keep with the deposit.

---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# A dataset of declared licence values

Candidate for publication as a dataset with a short data paper, and for a
section of the licenseid write-up. The data were built as test fixtures in
PR #110 (task T0 of the 0.7.0 plan); this note says what they are, why other
tool developers could use them, and what is missing before they can be
published. **[observation]** where marked.

## What exists (PR #110)

Two tab-separated tables under `tests/fixtures/`, documented in its
`README.md` (section 7):

| Table | Rows | Content |
| --- | --- | --- |
| `pypi_values_2026-10.tsv` | 462 distinct values | The licence value each of the top 10,000 PyPI projects declares, with field, project count, download total and the answer of `resolve()` 0.6.0 |
| `resolver_parity.tsv` | 140 values | 83 real values and 57 synthetic edge cases, with the answers of Pitloom 0.21.1 and licenseid 0.6.0 and the answer expected from 0.7.0, each with a reason |

PyPI sample:

- Projects: the 10,000 most downloaded of hugovk's `top-pypi-packages` list
  (30-day counts); `info.license`, `info.license_expression` and the
  `License ::` classifiers of each project's latest release from the PyPI
  JSON API, fetched on 2026-10-28. 9,998 answered.
- The value used per project: the first of `License-Expression`, a one-line
  `License` of at most 200 characters, the classifiers. 9,370 projects have
  such a value; 17 with several classifiers are left out; the other 9,353
  share 462 distinct strings.
- The distinct values are kept exactly as written (no case or white space
  folding: folded, they would be 436). An independent recount from the raw
  fetch matched the table row by row, and a re-export is byte-identical.
- A header records the count and a SHA-256 of the sorted rows.

What the 10,000 declare, as `resolve()` 0.6.0 reads it (projects): exact ID
5,639 (60.2%); unresolved 1,783 (19.0%); listed name 1,305 (13.9%);
separator spelling 305 (3.3%); bare deprecated ID 124 (1.3%); compound 111
(1.2%); version spelling 70; several classifiers 17; other lexical 10; `+`
to `-or-later` 6. The unresolved, by a first reading of their pattern:
bare or family names 684, trove classifier names 484, prose forms of one ID
318, other 158, proprietary 70, trailing parenthesis 33, aliases 22, full
trove paths 14.

The top-5,000 subset reproduces the earlier sample of the same day
(`results-and-findings.md` section 3.5) to within one project, the
difference being PyPI drift.

Parity corpus:

- Real values: the licence fields of installed distributions (two local
  Python environments) and of Pitloom's test projects and sdists, collected
  on 2026-10-28; 30 multi-line or over-long values left out.
- Synthetic values: the gaps named in the 0.7.0 design
  (`../design/expression-resolution.md`), dropped characters (`Apache
  2.0?`, a lone surrogate, U+FFFD), control and format characters, `WITH`
  and `+` shapes, brackets, repeated terms.
- `expected_0_7_0` is a prediction from the plan, not a measured answer;
  `?` marks the rows the plan does not decide.
- Pitloom 0.21.1's answers equal those recorded for 0.21.0 in the evidence
  document on every value that could be compared.

Values are written with Python's `unicode_escape`, so tabs, NUL, bidirectional
controls and lone surrogates survive a round trip (checked for every code
point).

## Why it may be useful beyond licenseid

This section is an **[observation]**, not a measured claim.

- Declared licence values are what SBOM generators, licence scanners and
  package-metadata tools read first, and PEP 639 (`License-Expression`) is
  still being adopted: 1,571 of the top 5,000 projects use it. A shared,
  frozen sample lets two tools be compared on the same input.
- The long tail is small and concrete: 462 strings cover 9,353 projects,
  so a tool author can read every one.
- Each row carries two independent tools' answers and the reason they
  differ, which is a starting point for a gold standard.
- The synthetic rows are adversarial cases that real data rarely shows
  (doubt marks, encoding damage, repeated terms) but that a normaliser must
  not read as a licence.

## Before it can be published

1. **A gold standard.** Today the rows hold tool answers and predictions.
   A dataset needs, per value, what a careful reader would record: an SPDX
   expression, `NOASSERTION`, or "several licences", with a reason. Two
   annotators and their agreement (Cohen's kappa), disagreements resolved
   and kept.
2. **The raw fetch.** `sample-2026-10.jsonl` (project, version, the three
   fields, downloads) is kept outside the repository. Publishing it makes the
   per-project view and other "value used" rules reproducible.
3. **Rights.** The values are short facts written by project authors and
   served by the PyPI JSON API. hugovk's `top-pypi-packages` repository
   states no licence (checked 2026-10-28); its counts come from the
   ClickHouse PyPI dataset. Confirm the terms of both before redistributing
   the download counts. A candidate licence for the dataset itself:
   CDLA-Permissive-2.0 or CC0-1.0.
4. **A datasheet** in the style of Gebru et al.: motivation, composition,
   collection, preprocessing, uses, distribution, maintenance.
5. **Scope.** Options that would make it a dataset rather than a fixture:
   more projects (the whole list of about 15,000), several releases per
   project (the uptake of `License-Expression` over time), and npm, Cargo
   and Maven fields.
6. **Versioning.** A release with a DOI (Zenodo), each tied to its fetch
   date, the SPDX list version (3.29.0) and the tool versions that answered.

Possible venues: a data or tool showcase track of a software engineering
conference (for example the MSR Data and Tool Showcase Track), a data
journal, or a section of the licenseid paper with the data deposited.

## Threats to validity

- The top projects by downloads; a value weighted by installation, not by
  authorship.
- The latest release only.
- One "value used" rule; another order of the fields gives other counts.
- The groups of unresolved values are patterns, not tested rules.
- The real values of the parity corpus come from one developer's machines.

## Sources

- PR #110: `tests/fixtures/pypi_values_2026-10.tsv`,
  `tests/fixtures/resolver_parity.tsv`, `tests/fixtures/README.md`,
  `tools/pypi_licence_sample/` (`fetch`, `analyze`, `export`).
- `../design/resolver-0-7-evidence.md` (PR #103): the first sample.
- Gebru, Timnit, Jamie Morgenstern, Briana Vecchione, Jennifer Wortman
  Vaughan, Hanna Wallach, Hal Daumé III, and Kate Crawford. "Datasheets
  for Datasets." *Communications of the ACM* 64, no. 12 (2021): 86–92.

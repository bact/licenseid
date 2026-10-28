# PyPI licence sample

Measures how `licenseid.resolve()` fares on the licence values that real
PyPI projects declare, and groups the ones it cannot read by what would read
them.

## Why it exists

`resolve()` was built from a short list of examples. Which cases to support
next (compounds, prose such as `Apache License, Version 2.0`, trove classifier
names, aliases) is a question of how often each occurs and how many downloads
it carries. This tool answers it with data, so a rule is chosen by its share
and not by memory. The findings are in
`working-docs/design/resolver-0-7-evidence.md`; the plan they feed is
`working-docs/design/expression-resolution.md`.

## When to run it

- Before deciding what the next `resolve()` release should read.
- After a change to the lexical rules, to see how many real values it newly
  reads (compare the `unresolved` count before and after).
- Rarely otherwise: it is a research tool, not part of the tests or CI.

## How to run it

```shell
# 1. Download the licence fields (network, a few minutes for 5,000 projects).
python -m tools.pypi_licence_sample fetch --count 5000 --out sample.jsonl

# 2. Count (no network; needs the licence database: licenseid update).
python -m tools.pypi_licence_sample analyze sample.jsonl --top 40

# 3. Freeze the distinct values and their answers as test fixtures.
python -m tools.pypi_licence_sample export sample.jsonl \
    --out tests/fixtures/pypi_values_2026-10 --db /path/to/licenses.db
```

`analyze` and `export` read the default database unless `--db PATH` names one
(opened read only). The `fetch` list is in download order, so the first N
lines of the file are the top N projects: `head -5000 sample.jsonl >
top5000.jsonl` makes the top-5,000 subset.

`fetch` reads the `top-pypi-packages` list (hugovk; download counts) and the
PyPI JSON API of each project's latest release. It sends a User-Agent naming
this repository, 16 requests at a time, retrying a failure three times. Keep
the file: the same sample compared before and after a change is the point, and
PyPI changes over time.

`analyze` prints, for the projects with a short declared value:

- the source used (`License-Expression`, `License`, classifiers, none, or
  licence text only);
- the category `resolve()` gives each value, with its share;
- the unresolved values by group (`GROUPS` in `__main__.py`), with project
  counts and download totals;
- the most common unresolved values.

`export` writes the distinct short values (the value `analyze` picks, but not
several classifiers joined by `AND`) to tab-separated files, sorted by value:
`value` (Python `unicode_escape`), `field` (the source most projects used),
`projects`, `downloads` and the answer of `resolve()`: `expression_0_6_0`,
`category_0_6_0`, `candidates_0_6_0`, `steps_0_6_0`, `expansions_0_6_0`,
`trust_0_6_0` and `input_same_0_6_0` (`-` is none). A file has at most 790
lines (`--max-lines`), so `--out P` gives `P.tsv`, or `P-1.tsv`, `P-2.tsv` and
on. If the values need more than `--max-files` (6) files, `export` keeps every
value whose category is not `exact`; if those still do not fit, or
`--max-files` is below 1, it exits 2 and writes nothing. Each header records
the number of distinct values and the SHA-256 of the full sorted `(value,
expression, category, candidates)` set. Remove the files of an earlier export
first: it does not delete them. `tests/test_resolver_sample.py` freezes these
files (see `tests/fixtures/README.md`).

## Reading the result

- The groups are patterns, a first reading to rank work by. A rule is
  promised only after the sample is rerun with it.
- The value used per project follows the usual order: `License-Expression`,
  then a one-line `License` of at most 200 characters, then the classifiers
  (several are joined with ` AND `, counted apart as "several classifiers").
- Only the latest release of each project is sampled, and only the top N by
  downloads.
- Downloads are the list's 30-day counts; they weight a value by how widely it
  is installed, not by how many people wrote it.

## What it does not do

- It does not compare with any consumer. Pitloom's own reading was compared by
  hand once; see the evidence document.
- It does not cover npm, Cargo or Maven licence fields.
- It does not time `resolve()`.

Standard library and `licenseid` only.

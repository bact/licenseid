# Licence sample of six package channels

Takes a sampling frame of the top packages of PyPI, npm, crates.io, Maven
Central, NuGet and Hugging Face, reads each package's declared licence
values from its own registry, and counts what `licenseid.resolve()` reads,
licence URLs apart. The criteria, and why, are in
`working-docs/paper-notes/collection-criteria.md`.

## How to run it

```shell
# 1. The frame: the top 1,000 packages of a channel (network).
python -m tools.licence_sample rank maven --count 1000 --out frame-maven.jsonl

# 2. The values of each package of the frame, at its pinned version (network).
python -m tools.licence_sample fetch frame-maven.jsonl --out sample-maven.jsonl

# 3. Count (no network): --list is an SPDX license-list-data tarball or its
#    licenses.json, for the URLs of seeAlso; --db a licenseid database.
python -m tools.licence_sample analyze sample-*.jsonl --list licenses.json

# The top 50 of a larger frame and its sample, as files of their own
# (no network): the header keeps the criteria and states cut_from.
python -m tools.licence_sample cut frame-maven.jsonl sample-maven.jsonl \
  --count 50 --out-frame top50/frame-maven.jsonl \
  --out-sample top50/sample-maven.jsonl
```

Keep the frame and the sample files: they are what makes a count
reproducible. The frame's first line states its criteria; each sample line
records the URL and SHA-256 of every reply read, so a later `fetch` of the
same frame shows which replies changed.

A ranking page that fails ends `rank` with an error rather than a shorter
frame. A reply that fails after three tries is recorded with its `error`;
`fetch` warns how many packages have one, and `analyze` counts them as
`failed`, not as stating no licence. Fetch those packages again. `cut`
refuses a sample that lacks a rank of the cut.

## Where each value comes from

Ranked by downloads, except Maven Central (dependents):

- `pypi`: `License-Expression`, `License` and `License ::` classifiers
  (PyPI JSON of the release).
- `npm`: `license` and `licenses` (registry document of the version).
- `cargo`: `license` as ecosyste.ms lists it (crates.io allows one request
  a second).
- `maven`: `<licenses>` names and URLs of the POM, else of the nearest
  parent POM.
- `nuget`: `<license>` (with its type) and `<licenseUrl>` of the
  `.nuspec`.
- `huggingface`: `license`, `license_name` and `license_link` of the model
  card at the commit.

The ranking comes from ecosyste.ms (`packages.ecosyste.ms`). An XML reply
that declares a DTD or an entity is not read. Requests send a User-Agent
naming this repository, 8 at a time, retrying a failure three times.

`analyze` prints, per channel: the packages with a value and with a URL,
the fields, the category `resolve()` gives each value that is no URL, and
for each URL whether the List's `seeAlso` (with SPDX's own page of each ID)
names one licence, several or none, with the hosts and URLs of the rest.
URLs are compared by `licenseid.urlkey` (scheme, `www.`, case, fragment,
trailing slash and index page do not count; a query does); a `seeAlso` URL
with a fragment is skipped.

Standard library and `licenseid` only. `tests/test_licence_sample.py` runs
every reader on fake replies.

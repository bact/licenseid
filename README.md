# LicenseID - A portable SPDX licence identification tool

[![PyPI - Version](https://img.shields.io/pypi/v/licenseid)](https://pypi.org/project/licenseid/)
![GitHub License](https://img.shields.io/github/license/bact/licenseid)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14002/badge)](https://www.bestpractices.dev/projects/14002)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/bact/licenseid/badge)](https://scorecard.dev/viewer/?uri=github.com/bact/licenseid)
[![DOI](https://img.shields.io/badge/doi-10.5281%2Fzenodo.19881009-blue)](https://doi.org/10.5281/zenodo.19881009)

Get the [SPDX License ID][spdx-license-id] from licence text.

A portable SPDX licence identification tool with a command line interface
and a Python API.
No database daemon or server needed.

*Used as a licence detection engine for [Pitloom] software bill of materials
generator.*

[spdx-license-id]: https://spdx.org/licenses/
[Pitloom]: https://github.com/bact/pitloom/

## Features

- Finds the licence in a file, a licence text or a source file's
  `SPDX-License-Identifier` tag.
- Reads a declared value (a `license` field, a trove classifier) as an SPDX
  expression, with each step taken, or refuses: it never guesses.
- Normalises expressions: `(MIT OR MIT) and Apache-2.0` ->
  `Apache-2.0 AND MIT`; deprecated IDs: `GPL-2.0+` -> `GPL-2.0-or-later`.
- Reads a licence URL (`https://www.apache.org/licenses/LICENSE-2.0` ->
  `Apache-2.0`), loose IDs (`Apache2`, `GPLv3`), a licence's own title
  (`CC0 1.0 Universal`), the BSD aliases (`New BSD`, `BSD-3`), prose forms
  (`BSD 3-Clause License`) and trove classifiers.
- Prints parseable, line-delimited output.

## Installation

```bash
pipx install licenseid
```

Or with `uv`: `uv tool install licenseid`. Under a multibyte locale that is
not UTF-8, set `PYTHONUTF8=1` first; see [installation][doc-installation].

## Quick start

Build the local licence index once:

```bash
licenseid update
```

Then ask a question. `detect` finds the licence in a file, an ID or a text;
`resolve` reads a declared value and needs no database. Each prints the SPDX
expression alone, best first (`--top 1` keeps one), or an empty line and
exit code 1 when there is no answer:

```bash
licenseid detect --top 1 LICENSE.txt        # Apache-2.0
licenseid detect --top 1 MIT                # MIT
echo "MIT License..." | licenseid detect    # a text from standard input
licenseid resolve "GPLv2 or later"          # GPL-2.0-or-later
```

Add `-v` for the detail behind the answer (score, steps, reason), or
`--json` for one JSON object per result:

```console
$ licenseid resolve -v "GPLv2+ or MIT"
EXPRESSION=GPL-2.0-or-later OR MIT	CATEGORY=version_spelling	TRUST=resolver_rule
STEP=separator	FROM=GPLv2	TO=GPL-2.0
STEP=version_spelling	FROM=GPLv2	TO=GPL-2.0
STEP=operator_case	FROM=GPL-2.0-or-later or MIT	TO=GPL-2.0-or-later OR MIT
STEP=plus_to_or_later	FROM=GPLv2+	TO=GPL-2.0-or-later
```

### Licence checks in scripts

`is-spdx`, `is-osi` and `is-fsf` exit 0 for true and 1 for false:

```bash
licenseid is-osi MIT >/dev/null && echo "OSI-approved"
```

### Python

```python
from licenseid import detect, resolve

detect(file_path="LICENSE")[0]["expression"]  # "Apache-2.0"
resolve("GPLv2 or later")["expression"]       # "GPL-2.0-or-later"
```

Use `detect()` to scan files and `resolve()` to record what a package
declares, as an SBOM tool does.

## Documentation

- [Installation][doc-installation]: install, and the non-UTF-8 locale note.
- [Command line][doc-cli]: every command, option, input kind, exit code and
  the `is-*` predicates.
- [Output formats][doc-output]: the text record, JSON Lines, fields,
  escaping, reading the output with `awk` and `jq`, and error lines.
- [Python API][doc-python-api]: `detect()`, `LicenseDetector`, the
  predicates, results, errors and warnings.
- [Declared values][doc-resolve]: what `resolve()` reads and returns, its
  categories, trust and reasons for a refusal.
- [How it works][doc-how-it-works]: ID normalisation, expressions and the
  matching tiers.
- [Development][doc-development]: running the tests.

[doc-installation]: https://github.com/bact/licenseid/blob/main/docs/installation.md
[doc-cli]: https://github.com/bact/licenseid/blob/main/docs/cli.md
[doc-output]: https://github.com/bact/licenseid/blob/main/docs/output.md
[doc-python-api]: https://github.com/bact/licenseid/blob/main/docs/python-api.md
[doc-resolve]: https://github.com/bact/licenseid/blob/main/docs/resolve.md
[doc-how-it-works]: https://github.com/bact/licenseid/blob/main/docs/how-it-works.md
[doc-development]: https://github.com/bact/licenseid/blob/main/docs/development.md

## License

Apache-2.0

## Citation

If you use this software, please cite it as follows:

> Suriyawongkul, A. (2026). LicenseID - A portable SPDX licence identification
> tool (Version 0.8.3) [Computer software].
> <https://doi.org/10.5281/zenodo.19881009>

BibTeX:

```bibtex
@software{Suriyawongkul_LicenseID_-_A_2026,
    author = {Suriyawongkul, Arthit},
    doi = {10.5281/zenodo.19881009},
    license = {Apache-2.0},
    month = nov,
    title = {{LicenseID - A portable SPDX licence identification tool}},
    url = {https://github.com/bact/licenseid.git},
    version = {0.8.3},
    year = {2026}
}
```

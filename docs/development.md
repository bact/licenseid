---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Development

How to work on `licenseid`.

## Running tests

Regular test suite:

```bash
pytest
```

Run it in parallel (about three times faster; needs `pytest-xdist`, which
`uv sync --group test` installs):

```bash
pytest -n auto
```

Run only the files that depend on the operating system, as CI does on
Windows (the list is `tests/platform_files.py`; a plain `pytest` runs every
file on every system):

```bash
pytest -m platform
```

Run benchmarks and accuracy tests (expensive; CI runs them weekly and when
the matching code changes):

```bash
pytest --run-benchmark
```

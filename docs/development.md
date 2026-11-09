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

Run benchmarks and accuracy tests (expensive; CI runs them weekly and when
the matching code changes):

```bash
pytest --run-benchmark
```

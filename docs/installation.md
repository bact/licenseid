---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Installation

Install `licenseid` as a command line tool.

Install with `pipx`:

```bash
pipx install licenseid
```

Or using `uv`:

```bash
uv tool install licenseid
```

## Non-UTF-8 locales

A dependency, `py-spdx-license` 0.0.1, reads its bundled licence data with
the locale's encoding. Under a multibyte locale that is not UTF-8, such as
`ja_JP.eucJP`, every command then fails at start-up with a
`UnicodeDecodeError`. The fix is waiting upstream in
[JPEWdev/py-spdx-license#5](https://github.com/JPEWdev/py-spdx-license/pull/5).
Until a fixed release is out, set `PYTHONUTF8=1` to run Python in UTF-8
mode:

```bash
export PYTHONUTF8=1
```

On Windows, use `set PYTHONUTF8=1` in Command Prompt or
`$env:PYTHONUTF8 = "1"` in PowerShell. UTF-8 locales and Python 3.15 or
later need no setting.

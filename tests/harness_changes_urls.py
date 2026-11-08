# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answers moved by ``resolve()`` reading a licence
URL (``licenseid.resolveurl``), for ``harness_changes.DETECT_CHANGES``:
``{case: (new value, reason)}``. The old answers were name guesses."""

_READ = "resolve() reads the licence URL (license_url): exact, by name"
_GUESS = f"{_READ} (was a name guess)"
_APACHE = "Apache-2.0\tname\tyes\t1.0000"
_MIT = "MIT\tname\tyes\t1.0000"

URL_CHANGES: dict[str, tuple[str, str]] = {
    "value/http://www.apache.org/licenses/LICENSE-2.0": (_APACHE, _GUESS),
    "value/https://www.apache.org/licenses/LICENSE-2.0": (_APACHE, _GUESS),
    "value/http://www.opensource.org/licenses/mit-license.php": (_MIT, _GUESS),
    "value/https://opensource.org/license/mit/": (_MIT, _GUESS),
    "value/https://opensource.org/licenses/BSD-3-Clause": (
        "BSD-3-Clause\tname\tyes\t1.0000",
        f"{_READ} (had no answer)",
    ),
}

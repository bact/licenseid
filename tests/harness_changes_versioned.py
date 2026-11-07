# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answers moved by ``resolve()`` reading a name with
a version (``licenseid.resolveprose``: ``Apache Software License 2.0``), for
``harness_changes.DETECT_CHANGES``: ``{case: (new value, reason)}``."""

_APACHE = "Apache-2.0\tname\tyes\t1.0000"
_ARTISTIC = "Artistic-2.0\tname\tyes\t1.0000"
_READ = "resolve() reads the name with a version (prose_form): exact, by name"
_GUESS = f"{_READ} (was a name guess)"

_CASES: dict[str, tuple[str, str]] = {
    "name/Apache-2.0/name_distored": (_APACHE, _READ),  # no answer since #161
    "name/Artistic-2.0/name_distored": (_ARTISTIC, _READ),
    "value/Apache Software License 2.0": (_APACHE, _GUESS),
    "value/Apache Software License v2": (_APACHE, _READ),
    "value/Apache Software License, Version 2.0": (_APACHE, _GUESS),
    "value/Apache Version 2.0": (_APACHE, _READ),
}

VERSIONED_CHANGES: dict[str, tuple[str, str]] = _CASES

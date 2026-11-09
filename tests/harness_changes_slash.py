# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden ``detect()`` answer moved by the "/" rule
(``licenseid.resolveslash``, roadmap item 43), for
``harness_changes.DETECT_CHANGES``: ``{case: (new value, reason)}``."""

SLASH_CHANGES: dict[str, tuple[str, str]] = {
    "value/MIT/Apache-2.0": (
        "Apache-2.0 OR MIT\tid\tyes\t1.0000",
        (
            "resolve() reads IDs joined by `/` as OR (the golden had no answer"
            " after resolve-first; before it, a wrong one: ECL-2.0)"
        ),
    ),
}

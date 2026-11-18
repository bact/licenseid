# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden detect() answers that moved in the 0.9.0 review, as
harness_changes.DETECT_CHANGES: {case: (new value, reason)}: an exact that went
from yes to no because the value was cut (a dropped end mark: category
``separator``; ``licenseid.resolvefirst.is_exact``), and a List name with a run
of white space, now read as the name."""

_CUT = "resolver-docs-1: a `separator` reading (a character was dropped) is not exact"
_RUN = (
    "A1: a run of white space in a List name reads as one space, so the name"
    " answers as the name spaced once does (`listed_name`), not as an ID"
)

REVIEW090_CHANGES: dict[str, tuple[str, str]] = {
    "value/Apache License 2.0.": ("Apache-2.0\tname\tno\t1.0000", _CUT),
    "name/BSD-4-Clause-Shortened/name_space": (
        "BSD-4-Clause-Shortened\tname\tyes\t1.0000",
        _RUN,
    ),
}

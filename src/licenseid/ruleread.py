# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whether ``resolve()`` read a value by a rewrite rule, for the ``EXACT`` of a
tag or a field (roadmap item 52)."""

from licenseid.listlookup import ListLookup
from licenseid.resolvefirst import is_exact
from licenseid.resolver import resolve_with


def rule_read(db: ListLookup, value: str) -> bool:
    """Whether ``resolve()`` reads *value* by a rewrite rule, so that a tag or
    a field of it is not exact, as the argument is not (``resolvefirst``)."""
    resolution = resolve_with(db, value)
    return resolution["expression"] is not None and not is_exact(resolution)

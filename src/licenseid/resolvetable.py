# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A value read as the ID a table of names gives it: the one reader of the
title table (:mod:`licenseid.resolvetitle`) and the alias table
(:mod:`licenseid.resolvealias`)."""

from collections.abc import Mapping

from licenseid.listlookup import ListLookup, fold_case
from licenseid.resolveleaf import Found, read_leaf
from licenseid.resolvertypes import step
from licenseid.resolvetrove import copy_reading


def read_by_table(
    db: ListLookup, text: str, table: Mapping[str, str], kind: str, found: Found
) -> bool:
    """Read *text* as the ID *table* gives its folded form (each run of white
    space one space, a line break too, and
    :func:`licenseid.listlookup.fold_case`, ASCII only) into *found*: a step
    of *kind* to that ID, then the steps of the ID read alone (a bare
    deprecated ID stays ``assumed_only``). False if *table* lacks *text* or
    the list lacks its ID."""
    license_id = table.get(fold_case(" ".join(text.split())))
    if license_id is None:
        return False
    reading = Found()
    if not read_leaf(db, license_id, reading):
        return False  # the list read lacks the ID
    found.steps = [step(kind, True, text, license_id), *reading.steps]
    copy_reading(found, reading)
    return True

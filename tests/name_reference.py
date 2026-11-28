# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``licenseid.shorttext`` worked out from the rows on every call before
``licenseid.nameindex`` held it, kept as the reference the index is tested
against (``test_shorttext``, ``test_db_lookup``). Do not optimise it."""

from licenseid.plusoperator import grant_stem
from licenseid.types import LicenseNameId

GRANT_WORDS = (" only", " or later")


def spellings(name: str) -> list[set[str]]:
    """The word sets that state a name without its grant."""
    words = name.split()
    spelled = [set(words)]
    if len(words) > 1 and words[-1] == "0":
        before = words[-2]
        if before.startswith("v") and before[1:].isdigit():
            spelled.append(set(words[:-1]))
    return spelled


def grant_left_out(rows: list[LicenseNameId], query: set[str]) -> set[str]:
    """The stems whose both grants name *query* (the old per-call scan)."""
    grants: dict[str, set[str]] = {}
    for row in rows:
        stem = grant_stem(row["license_id"])
        usable = not row["is_deprecated"] and stem != row["license_id"]
        for grant in GRANT_WORDS:
            name = row["norm_name"]
            stated = spellings(name[: len(name) - len(grant)])
            if usable and name.endswith(grant) and query in stated:
                grants.setdefault(stem, set()).add(grant)
    return {stem for stem, found in grants.items() if len(found) == len(GRANT_WORDS)}


def partial_names(
    rows: list[LicenseNameId], words: list[str], stems: set[str]
) -> set[str]:
    """The names that hold every word of *words* and more (old)."""
    query = set(words)
    pairs = [(row, set(row["norm_name"].split())) for row in rows]
    named = {bool(row["is_deprecated"]) for row, name in pairs if name == query}
    held = [row for row, name in pairs if query < name]
    if False not in named and stems:
        return {
            row["norm_name"]
            for row in held
            if grant_stem(row["license_id"]) not in stems
        }
    if named == {True}:
        return set()
    holders = {row["norm_name"] for row in held}
    if (
        len(holders) == 1
        and not named
        and 2 * len(query) >= len(set(next(iter(holders)).split()))
    ):
        return set()
    return holders


def exact_id_row(
    rows: list[LicenseNameId], norm_input: str, plus: bool
) -> LicenseNameId | None:
    """The first row whose upper-cased ID is *norm_input* (old)."""
    norm_upper = norm_input.upper()
    found = [
        row
        for row in rows
        if row["norm_license_id"].upper() == norm_upper
        and row["license_id"].endswith("+") == plus
    ]
    return found[0] if found else None


def live_names(rows: list[LicenseNameId]) -> set[str]:
    """The names of the rows in use (old)."""
    return {m["norm_name"] for m in rows if not m["is_deprecated"]}

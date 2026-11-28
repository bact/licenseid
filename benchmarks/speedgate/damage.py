# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Damaged copies of a side's database: what ``detect()`` answers on them
must equal what it answers on the intact build.

A damage applies where its table exists: the per-entry checks table is added
by task T6, so those two kinds are recorded as not applicable until then."""

import json
import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Final

Damage = Callable[[sqlite3.Connection], None]
#: Owners tried, in order, for the "regions changed" damage.
REGION_OWNERS: Final = ("BSD-3-Clause", "MIT", "ISC", "HPND", "Apache-2.0")
INTACT: Final = "none"


def _body(con: sqlite3.Connection, kind: str, owner: str | None = None) -> str:
    sql = "SELECT body FROM text_codes WHERE kind = ?"
    args: tuple[str, ...] = (kind,)
    if owner is not None:
        sql += " AND owner_id = ?"
        args += (owner,)
    row = con.execute(sql, args).fetchone()
    return str(row[0])


def _set_body(con: sqlite3.Connection, kind: str, owner: str, body: str) -> None:
    con.execute(
        "UPDATE text_codes SET body = ? WHERE kind = ? AND owner_id = ?",
        (body, kind, owner),
    )


def _swap_codes(con: sqlite3.Connection) -> None:
    body = _body(con, "text", "MIT")
    _set_body(con, "text", "MIT", body[1] + body[0] + body[2:])


def _change_text(con: sqlite3.Connection) -> None:
    row = con.execute(
        "SELECT search_text FROM license_index WHERE license_id = 'MIT'"
    ).fetchone()
    con.execute(
        "UPDATE license_index SET search_text = ? WHERE license_id = 'MIT'",
        (str(row[0]).replace("permission", "permision", 1),),
    )


def _swap_words(con: sqlite3.Connection) -> None:
    words = json.loads(_body(con, "words"))
    i, j = words.index("permission"), words.index("warranty")
    words[i], words[j] = words[j], words[i]
    con.execute(
        "UPDATE text_codes SET body = ? WHERE kind = 'words'",
        (json.dumps(words, separators=(",", ":")),),
    )


def region_owner(con: sqlite3.Connection) -> str:
    """The first owner of ``REGION_OWNERS`` with stored regions."""
    for owner in REGION_OWNERS:
        found = con.execute(
            "SELECT 1 FROM text_codes WHERE kind = 'textvars' AND owner_id = ?",
            (owner,),
        ).fetchone()
        if found:
            return owner
    raise LookupError("no stored regions")


def _move_regions(con: sqlite3.Connection) -> None:
    owner = region_owner(con)
    regions = json.loads(_body(con, "textvars", owner))
    regions[0][1] += 3
    _set_body(con, "textvars", owner, json.dumps(regions, separators=(",", ":")))


def _drop_codes(con: sqlite3.Connection) -> None:
    con.execute(
        "DELETE FROM text_codes WHERE kind = 'text' AND owner_id = 'Apache-2.0'"
    )


def _change_patterns(con: sqlite3.Connection) -> None:
    _set_body(con, "patterns", "", _body(con, "patterns").replace("a", "b", 1))


def _change_corpus_check(con: sqlite3.Connection) -> None:
    con.execute("UPDATE text_codes SET body = 'x' WHERE kind = 'check'")


def _change_entry_check(con: sqlite3.Connection) -> None:
    con.execute(
        "UPDATE text_code_checks SET digest = 'x' WHERE owner_id = 'BSD-3-Clause'"
    )


def _drop_checks(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE text_code_checks")


REFERENCE: Final = " [reference]"


def _change_text_and_drop_codes(con: sqlite3.Connection) -> None:
    """What an ``update`` would hold for the changed text: the codes follow
    the text (here: none stored, so they are built from the texts)."""
    _change_text(con)
    con.execute("DELETE FROM text_codes")


#: Name, damage, table it needs (empty: none beyond ``text_codes``).
KINDS: Final[tuple[tuple[str, Damage, str], ...]] = (
    (INTACT, lambda con: None, ""),
    ("codes of MIT changed", _swap_codes, ""),
    ("text of MIT changed, codes kept", _change_text, ""),
    ("codes of Apache-2.0 deleted", _drop_codes, ""),
    ("two words of the vocabulary swapped", _swap_words, ""),
    ("regions of one text changed", _move_regions, ""),
    ("patterns changed", _change_patterns, ""),
    ("check of the whole corpus changed", _change_corpus_check, ""),
    ("check of BSD-3-Clause changed", _change_entry_check, "text_code_checks"),
    ("no checks table", _drop_checks, "text_code_checks"),
)


#: Kinds whose right answer is not the intact build's: the damaged text is
#: the truth there, so they are judged against this reference copy.
REFERENCES: Final[dict[str, Damage]] = {
    "text of MIT changed, codes kept": _change_text_and_drop_codes,
}


def has_table(con: sqlite3.Connection, table: str) -> bool:
    """Whether the database has a table of this name."""
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def make_copies(source: Path, folder: Path) -> dict[str, Path | None]:
    """One damaged copy of *source* per kind in *folder*; None for a kind
    whose table the build does not have."""
    folder.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path | None] = {}
    for number, (name, damage, table) in enumerate(KINDS):
        target = folder / f"case{number}.db"
        shutil.copy(source, target)
        con = sqlite3.connect(target)
        try:
            if table and not has_table(con, table):
                out[name] = None
                continue
            damage(con)
            con.commit()
        finally:
            con.close()
        out[name] = target
    for name, damage in REFERENCES.items():
        target = folder / f"reference-{len(out)}.db"
        shutil.copy(source, target)
        con = sqlite3.connect(target)
        try:
            damage(con)
            con.commit()
        finally:
            con.close()
        out[name + REFERENCE] = target
    return out

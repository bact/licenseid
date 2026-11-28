# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The Versions set: the side on a database of the last tag, and the last
tag on the side's database (plan section 6.2, gate "Versions").

The side on a copy of the old database: every lookup (``detect``,
``resolve``, the ``is-*`` commands, the API) exits 2 with ``database: build
vN outdated`` and writes nothing (bytes, time, no ``-journal`` or ``-wal``
left); ``update`` then makes its tables and rows those of the side's own
build, and its answers the same; ``clear-cache`` deletes another copy.
``resolve()`` with no database given and the old file at the default path is
recorded as it is. The old tree on a copy of the side's database: every
command, ``update`` and ``clear-cache`` too, exits 2 with ``database:
invalid`` and writes nothing.

The old tree and database are ``<sides>/0.9.4`` and ``<db>/0.9.4/licenses.db``
beside the side's (``SPEEDGATE_OLD_SIDE``, ``SPEEDGATE_OLD_DB`` name others).
Both are copied, never written."""

import contextlib
import dataclasses
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Final

from benchmarks.speedgate.runner import CLI_BOOT, Job, Side
from benchmarks.speedgate.sidedb import DEAD_PROXY, BuildError, build_database

OLD: Final = "0.9.4"
MIT: Final = "Permission is hereby granted, free of charge, to any person"
API: Final = """
import sys, warnings
warnings.simplefilter("ignore")
import licenseid
path, call = sys.argv[1], sys.argv[2]
try:
    if call == "LicenseDetector":
        licenseid.LicenseDetector(path)
    elif call == "resolve(db=)":
        licenseid.resolve("MIT", db=path)
    elif call == "resolve()":
        print(licenseid.resolve("MIT")["lists"][0]["source"])
    else:
        print(licenseid.detect(license_id="MIT")[0]["expression"])
except licenseid.DatabaseNotReadyError as exc:
    sys.stderr.write(f"ERROR: {exc}\\n")
    sys.exit(2)
"""
LOOKUPS: Final = (
    ("detect", ["detect", "--text", MIT]),
    ("detect --id", ["detect", "--id", "MIT"]),
    ("resolve", ["resolve", "MIT"]),
    ("is-osi", ["is-osi", "MIT"]),
    ("is-fsf", ["is-fsf", "MIT"]),
    ("is-spdx", ["is-spdx", "MIT"]),
)
API_CALLS: Final = ("LicenseDetector", "resolve(db=)")
OLD_COMMANDS: Final = (
    *LOOKUPS,
    ("update", ["update"]),
    ("clear-cache", ["clear-cache"]),
)
ANSWERS: Final = (
    ["detect", "--verbose", "--text", MIT],
    ["detect", "--verbose", "--id", "GPL-2.0+"],
    ["resolve", "--verbose", "Apache 2.0"],
)
# Keys written with the time of a build: never the same twice.
TIMED: Final = ("last_check_datetime", "last_update_datetime", "text_postings_update")
OUTDATED: Final = re.compile(
    r"ERROR: database: build v\d+ outdated: current v\d+; run 'licenseid update'\n"
)


def old_paths(side: Side) -> tuple[Path, Path]:
    """The tree and the database of the last tag."""
    tree = os.environ.get("SPEEDGATE_OLD_SIDE") or side.path.parent / OLD
    db = (
        os.environ.get("SPEEDGATE_OLD_DB")
        or side.db.parent.parent / OLD / "licenses.db"
    )
    return Path(tree), Path(db)


def file_state(path: Path) -> dict[str, Any]:
    """The digest and time of *path*, and the names of the files beside it."""
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mtime_ns": path.stat().st_mtime_ns,
        "beside": sorted(p.name for p in path.parent.iterdir()),
    }


def _run(side: Side, args: list[str], code: str = CLI_BOOT) -> dict[str, Any]:
    """*code* run by the side's Python with *args*; no download can be made."""
    env = side.env()
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env[name] = DEAD_PROXY
    done = subprocess.run(
        [side.python, "-c", code, *args],
        env=env,
        cwd=str(side.home),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return {"rc": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


def _fresh_copy(source: Path, folder: Path) -> Path:
    """*source* copied alone into an empty *folder*."""
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    return Path(shutil.copy2(source, folder / "licenses.db"))


def _judged(side: Side, path: Path, calls: list[tuple[str, list[str]]]) -> list[Any]:
    """Each command and API call on *path*, with the file's state after it
    (each judged against the state before the first)."""
    out = []
    for name, args in calls:
        if name in API_CALLS:
            result = _run(side, [str(path), name], API)
        else:
            result = _run(side, ["--db", str(path), *args])
        out.append({"name": name, **result, "after": file_state(path)})
    return out


def _schema_and_rows(path: Path) -> dict[str, Any]:
    """Every object of *path* and its rows, but what a build writes with its
    time (the stamps and the checks made with it, whose owners are kept)."""
    with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
        objects = sorted(con.execute("SELECT type, name, sql FROM sqlite_master"))
        rows = {}
        for kind, name, _ in objects:
            if kind != "table":
                continue
            column = "owner_id" if name == "text_code_checks" else "*"
            found = con.execute(f'SELECT {column} FROM "{name}"').fetchall()
            if name == "db_metadata":
                found = [row for row in found if row[0] not in TIMED]
            rows[name] = hashlib.sha256(
                repr(sorted(found, key=repr)).encode()
            ).hexdigest()
    return {"objects": [list(o) for o in objects], "rows": rows}


def _answers(side: Side, path: Path) -> list[str]:
    return [_run(side, ["--db", str(path), *args])["stdout"] for args in ANSWERS]


def _default_resolve(side: Side, old_db: Path, scratch: Path) -> dict[str, Any]:
    """``resolve()`` with no database given, the old file at the default path."""
    home = scratch / "home"
    default = home / ".local" / "share" / "licenseid" / "licenses.db"
    default.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old_db, default)
    result = _run(dataclasses.replace(side, home=home), ["-", "resolve()"], API)
    return {**result, "unchanged": file_state(default)["sha256"] == _digest(old_db)}


def _digest(path: Path) -> str:
    return str(file_state(path)["sha256"])


def run_versions(side: Side, job: Job) -> dict[str, Any]:
    """The Versions set of *side* (module docstring)."""
    old_tree, old_db = old_paths(side)
    if not old_tree.is_dir() or not old_db.is_file():
        return {"error": f"no old side or database: {old_tree}, {old_db}"}
    scratch = job.scratch / "versions"
    on_old = _fresh_copy(old_db, scratch / "on-old")
    before = file_state(on_old)
    lookups = _judged(side, on_old, [*LOOKUPS, *((c, []) for c in API_CALLS)])
    updated = _fresh_copy(old_db, scratch / "updated")
    try:
        build_database(dataclasses.replace(side, db=updated), side.db.parent)
        update: dict[str, Any] = {"rc": 0}
    except BuildError as exc:
        update = {"rc": 1, "error": str(exc)[-400:]}
    update["same_tables"] = _schema_and_rows(updated) == _schema_and_rows(side.db)
    update["same_answers"] = _answers(side, updated) == _answers(side, side.db)
    cleared = _fresh_copy(old_db, scratch / "cleared")
    clear = _run(side, ["--db", str(cleared), "clear-cache"])
    clear["deleted"] = not cleared.exists()
    on_new = _fresh_copy(side.db, scratch / "on-new")
    new_before = file_state(on_new)
    old_side = Side(path=old_tree, db=on_new, home=side.home, python=side.python)
    return {
        "old_side": str(old_tree),
        "old_db": str(old_db),
        "new_on_old": {"before": before, "runs": lookups},
        "update": update,
        "clear_cache": clear,
        "default_resolve": _default_resolve(side, old_db, scratch),
        "old_on_new": {
            "path": str(on_new),
            "before": new_before,
            "runs": _judged(old_side, on_new, list(OLD_COMMANDS)),
        },
    }


def _left_alone(block: dict[str, Any]) -> bool:
    """Whether every run of *block* left the file as it was before them."""
    return all(run["after"] == block["before"] for run in block["runs"])


def problems(result: dict[str, Any]) -> list[str]:
    """What the Versions set found wrong; empty when the gate passes."""
    if "new_on_old" not in result:
        return [str(result.get("error", "versions set missing"))]
    found = [
        f"new on old {run['name']}: exit {run['rc']}, {run['stderr'].strip()[:80]!r}"
        for run in result["new_on_old"]["runs"]
        if run["rc"] != 2 or run["stdout"] or not OUTDATED.fullmatch(run["stderr"])
    ]
    if not _left_alone(result["new_on_old"]):
        found.append("new on old: the file changed")
    update = result["update"]
    if update["rc"] or not update["same_tables"] or not update["same_answers"]:
        found.append(f"update: {update}")
    if not result["clear_cache"]["deleted"] or result["clear_cache"]["rc"]:
        found.append("clear-cache: the file is still there")
    invalid = f"ERROR: database: invalid: {result['old_on_new']['path']}\n"
    found += [
        f"old on new {run['name']}: exit {run['rc']}, {run['stderr'].strip()[:80]!r}"
        for run in result["old_on_new"]["runs"]
        if run["rc"] != 2 or run["stdout"] or run["stderr"] != invalid
    ]
    if not _left_alone(result["old_on_new"]):
        found.append("old on new: the file changed")
    return found

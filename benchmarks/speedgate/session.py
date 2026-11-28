# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A run of one side over the chosen sets, written as a folder of results."""

import dataclasses
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Final

from benchmarks.speedgate import damage
from benchmarks.speedgate.buildinputs import read_inputs
from benchmarks.speedgate.model import DETECT_SETS
from benchmarks.speedgate.runner import (
    Job,
    Side,
    is_loaded,
    load_now,
    run_child,
    run_onecall,
    run_stress,
    timed,
)

ALL_SETS: Final = (
    *DETECT_SETS,
    "stress",
    "onecall",
    "damage",
    "memory",
    "threads",
)
META: Final = "meta.json"
STAMP: Final = "%Y-%m-%d %H:%M:%S"


def sha256(path: Path) -> str:
    """The digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gram_check(side: Side, job: Job) -> dict[str, Any]:
    """``gram_scores`` of fixed inputs on the side's database, and whether the
    file's bytes are the same after (a lookup never writes). A side without
    the postings tables gives nothing."""
    if not damage.has_postings(side.db):
        return {}
    before = sha256(side.db)
    result = run_child(side, job, ["grams", "--set", "damage"])
    same = sha256(side.db) == before
    if "tables" not in result:
        return {"grams_error": result.get("error", "no tables"), "bytes_same": same}
    return {"grams": result["tables"], "bytes_same": same}


def run_damage(side: Side, job: Job) -> dict[str, Any]:
    """The damage set on each damaged copy of the side's database."""
    start = load_now()
    copies = damage.make_copies(side.db, job.scratch / "damaged")
    out: dict[str, Any] = {}
    first: dict[str, Any] = {}
    for name, path in copies.items():
        if path is None:
            out[name] = {"applicable": False}
            continue
        on_copy = dataclasses.replace(side, db=path)
        result = run_child(on_copy, job, ["detect", "--set", "damage"])
        out[name] = {"applicable": True, **result, **gram_check(on_copy, job)}
        first = first or {k: v for k, v in result.items() if k != "cases"}
    end = load_now()
    return {
        **first,
        "kinds": out,
        "load_start": start,
        "load_end": end,
        "loaded": is_loaded(start, end),
    }


def core_job(job: Job) -> Job:
    """A job over a small inputs file with the core set only: the memory of a
    child must not hold every set of the full file (it is 40 MB of text)."""
    inputs = read_inputs(job.inputs)
    small = job.scratch / "core-inputs.json"
    small.write_text(
        json.dumps(
            {"digest": inputs["digest"], "sets": {"core": inputs["sets"]["core"]}}
        ),
        encoding="utf-8",
    )
    return dataclasses.replace(job, inputs=small)


def run_one(side: Side, name: str, job: Job) -> dict[str, Any]:
    """One set, whatever its kind."""
    if name == "onecall":
        return run_onecall(side, read_inputs(job.inputs)["onecall"], job)
    if name == "damage":
        return run_damage(side, job)
    if name == "stress":
        return run_stress(side, job)
    if name == "memory":
        return timed(side, core_job(job), ["memory"])
    if name == "threads":
        return timed(side, core_job(job), ["threads", "--items", str(job.items)])
    return timed(side, job, ["detect", "--set", name])


def run_side(
    side: Side, job: Job, out: Path, sets: list[str], force: bool = False
) -> None:
    """Run *sets* and write ``<out>/<set>.json`` for each, and ``meta.json``.
    A set whose file exists is skipped unless *force*."""
    out.mkdir(parents=True, exist_ok=True)
    job.scratch.mkdir(parents=True, exist_ok=True)
    digest = read_inputs(job.inputs)["digest"]
    meta = {
        "side": str(side.path),
        "db": str(side.db),
        "db_bytes": side.db.stat().st_size,
        "inputs_digest": digest,
        "load_start": load_now(),
        "started": time.strftime(STAMP),
    }
    for name in sets:
        target = out / f"{name}.json"
        if target.exists() and not force:
            continue
        result = run_one(side, name, job)
        result.update(set=name, side=str(side.path), inputs_digest=digest)
        target.write_text(json.dumps(result), encoding="utf-8")
        print(f"{name}: written ({result.get('error', 'ok')})", flush=True)
    meta.update(load_end=load_now(), finished=time.strftime(STAMP))
    (out / META).write_text(json.dumps(meta, indent=1), encoding="utf-8")

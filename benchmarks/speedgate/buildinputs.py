# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Make the inputs file: every set, as text, once. Both sides of a comparison
read the same file, so the inputs cannot differ between them."""

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from benchmarks.speedgate import (
    corpusdir,
    sets_core,
    sets_mixed,
    sets_roadmap,
    sets_synth,
)
from benchmarks.speedgate.model import Case, digest

INPUTS: Final = "inputs.json"
ONECALL_FILES: Final = (
    "real-MIT",
    "real-BSD-3-Clause",
    "real-Apache-2.0",
    "long-GPL-3.0",
    "short-tail-300",
    "distorted-10",
    "real-no-answer",
    "real-sbom-json",
)
ONECALL_COMMANDS: Final = (
    ("resolve ID", ["resolve", "@value:id"]),
    ("resolve expression", ["resolve", "@value:expr"]),
    ("detect ID value", ["detect", "@value:id"]),
    *((f"detect {name}", ["detect", f"@file:{name}"]) for name in ONECALL_FILES),
)


def load_core_text(path: Path) -> Callable[[str], str | None]:
    """``core_text`` of a ``coretext.py`` file (standard library only), read
    by path so that no tree is put on ``sys.path``."""
    spec = importlib.util.spec_from_file_location("speedgate_coretext", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    core: Callable[[str], str | None] = module.core_text
    return core


def onecall_spec(texts: dict[str, str]) -> dict[str, Any]:
    """The one-call set: the files, the values and the commands over them."""
    return {
        "files": {n: texts[n] for n in ONECALL_FILES},
        "values": {"id": texts["id"].strip(), "expr": texts["expr"].strip()},
        "commands": [{"name": n, "args": a} for n, a in ONECALL_COMMANDS],
    }


def build_inputs(
    folder: Path, fixtures: Path, tarball: Path, coretext: Path
) -> dict[str, Any]:
    """Every set of the benchmark from the corpus *folder*, the *fixtures* of a
    tree, a SPDX list tarball and a ``coretext.py``."""
    manifest = corpusdir.load_manifest(folder)
    core_of = load_core_text(coretext)
    real = corpusdir.read_entries(folder, "real")
    named = [(str(e["key"]), t) for e, t in corpusdir.read_entries(folder, "roadmap")]
    one = {str(e["key"]): t for e, t in corpusdir.read_entries(folder, "onecall")}
    real_files = [(str(e["key"]), t) for e, t in real]
    sets: dict[str, list[Case]] = {
        "core": sets_core.real_cases(real) + sets_core.fixture_cases(fixtures),
        "prose": sets_core.readme_cases(corpusdir.read_entries(folder, "readme"))
        + sets_core.notice_cases()
        + sets_mixed.mixed_cases(fixtures, one["real-no-answer"]),
        "many": sets_synth.many_cases(fixtures)
        + sets_synth.core_many_cases(fixtures, core_of),
        "cjk": sets_synth.cjk_cases(fixtures),
        "options": sets_synth.option_cases(fixtures),
        "roadmap": sets_roadmap.roadmap_cases(
            sets_roadmap.Sources(
                fixtures, tarball, core_of, real_files, named, manifest["item68"]
            )
        ),
        "stress": sets_synth.stress_cases(fixtures),
        "damage": sets_synth.damage_cases(fixtures),
    }
    labels = {
        str(e["key"]): e.get("ids") for e in manifest["files"] if e["kind"] == "real"
    }
    inputs: dict[str, Any] = {
        "format": 1,
        "sets": sets,
        "labels": labels,
        "onecall": onecall_spec(one),
    }
    inputs["digest"] = digest({"sets": sets, "labels": labels})
    inputs["counts"] = {name: len(cases) for name, cases in sets.items()}
    return inputs


def write_inputs(folder: Path, inputs: dict[str, Any]) -> Path:
    """Write the inputs file into the corpus folder."""
    target = folder / INPUTS
    target.write_text(json.dumps(inputs, ensure_ascii=False), encoding="utf-8")
    return target


def read_inputs(path: Path) -> dict[str, Any]:
    """An inputs file."""
    loaded: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return loaded


def sets_of(inputs: dict[str, Any], name: str) -> list[Case]:
    """The cases of one set."""
    cases: list[Case] = inputs["sets"][name]
    return cases

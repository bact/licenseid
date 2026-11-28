# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tiny fixtures and made-up results for the tests of the speed gate."""

import json
from pathlib import Path
from typing import Any

LONG_NAMES = [f"LIC-{n:02d}" for n in range(70)] + [
    "MIT",
    "Apache-2.0",
    "GPL-3.0-only",
    "BSD-3-Clause",
    "CC-BY-SA-2.1-JP",
    "GPL-2.0-only",
    "LGPL-2.1-only",
    "ISC",
    "MulanPSL-2.0",
    "MulanPSL-1.0",
    "Imlib2",
    "HPND",
]
LEVELS = ("01", "02", "05", "10", "20")


def write_fixtures(root: Path) -> Path:
    """A fixtures folder with 82 long and 50 short licences, each text a few
    made-up lines (the Han ones long enough to cut at 3,000 characters)."""
    (root / "license-text-long").mkdir(parents=True)
    (root / "license-text-short").mkdir()
    (root / "license-template").mkdir()
    for number, name in enumerate(LONG_NAMES):
        body = f"{name} says: permission is granted to use number {number}.\n" * 6
        if name in ("CC-BY-SA-2.1-JP", "MulanPSL-2.0", "MulanPSL-1.0"):
            body = "このソフトウェアを使用する許可を与える。\n" * 400
        data: dict[str, Any] = {
            "license_id": name,
            "license_text": body,
            "close_license_ids": ["JSON"],
        }
        for level in LEVELS:
            data[f"license_text_long_distorted_{level}"] = body.replace("a", "e", 3)
        (root / "license-text-long" / f"{name}.json").write_text(json.dumps(data))
    for name in LONG_NAMES[:50]:
        short = {
            f"license_text_short_{w}_{n}": f"{name} {w} {n}"
            for w in ("head", "tail")
            for n in (300, 700)
        }
        (root / "license-text-short" / f"{name}.json").write_text(
            json.dumps({"license_id": name, **short})
        )
    template = (
        "A <<beginOptional>>title <<endOptional>>text "
        '<<var;name="x";original="y";match=".+">> end.'
    )
    for name in ("LIC-01", "LIC-02", "LIC-03", "HPND"):
        (root / "license-template" / f"{name}.template.txt").write_text(template)
    return root


def core_of(template: str) -> str | None:
    """A stand-in for ``licenseid.coretext.core_text``: drop the title."""
    return template.replace("<<beginOptional>>title <<endOptional>>", "") or None


def row(expression: str, score: float = 1.0, exact: bool = True) -> list[Any]:
    """One result row as the worker writes it."""
    return [expression, score, "text", exact]


def case(
    cpu_ms: float, answer: str | None = "MIT", score: float = 1.0, texts: Any = None
) -> dict[str, Any]:
    """One measured case."""
    rows = [row(answer, score)] if answer else []
    return {
        "cpu_ms": cpu_ms,
        "rows": rows,
        "texts_row": [texts],
        "chars": 10,
    }


def result(cases: dict[str, dict[str, Any]], **more: Any) -> dict[str, Any]:
    """A set result with the identity fields a run records."""
    return {
        "cases": cases,
        "licenseid_file": "/side/src/licenseid/__init__.py",
        "licenseid_version": "0.0.0",
        "python": "3.10.0",
        "from_side": True,
        "inputs_digest": "d",
        "loaded": False,
        **more,
    }

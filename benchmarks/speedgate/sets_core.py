# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The core set and the prose set: real files, fixtures, READMEs, notices and
mixed inputs. Every builder is deterministic (fixed seeds)."""

import inspect
import json
import random
from pathlib import Path
from typing import Final

from benchmarks.speedgate.model import Case

LONG_MUST: Final = (
    "MIT",
    "Apache-2.0",
    "GPL-3.0-only",
    "BSD-3-Clause",
    "CC-BY-SA-2.1-JP",
    "GPL-2.0-only",
    "LGPL-2.1-only",
    "ISC",
)
SHORT_FIELDS: Final = (
    "license_text_short_head_300",
    "license_text_short_tail_300",
    "license_text_short_head_700",
    "license_text_short_tail_700",
)
FIXTURE_SEED: Final = 11
LONG_SAMPLE: Final = 60
SHORT_SAMPLE: Final = 40


def long_text(fixtures: Path, licence: str, field: str = "license_text") -> str:
    """One text of a long fixture: the clean text or a distortion field."""
    data = json.loads(
        (fixtures / "license-text-long" / f"{licence}.json").read_text("utf-8")
    )
    return str(data[field])


def fixture_cases(fixtures: Path) -> list[Case]:
    """408 long and 160 short fixtures: 68 licences (60 sampled and 8 named)
    clean and at five distortions, 40 licences with four fragments."""
    rnd = random.Random(FIXTURE_SEED)
    longs = sorted((fixtures / "license-text-long").glob("*.json"))
    picked = rnd.sample(longs, LONG_SAMPLE)
    for must in LONG_MUST:
        path = fixtures / "license-text-long" / f"{must}.json"
        if path not in picked and path.exists():
            picked.append(path)
    out: list[Case] = []
    for path in picked:
        data = json.loads(path.read_text("utf-8"))
        for field, value in data.items():
            if field == "license_text" or field.startswith(
                "license_text_long_distorted"
            ):
                level = (
                    "clean"
                    if field == "license_text"
                    else field[len("license_text_long_") :]
                )
                out.append(
                    {
                        "key": f"long:{data['license_id']}:{level}",
                        "text": value,
                        "kind": f"long:{level}",
                        "want": data["license_id"],
                    }
                )
    shorts = sorted((fixtures / "license-text-short").glob("*.json"))
    for path in rnd.sample(shorts, SHORT_SAMPLE):
        data = json.loads(path.read_text("utf-8"))
        for field in SHORT_FIELDS:
            if field in data:
                out.append(
                    {
                        "key": f"short:{data['license_id']}:{field[-8:]}",
                        "text": data[field],
                        "kind": "short",
                        "want": data["license_id"],
                    }
                )
    return out


def real_cases(entries: list[tuple[dict[str, object], str]]) -> list[Case]:
    """The real licence files, as the corpus manifest lists them."""
    return [
        {"key": str(e["key"]), "text": text, "kind": "real", "want": None}
        for e, text in entries
    ]


def readme_cases(entries: list[tuple[dict[str, object], str]]) -> list[Case]:
    """The README texts that hold the word "licens"."""
    return [
        {"key": f"readme:{e['key']}", "text": text, "kind": "readme", "want": None}
        for e, text in entries
    ]


def stdlib_prose() -> list[str]:
    """Neutral prose: documentation of standard library modules without the
    words licence or copyright, 450 words or more."""
    import argparse
    import bisect
    import csv
    import heapq
    import shlex
    import textwrap

    modules = (json, textwrap.TextWrapper, argparse, csv, heapq, bisect, shlex.shlex)
    words = " ".join(inspect.getdoc(m) or "" for m in modules).split()
    return [
        w for w in words if "licen" not in w.lower() and "copyright" not in w.lower()
    ]


NAMES: Final = [
    "MIT License",
    "the MIT license",
    "Apache License 2.0",
    "Apache License, Version 2.0",
    "the Apache Licence, Version 2.0",
    "BSD 3-Clause License",
    "the 3-clause BSD license",
    "GNU General Public License v3.0",
    "GNU General Public License version 2",
    "the GNU GPL, version 3 or later",
    "GNU Lesser General Public License v2.1",
    "GNU Affero General Public License v3.0",
    "Mozilla Public License 2.0",
    "Mozilla Publik License, version 2.0",
    "ISC License",
    "zlib License",
    "Eclipse Public License 2.0",
    "Boost Software License 1.0",
    "The Unlicense",
    "Creative Commons Zero v1.0 Universal",
    "Creative Commons Attribution 4.0 International",
    "Artistic License 2.0",
    "PostgreSQL License",
    "European Union Public License 1.2",
]
SHAPES: Final = {
    "sentence": "This software is distributed under the terms of {n}. See the "
    "LICENSE file in the root of the repository for the full text and conditions.",
    "readme": "{p1}\n\n## License\n\nThis project is licensed under {n} - see the "
    "LICENSE file for details.\n\n## Contributing\n\n{p2}",
    "header": "# Copyright (c) 2024 Example Authors. All rights reserved.\n# Use of "
    "this source code is governed by {n}\n# that can be found in the LICENSE "
    "file.\n\nimport os\nimport sys\n\n\ndef main():\n    print(os.getcwd(), "
    "sys.argv)\n",
    "long-prose": "{p1} {p2}\n\nLicense: {n}.\n\n{p3}",
}


def notice_cases() -> list[Case]:
    """96 notices: 24 licence names in four shapes (a sentence, a README
    section, a code header, a licence line in long prose), no licence text."""
    prose = stdlib_prose()
    parts = {
        "p1": " ".join(prose[:150]),
        "p2": " ".join(prose[150:300]),
        "p3": " ".join(prose[300:450]),
    }
    return [
        {
            "key": f"notice:{shape}:{name}",
            "text": template.format(n=name, **parts),
            "kind": "notice",
        }
        for name in NAMES
        for shape, template in SHAPES.items()
    ]

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The mixed inputs of the prose set: a text beside another text, inside
prose, as a code header or beside a tag."""

import random
from pathlib import Path
from typing import Final

from benchmarks.speedgate.model import Case
from benchmarks.speedgate.sets_core import long_text

IDS: Final = [
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "ISC",
    "GPL-2.0-only",
    "GPL-3.0-only",
    "LGPL-2.1-only",
    "MPL-2.0",
    "Zlib",
    "Unlicense",
    "CC0-1.0",
    "EPL-2.0",
    "BSL-1.0",
    "0BSD",
    "PostgreSQL",
    "Python-2.0",
    "AGPL-3.0-only",
    "LGPL-3.0-only",
    "Artistic-2.0",
]
TRIPLES: Final = (
    ("MIT", "BSD-3-Clause", "Apache-2.0"),
    ("ISC", "MIT", "BSD-2-Clause"),
    ("Zlib", "MIT", "ISC"),
    ("Apache-2.0", "MIT", "BSD-3-Clause"),
)
APACHE_HEADER: Final = (
    'Licensed under the Apache License, Version 2.0 (the "License"); you may not '
    "use this file except in compliance with the License. You may obtain a copy "
    "of the License at http://www.apache.org/licenses/LICENSE-2.0 Unless "
    "required by applicable law or agreed to in writing, software distributed "
    'under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR '
    "CONDITIONS OF ANY KIND, either express or implied. See the License for the "
    "specific language governing permissions and limitations under the License."
)
GPL_NOTICE: Final = (
    "This program is free software: you can redistribute it and/or modify it "
    "under the terms of the GNU General Public License as published by the Free "
    "Software Foundation, either version 3 of the License, or (at your option) "
    "any later version. This program is distributed in the hope that it will be "
    "useful, but WITHOUT ANY WARRANTY; without even the implied warranty of "
    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General "
    "Public License for more details."
)
CODE: Final = "\n".join(
    f"def step_{k}(value):\n    total = value * {k} + offset\n"
    f"    return [total, value - {k}]\n"
    for k in range(60)
)


def commented(text: str, mark: str) -> str:
    """*text* with *mark* before every line."""
    return "\n".join(mark + line for line in text.splitlines())


def mixed_cases(fixtures: Path, prose_text: str) -> list[Case]:
    """77 inputs: pairs and triples of texts, a text before, around or after
    prose, a text or a notice as a code header, a tag with a text. *prose_text*
    is a real file that names no licence (the one-call set's)."""
    present = [
        i for i in IDS if (fixtures / "license-text-long" / f"{i}.json").exists()
    ]
    texts = {i: long_text(fixtures, i) for i in present}
    words = prose_text.split()
    rnd = random.Random(5)
    cases: dict[str, str] = {}
    pairs = [(a, b) for a in present for b in present if a != b]
    rnd.shuffle(pairs)
    for a, b in pairs[:36]:
        cases[f"two:{a}+{b}"] = texts[a] + "\n\n" + "-" * 60 + "\n\n" + texts[b]
    for trio in TRIPLES:
        if all(x in texts for x in trio):
            cases["three:" + "+".join(trio)] = "\n\n=====\n\n".join(
                texts[x] for x in trio
            )
    for i in [
        x
        for x in ("MIT", "BSD-3-Clause", "ISC", "Apache-2.0", "Zlib", "BSD-2-Clause")
        if x in texts
    ]:
        cases[f"prose-before:{i}"] = (
            " ".join(words[:300]) + "\n\n## License\n\n" + texts[i]
        )
        cases[f"prose-around:{i}"] = (
            " ".join(words[:200])
            + "\n\n"
            + texts[i]
            + "\n\n"
            + " ".join(words[200:400])
        )
        cases[f"text-then-prose:{i}"] = texts[i] + "\n\n" + " ".join(words[:400])
    for i in [
        x for x in ("MIT", "BSD-3-Clause", "ISC", "Zlib", "BSD-2-Clause") if x in texts
    ]:
        for mark in ("# ", " * ", "// "):
            cases[f"code-header:{i}:{mark.strip()}"] = (
                commented(texts[i], mark) + "\n\n" + CODE
            )
    cases["code-header:Apache notice:#"] = (
        commented(APACHE_HEADER, "# ") + "\n\n" + CODE
    )
    cases["code-header:GPL notice://"] = commented(GPL_NOTICE, "// ") + "\n\n" + CODE
    cases["code-header:tag+MIT text"] = (
        "# SPDX-License-Identifier: MIT\n"
        + commented(texts["MIT"], "# ")
        + "\n\n"
        + CODE
    )
    cases["two:tag Apache + MIT text"] = (
        "SPDX-License-Identifier: Apache-2.0\n\n" + texts["MIT"]
    )
    return [
        {"key": f"mixed:{k}", "text": t, "kind": "mixed", "texts_call": True}
        for k, t in cases.items()
    ]

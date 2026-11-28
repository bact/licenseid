# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Sets made from List texts: many texts in one input, Han and kana text
wrapped at other widths, the options on whole texts, large and odd inputs."""

import importlib
import json
import pydoc
import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

from benchmarks.speedgate.model import Case
from benchmarks.speedgate.sets_core import long_text

MANY_COUNTS: Final = (2, 3, 5, 8, 10, 12, 15, 20, 25, 30, 40)
MANY_SEEDS: Final = 5
MANY_KINDS: Final = ("clean", "distorted_02", "distorted_05")
CORE_COUNTS: Final = (2, 3, 5, 7)
CJK_IDS: Final = ("CC-BY-SA-2.1-JP", "MulanPSL-2.0", "MulanPSL-1.0")
CJK_WIDTHS: Final = (20, 30, 40, 76)


def _field(kind: str) -> str:
    return "license_text" if kind == "clean" else f"license_text_long_{kind}"


def long_ids(fixtures: Path) -> list[str]:
    """The IDs of the long fixtures, sorted."""
    return sorted(p.stem for p in (fixtures / "license-text-long").glob("*.json"))


def many_cases(fixtures: Path) -> list[Case]:
    """165 inputs: 2 to 40 fixture texts joined by blank lines, five draws a
    count, clean and at 2 % and 5 % distortion. TEXTS comes from ``texts()``."""
    names = long_ids(fixtures)
    out: list[Case] = []
    for kind in MANY_KINDS:
        for count in MANY_COUNTS:
            for seed in range(MANY_SEEDS):
                ids = random.Random(1000 * count + seed).sample(names, count)
                text = "\n\n".join(long_text(fixtures, i, _field(kind)) for i in ids)
                out.append(
                    {
                        "key": f"many:{kind}:{count}:{seed}",
                        "text": text,
                        "kind": f"many:{kind}",
                        "texts_call": True,
                        "want": " ".join(ids),
                    }
                )
    return out


def core_many_cases(fixtures: Path, core_of: Callable[[str], str | None]) -> list[Case]:
    """18 inputs that hold cores: 12 of two to seven cores only, and 6 of
    cores of some licences with the whole texts of others. *core_of* gives
    the core of a template (``licenseid.coretext.core_text``)."""
    cores: dict[str, str] = {}
    for path in sorted((fixtures / "license-template").glob("*.template.txt")):
        core = core_of(path.read_text("utf-8"))
        if core:
            cores[path.name.removesuffix(".template.txt")] = core
    names = sorted(cores)
    out: list[Case] = []
    for count in CORE_COUNTS:
        for seed in range(3):
            ids = random.Random(7000 + 10 * count + seed).sample(
                names, min(count, len(names))
            )
            out.append(
                _joined(
                    f"cores:{count}:{seed}", "many:cores", [cores[i] for i in ids], ids
                )
            )
    others = [i for i in long_ids(fixtures) if i not in cores]
    for count in (4, 6, 8):
        for seed in range(2):
            rnd = random.Random(8000 + 10 * count + seed)
            ids = rnd.sample(names, count // 2) + rnd.sample(others, count - count // 2)
            parts = [cores[i] if i in cores else long_text(fixtures, i) for i in ids]
            out.append(_joined(f"coremix:{count}:{seed}", "many:coremix", parts, ids))
    return out


def _joined(key: str, kind: str, parts: list[str], ids: list[str]) -> Case:
    return {
        "key": f"many:{key}",
        "text": "\n\n".join(parts),
        "kind": kind,
        "texts_call": True,
        "want": " ".join(ids),
    }


def wrap(text: str, width: int) -> str:
    """*text* cut into lines of *width* characters."""
    return "\n".join(text[i : i + width] for i in range(0, len(text), width))


def cjk_cases(fixtures: Path) -> list[Case]:
    """24 inputs: three Han and kana licences as in the List, joined to one
    line, wrapped at 20, 30, 40 and 76 characters, and two fragments."""
    out: list[Case] = []
    for lid in CJK_IDS:
        text = long_text(fixtures, lid)
        flat = re.sub(r"\s*\n\s*", "", text)
        variants = {"as is": text, "lines joined": flat}
        variants.update({f"wrapped {n}": wrap(flat, n) for n in CJK_WIDTHS})
        variants["rewrapped 40, first 1500"] = wrap(flat[:1500], 40)
        variants["rewrapped 30, middle 1500"] = wrap(flat[1500:3000], 30)
        out.extend(
            {
                "key": f"cjk:{lid}:{name}",
                "text": value,
                "kind": "cjk",
                "texts_call": True,
            }
            for name, value in variants.items()
        )
    return out


OPTION_LICENCES: Final = (
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "ISC",
    "GPL-3.0-only",
    "Imlib2",
)


def option_cases(fixtures: Path) -> list[Case]:
    """36 inputs: six whole texts, each with no option, ``exclude`` of its
    own ID, ``exclude`` of it and a neighbour, ``only_common``, ``only_spdx``
    off, and a ``hint`` of a neighbour. TEXTS is read from the first row."""
    out: list[Case] = []
    for lid in OPTION_LICENCES:
        path = fixtures / "license-text-long" / f"{lid}.json"
        data = json.loads(path.read_text("utf-8"))
        neighbour = (data["close_license_ids"] or ["JSON"])[0]
        text = str(data["license_text"])
        options: dict[str, dict[str, object]] = {
            "none": {},
            "exclude self": {"exclude": [lid]},
            "exclude self and neighbour": {"exclude": [lid, neighbour]},
            "only_common": {"only_common": True},
            "only_spdx off": {"only_spdx": False},
            "hint neighbour": {"hint": [neighbour]},
        }
        out.extend(
            {
                "key": f"options:{lid}:{name}",
                "text": text,
                "kind": "options",
                "options": value,
                "texts_call": True,
            }
            for name, value in options.items()
        )
    return out


def _prose(chars: int) -> str:
    out: list[str] = []
    for name in [
        "argparse",
        "asyncio",
        "collections",
        "datetime",
        "decimal",
        "email",
        "fractions",
        "itertools",
        "logging",
        "os",
        "pathlib",
        "random",
        "shutil",
        "statistics",
        "string",
        "subprocess",
        "threading",
        "unittest",
        "urllib.request",
        "zipfile",
    ]:
        out.append(
            pydoc.render_doc(importlib.import_module(name), renderer=pydoc.plaintext)
        )
    text = "\n".join(out)
    return (text * (chars // len(text) + 1))[:chars]


def _shuffled(fixtures: Path, chars: int) -> str:
    names = long_ids(fixtures)
    random.Random(7).shuffle(names)
    words = " ".join(long_text(fixtures, i) for i in names[:60]).split()
    random.Random(3).shuffle(words)
    return " ".join(words)[:chars]


def stress_cases(fixtures: Path) -> list[Case]:
    """18 large or odd inputs. The prose is the standard library's own
    documentation, so it depends on the Python that builds the inputs; the
    text is stored in the inputs file, so both sides read the same."""
    ids = long_ids(fixtures)
    random.Random(7).shuffle(ids)

    def fx(lid: str) -> str:
        return long_text(fixtures, lid)

    def rep(lid: str, n: int) -> str:
        return "\n\n".join([fx(lid)] * n)

    mit = fx("MIT")
    texts = {
        "MIT x 50": rep("MIT", 50),
        "Apache-2.0 x 20": rep("Apache-2.0", 20),
        "GPL-3.0-only x 30 (1 MB)": rep("GPL-3.0-only", 30),
        "MulanPSL-2.0 x 100": rep("MulanPSL-2.0", 100),
        "20 licence texts joined": "\n\n".join(fx(i) for i in ids[:20]),
        "100 licence texts joined": "\n\n".join(fx(i) for i in ids[:100]),
        "prose 100 KB": _prose(100_000),
        "prose 1 MB": _prose(1_000_000),
        "prose 1 MB then MIT": _prose(1_000_000) + "\n\n" + mit,
        "licence words shuffled 1 MB": _shuffled(fixtures, 1_000_000),
        "one phrase x 50,000": "permission is hereby granted " * 50_000,
        "one token of 1 MB": "a" * 1_000_000,
        "MIT then one token of 1 MB": mit + "\n" + "a" * 1_000_000,
        "100,000 distinct words": " ".join(f"w{i}" for i in range(100_000)),
        "MIT on one line": " ".join(mit.split()),
        "MIT, a mark before every line": "\n".join(
            "// * " + line for line in mit.splitlines()
        ),
        "marks only, 200 KB": "/* -- == ** // ## */ " * 10_000,
        "kana prose 300 KB": "このソフトウェアはオープンソースです。" * 16_000,
    }
    return [
        {"key": f"stress:{k}", "text": t, "kind": "stress", "texts_call": True}
        for k, t in texts.items()
    ]


def damage_cases(fixtures: Path) -> list[Case]:
    """The texts a damaged database is asked about (the damage set)."""
    out: list[Case] = []
    for lid in ("MIT", "Apache-2.0", "BSD-3-Clause", "GPL-2.0-only", "HPND", "ISC"):
        out.append(
            {
                "key": f"damage:{lid}",
                "text": long_text(fixtures, lid),
                "kind": "damage",
                "texts_call": True,
            }
        )
    mit = long_text(fixtures, "MIT")
    apache = long_text(fixtures, "Apache-2.0")
    out.append(
        {
            "key": "damage:MIT, first half",
            "text": mit[:500],
            "kind": "damage",
            "texts_call": True,
        }
    )
    out.append(
        {
            "key": "damage:Apache-2.0 then MIT",
            "text": apache + "\n\n" + mit,
            "kind": "damage",
            "texts_call": True,
        }
    )
    return out

# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The inputs that the open items of the tech-debt roadmap name (11, 61, 64,
68, 69, 70), so that the release gate can answer them."""

import json
import random
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Final, NamedTuple

from benchmarks.speedgate.model import Case
from benchmarks.speedgate.sets_core import long_text

HOLDER: Final = "Marlowe-Quartermaine Brightwater Holdings International Incorporated"
TWO_LINES: Final = (
    f"Copyright (c) 2006-2024 {HOLDER}\nCopyright (c) 2025 {HOLDER} Foundation\n\n"
)
#: Licences whose right answer ranked 26 to 50 in the notice-free query
#: (item 61), and the neighbours that answered instead.
NOTICE_FREE: Final = (
    "0BSD",
    "ISC",
    "NTP",
    "MIT-testregex",
    "RHeCos-1.1",
    "BSD-ask-to-endorse",
)
GRANT: Final = (
    "\n\nMarkus Kuhn -- 2007-05-26 (Unicode 5.0)\n\nPermission to use, copy, "
    "modify, and distribute this software\nfor any purpose and without fee is "
    "hereby granted. The author\ndisclaims all warranties with regard to this "
    "software.\n"
)
TOKEN_CHARS: Final = "abcdefghijklmnopqrstuvwxyz0123456789"


def list_text(tarball: Path, licence: str) -> str:
    """The text of a licence in an SPDX ``license-list-data`` tarball."""
    suffix = f"/text/{licence}.txt"
    with tarfile.open(tarball) as tar:
        for member in tar:
            if member.name.endswith(suffix):
                extracted = tar.extractfile(member)
                if extracted is not None:
                    return extracted.read().decode("utf-8")
    raise KeyError(licence)


def without_title(text: str) -> str:
    """*text* without its first line."""
    return "\n".join(text.strip().splitlines()[1:])


def _case(key: str, text: str, kind: str = "roadmap") -> Case:
    return {"key": key, "text": text, "kind": kind, "texts_call": True}


def item_11(fixtures: Path) -> list[Case]:
    """A slice of Apache-2.0, and 200 words of it among random tokens."""
    apache = long_text(fixtures, "Apache-2.0")
    rnd = random.Random(1)

    def token() -> str:
        return "".join(rnd.choice(TOKEN_CHARS) for _ in range(25))

    words = apache.split()[300:500]
    noisy = " ".join(
        [token() for _ in range(60)] + words + [token() for _ in range(60)]
    )
    return [
        _case("11: Apache-2.0, 3,000-character slice from 2,000", apache[2000:5000]),
        _case(
            "11: 200 words of Apache-2.0 among 120 random 25-character tokens", noisy
        ),
    ]


def item_61(
    fixtures: Path, tarball: Path, core_of: Callable[[str], str | None]
) -> list[Case]:
    """MIT and HPND under copyright lines, the licences the notice-free query
    found at rank 26 to 50 under two copyright lines, and HPND's core."""
    mit = long_text(fixtures, "MIT")
    head = "Copyright (c) 2019 Jane Roe\nCopyright (c) 2021 Acme Inc.\n\n"
    body = mit.split("\n", 1)[1] if mit.lower().startswith("mit") else mit
    out = [
        _case("61: MIT under two copyright lines", head + body),
        _case(
            "61: HPND under a copyright line",
            "Copyright 1995 Acme Inc.\n\n" + long_text(fixtures, "HPND"),
        ),
    ]
    out.extend(
        _case(
            f"61: {name} under two copyright lines",
            TWO_LINES + without_title(list_text(tarball, name)),
        )
        for name in NOTICE_FREE
    )
    template = (fixtures / "license-template" / "HPND.template.txt").read_text("utf-8")
    core = core_of(template)
    if core:
        out.append(
            _case(
                "61: HPND core under a copyright line",
                "Copyright 1995 Acme Inc.\n\n" + core,
            )
        )
    return out


def item_68(
    fixtures: Path, files: list[tuple[str, str]], keys: list[str]
) -> list[Case]:
    """MIT with a grant after it, one line before MIT, the real files of the
    packages the roadmap names, and the real files item 68 asks about
    (*files* is every real file as ``(key, text)``)."""
    mit = long_text(fixtures, "MIT")
    out = [
        _case("68: MIT text, then a three-line grant", mit + GRANT),
        _case("68: one line, then the MIT text", "Mypy extensions\n\n" + mit),
    ]
    by_key = dict(files)
    out.extend(_case(f"68 file: {k}", by_key[k]) for k in keys if k in by_key)
    return out


def hpnd_family(fixtures: Path) -> list[Case]:
    """The HPND family of item 64: each whole text and its short fragments."""
    out: list[Case] = []
    for path in sorted((fixtures / "license-text-long").glob("*HPND*.json")):
        data = json.loads(path.read_text("utf-8"))
        out.append(_case(f"64 HPND: {path.stem} whole", data["license_text"]))
        short = fixtures / "license-text-short" / path.name
        if short.exists():
            fields = json.loads(short.read_text("utf-8"))
            out.extend(
                _case(
                    f"64 HPND: {path.stem} {name[len('license_text_short_') :]}",
                    fields[name],
                )
                for name in (
                    "license_text_short_head_300",
                    "license_text_short_tail_300",
                    "license_text_short_tail_700",
                )
                if name in fields
            )
    return out


class Sources(NamedTuple):
    """What the roadmap set is made from: the fixtures of a tree, a List
    tarball, ``core_text``, every real file as ``(key, text)``, the licence
    files of the named packages and the keys of item 68's real files."""

    fixtures: Path
    tarball: Path
    core_of: Callable[[str], str | None]
    real_files: list[tuple[str, str]]
    named_files: list[tuple[str, str]]
    item68: list[str]


def roadmap_cases(src: Sources) -> list[Case]:
    """Every roadmap input."""
    out = item_11(src.fixtures)
    out += item_61(src.fixtures, src.tarball, src.core_of)
    out += item_68(src.fixtures, src.real_files, src.item68)
    out += [_case(k, text) for k, text in src.named_files]
    return out + hpnd_family(src.fixtures)

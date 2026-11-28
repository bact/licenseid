# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The headers set: the standard licence header of each licence in use, from
the SPDX data archive (``json/details/<ID>.json``, ``standardLicenseHeader``),
in two forms.

``given``: the header as the List gives it. ``cut``: what a source file's
header would hold word for word, by these steps, in this order:

1. A pair of ``"`` or ``*`` wrapping the whole header is dropped (List markup).
2. A line that is a template instruction (it starts with ``<`` or with ``one
   line to give``) is dropped.
3. A copyright statement (a line whose first word after comment marks is
   ``Copyright`` or ``Portions Copyright``) is cut up to the end of its holder
   (``YOUR NAME``, ``[name of ...]``, ``All Rights Reserved.``) when the line
   goes on, else dropped whole.
4. A placeholder left (``[Software Name]``, ``<name>``, a run of ``___``)
   becomes the plain word ``Example``; ``[1]`` and ``<https://...>`` stay.
"""

import json
import re
import tarfile
from pathlib import Path
from typing import Final

from benchmarks.speedgate.model import Case

FORMS: Final = ("given", "cut")
PLACEHOLDER: Final = "Example"
DETAILS: Final = "/json/details/"
_COMMENT: Final = r"[\s%#*/;-]*"
_COPYRIGHT_LINE: Final = re.compile(
    rf"^{_COMMENT}(Portions\s+)?Copyright\b", re.IGNORECASE
)
_HOLDER_END: Final = re.compile(
    r"YOUR NAME\s*\.?|\[name of [^\]]*\]|All Rights Reserved\.?", re.IGNORECASE
)
_INSTRUCTION: Final = re.compile(rf"^{_COMMENT}(<|one line to give)", re.IGNORECASE)
_SQUARE: Final = re.compile(r"\[(?!\d+\])[^\]\n]*\]")
_ANGLE: Final = re.compile(r"<(?![a-z]+://)[^>\n]*>", re.IGNORECASE)
_BLANKS: Final = re.compile(r"_{3,}")


def _unwrapped(header: str) -> str:
    text = header.strip()
    for mark in ('"', "*"):
        if len(text) > 2 and text[0] == mark and text[-1] == mark:
            text = text[1:-1].strip()
    return text


def _cut_line(line: str) -> str | None:
    """A line as a file would hold it, or None when it is left out."""
    if _INSTRUCTION.match(line):
        return None
    if _COPYRIGHT_LINE.match(line):
        end = _HOLDER_END.search(line)
        rest = line[end.end() :].strip() if end else ""
        if not rest:
            return None
        line = rest
    for pattern in (_SQUARE, _ANGLE, _BLANKS):
        line = pattern.sub(PLACEHOLDER, line)
    return line


def cut(header: str) -> str:
    """The *header* as a source file would hold it (steps in the module
    docstring)."""
    kept = (_cut_line(line) for line in _unwrapped(header).split("\n"))
    return "\n".join(line for line in kept if line is not None).strip()


def read_headers(tarball: Path) -> list[tuple[str, str]]:
    """``(ID, header)`` of each licence that is not deprecated and has a
    header, by ID. The archive is read in memory, never extracted."""
    found: list[tuple[str, str]] = []
    with tarfile.open(tarball) as tar:
        for member in tar:
            if DETAILS not in member.name or not member.name.endswith(".json"):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            data = json.load(handle)
            header = (data.get("standardLicenseHeader") or "").strip()
            if header and not data.get("isDeprecatedLicenseId"):
                found.append((str(data["licenseId"]), header))
    return sorted(found)


def header_cases(tarball: Path) -> list[Case]:
    """Two cases a header: ``hdr:given:<ID>`` and ``hdr:cut:<ID>``."""
    cases: list[Case] = []
    for licence, header in read_headers(tarball):
        for form, text in zip(FORMS, (header, cut(header))):
            cases.append(
                {
                    "key": f"hdr:{form}:{licence}",
                    "text": text,
                    "kind": f"hdr:{form}",
                    "want": licence,
                }
            )
    return cases

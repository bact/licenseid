# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Logic for detecting explicit license markers and headings in text."""

import re

from licenseid.database import LicenseDatabase
from licenseid.types import CandidateMatch, LicenseDetails


class MarkerDetector:
    """
    Detector for license markers like SPDX-License-Identifier,
    License metadata fields, and headings.
    """

    # Deprecated SPDX License IDs (pre-2.0 naming) mapped to their canonical
    # successors.
    # Plain version (e.g. GPL-2.0) -> -only; "+" suffix -> -or-later.
    DEPRECATED_SPDX_LICENSE_IDS: dict[str, str] = {
        "GPL-1.0": "GPL-1.0-only",
        "GPL-2.0": "GPL-2.0-only",
        "GPL-3.0": "GPL-3.0-only",
        "LGPL-2.0": "LGPL-2.0-only",
        "LGPL-2.1": "LGPL-2.1-only",
        "LGPL-3.0": "LGPL-3.0-only",
        "AGPL-1.0": "AGPL-1.0-only",
        "AGPL-3.0": "AGPL-3.0-only",
        "GPL-1.0+": "GPL-1.0-or-later",
        "GPL-2.0+": "GPL-2.0-or-later",
        "GPL-3.0+": "GPL-3.0-or-later",
        "LGPL-2.0+": "LGPL-2.0-or-later",
        "LGPL-2.1+": "LGPL-2.1-or-later",
        "LGPL-3.0+": "LGPL-3.0-or-later",
        "AGPL-1.0+": "AGPL-1.0-or-later",
        "AGPL-3.0+": "AGPL-3.0-or-later",
    }

    # SPDX-License-Identifier tag.
    # Include "+" in the character class to capture deprecated or-later notation
    # (e.g. GPL-2.0+).  The regex stops before any whitespace, so compound
    # expressions like "GPL-2.0 WITH Linux-syscall-note" yield only "GPL-2.0".
    RE_SPDX = re.compile(
        r"SPDX-License-Identifier\s*[:=]\s*['\"]?([a-zA-Z0-9.+-]+)",
        re.IGNORECASE,
    )

    RE_LICENSE_FIELD = re.compile(
        r"license\s*[:=]\s*['\"]?([a-zA-Z0-9.,\s-]+)['\"]?", re.IGNORECASE
    )

    # Heading patterns
    RE_MD_HEADING = re.compile(
        r"^#+\s*Licens(?:e|ing)\s*$", re.MULTILINE | re.IGNORECASE
    )
    RE_UNDERLINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)\s*\n\s*[=\-*#]{3,}\s*$", re.MULTILINE | re.IGNORECASE
    )
    RE_BOX_HEADING = re.compile(
        r"^\s*[=\-*#]{3,}\s*\n\s*Licens(?:e|ing)\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    RE_LINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)\s*$", re.MULTILINE | re.IGNORECASE
    )

    # GPL/LGPL/AGPL copyright notice header detection.
    # Matches "GNU [Lesser|Library|Affero] General Public License".
    RE_GPL_FAMILY = re.compile(
        r"GNU\s+((?:Lesser|Library|Affero)\s+)?General\s+Public\s+License",
        re.IGNORECASE,
    )
    # Version number appearing in or near the license grant.
    # "either version 2" / "version 2.1" / "v3" etc.
    RE_GPL_VERSION = re.compile(
        r"(?:either\s+)?v(?:ersion)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    # "or later" signals within the license grant window.
    # "either version" alone implies "or any later version" in GPL boilerplate.
    RE_GPL_OR_LATER = re.compile(
        r"or\s+\(?at\s+your\s+option\)?\s+any\s+later\s+version"
        r"|\beither\s+version\b",
        re.IGNORECASE,
    )

    def __init__(self, db: LicenseDatabase):
        self.db = db

    def detect(self, text: str) -> list[CandidateMatch]:
        """Detect license markers in the given text, deduplicating by license_id."""
        seen: set[str] = set()
        result: list[CandidateMatch] = []

        for group in (
            self._detect_explicit_identifiers(text),
            self._detect_gpl_headers(text),
            self._detect_headings(text),
            self._detect_first_line(text),
        ):
            for c in group:
                lid = c["license_id"]
                if lid not in seen:
                    result.append(c)
                    seen.add(lid)

        return result

    def _detect_explicit_identifiers(self, text: str) -> list[CandidateMatch]:
        """Detect SPDX-License-Identifier tags and License: metadata fields."""
        candidates: list[CandidateMatch] = []

        # 1. SPDX-License-Identifier
        for match in self.RE_SPDX.finditer(text):
            lic_id = match.group(1).strip()
            details = self.db.get_license_details(lic_id)
            if not details:
                canonical = self.DEPRECATED_SPDX_LICENSE_IDS.get(lic_id)
                if canonical:
                    details = self.db.get_license_details(canonical)
            if details:
                candidates.append(self.to_candidate(details, 1.0))

        # 2. License metadata field (e.g. in package.json / pyproject.toml)
        for match in self.RE_LICENSE_FIELD.finditer(text):
            val = match.group(1).strip()
            if not val:
                continue
            details = self.db.get_license_details(val) or self.db.get_license_by_name(
                val
            )
            if not details:
                canonical = self.DEPRECATED_SPDX_LICENSE_IDS.get(val)
                if canonical:
                    details = self.db.get_license_details(canonical)
            if details:
                candidates.append(self.to_candidate(details, 0.95))

        return candidates

    def _detect_gpl_headers(self, text: str) -> list[CandidateMatch]:
        """Detect GPL/LGPL/AGPL standard copyright notice headers.

        Parses the recommended boilerplate from the GPL appendix, e.g.:
          'under the terms of the GNU General Public License ... either
           version 2 of the License, or (at your option) any later version.'

        Extracts the license family, version, and or-later flag to build
        a precise SPDX ID.  Score 0.92 for explicit or-later, 0.88 for -only.
        """
        candidates: list[CandidateMatch] = []
        seen: set[str] = set()

        for m in self.RE_GPL_FAMILY.finditer(text):
            modifier = (m.group(1) or "").strip().lower()

            # Search for the version number and or-later signal within a window
            # following the license name (300 chars covers the typical notice).
            window = text[m.start() : min(len(text), m.end() + 300)]

            ver_match = self.RE_GPL_VERSION.search(window)
            if not ver_match:
                continue

            version_str = ver_match.group(1)  # "2", "2.1", "3", etc.
            if "." not in version_str:
                version_str += ".0"

            or_later = bool(self.RE_GPL_OR_LATER.search(window))

            if "lesser" in modifier or "library" in modifier:
                family = "LGPL"
            elif "affero" in modifier:
                family = "AGPL"
            else:
                family = "GPL"

            suffix = "-or-later" if or_later else "-only"
            license_id = f"{family}-{version_str}{suffix}"

            if license_id in seen:
                continue

            details = self.db.get_license_details(license_id)
            if details:
                score = 0.92 if or_later else 0.88
                candidates.append(self.to_candidate(details, score))
                seen.add(license_id)

        return candidates

    def _detect_headings(self, text: str) -> list[CandidateMatch]:
        """Detect license headings and extract the license name on the next line."""
        candidates: list[CandidateMatch] = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if self._is_heading(line, i, lines):
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line or any(c in next_line for c in "=#*-"):
                        continue
                    details = self.db.get_license_details(
                        next_line
                    ) or self.db.get_license_by_name(next_line)
                    if details:
                        candidates.append(self.to_candidate(details, 0.9))
                        break
        return candidates

    def _is_heading(self, line: str, i: int, lines: list[str]) -> bool:
        """Helper to identify if a line is part of a license heading."""
        if self.RE_MD_HEADING.match(line) or self.RE_LINE_HEADING.match(line):
            return True
        if i + 1 < len(lines) and self.RE_UNDERLINE_HEADING.match(
            line + "\n" + lines[i + 1]
        ):
            return True
        if 0 < i < len(lines) - 1 and self.RE_BOX_HEADING.match(
            lines[i - 1] + "\n" + line + "\n" + lines[i + 1]
        ):
            return True
        return False

    def _detect_first_line(self, text: str) -> list[CandidateMatch]:
        """Check if the first non-empty line is a known license ID or name."""
        for line in text.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            details = self.db.get_license_details(
                clean_line
            ) or self.db.get_license_by_name(clean_line)
            if details:
                return [self.to_candidate(details, 0.85)]
            break
        return []

    def get_sections(self, text: str) -> list[str]:
        """Find sections of the text that likely contain license information."""
        sections: list[str] = []
        words = text.split()
        for i, word in enumerate(words):
            if "licens" in word.lower():
                start = max(0, i - 20)
                end = min(len(words), i + 100)
                sections.append(" ".join(words[start:end]))
        return sections

    def to_candidate(
        self, details: LicenseDetails, base_score: float
    ) -> CandidateMatch:
        """Convert LicenseDetails to CandidateMatch with search text from index."""
        return {
            "license_id": details["license_id"],
            "search_text": self.db.get_search_text(details["license_id"]),
            "score": base_score,
            "is_spdx": details.get("is_spdx", False),
            "is_high_usage": details.get("is_high_usage", False),
            "is_osi_approved": details.get("is_osi_approved", False),
            "is_fsf_libre": details.get("is_fsf_libre", False),
            "popularity_score": details.get("popularity_score", 0),
            "word_count": details.get("word_count", 0),
        }

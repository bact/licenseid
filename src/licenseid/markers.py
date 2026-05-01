# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Logic for detecting explicit license markers and headings in text."""

import re

from licenseid.database import LicenseDatabase, LicenseDetails
from licenseid.types import CandidateMatch


class MarkerDetector:
    """
    Detector for license markers like SPDX-License-Identifier,
    License metadata fields, and headings.
    """

    # Regex patterns
    RE_SPDX = re.compile(
        r"SPDX-License-Identifier\s*[:=]\s*['\"]?([a-zA-Z0-9.-]+)['\"]?",
        re.IGNORECASE,
    )
    RE_LICENSE_FIELD = re.compile(
        r"license\s*[:=]\s*['\"]?([a-zA-Z0-9.,\s-]+)['\"]?", re.IGNORECASE
    )

    # Heading patterns: look for License/Licensing followed by non-empty line
    # Markdown: ## License
    RE_MD_HEADING = re.compile(
        r"^#+\s*Licens(?:e|ing)\s*$", re.MULTILINE | re.IGNORECASE
    )

    # Underlined headings: License\n=======
    RE_UNDERLINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)\s*\n\s*[=\-*#]{3,}\s*$", re.MULTILINE | re.IGNORECASE
    )

    # Boxed headings: =======\nLicense\n=======
    RE_BOX_HEADING = re.compile(
        r"^\s*[=\-*#]{3,}\s*\n\s*Licens(?:e|ing)\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    # Simple line heading: License
    RE_LINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)\s*$", re.MULTILINE | re.IGNORECASE
    )

    def __init__(self, db: LicenseDatabase):
        self.db = db

    def detect(self, text: str) -> list[CandidateMatch]:
        """Detect license markers in the given text."""
        candidates: list[CandidateMatch] = []
        candidates.extend(self._detect_explicit_identifiers(text))
        candidates.extend(self._detect_headings(text))
        candidates.extend(self._detect_first_line(text))
        return candidates

    def _detect_explicit_identifiers(self, text: str) -> list[CandidateMatch]:
        """Detect SPDX identifiers and License: fields."""
        candidates: list[CandidateMatch] = []
        # 1. SPDX-License-Identifier
        for match in self.RE_SPDX.finditer(text):
            lic_id = match.group(1).strip()
            details = self.db.get_license_details(lic_id)
            if details:
                candidates.append(self._to_candidate(details, 1.0))

        # 2. License metadata field
        for match in self.RE_LICENSE_FIELD.finditer(text):
            val = match.group(1).strip()
            details = self.db.get_license_details(val) or self.db.get_license_by_name(
                val
            )
            if details:
                candidates.append(self._to_candidate(details, 0.95))
        return candidates

    def _detect_headings(self, text: str) -> list[CandidateMatch]:
        """Detect license headings and extract following license info."""
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
                        candidates.append(self._to_candidate(details, 0.9))
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
        """Check if the first non-empty line is a known license."""
        for line in text.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            details = self.db.get_license_details(
                clean_line
            ) or self.db.get_license_by_name(clean_line)
            if details:
                return [self._to_candidate(details, 0.85)]
            break
        return []

    def get_sections(self, text: str) -> list[str]:
        """Find sections of the text that likely contain license information."""
        sections: list[str] = []

        # Look for the word "License" or "Licensing"
        # and take a window around it.
        # This is a naive implementation, could be improved.
        words = text.split()
        for i, word in enumerate(words):
            if "licens" in word.lower():
                # Take a window around the keyword to capture names like "Apache License"
                start = max(0, i - 20)
                end = min(len(words), i + 100)
                sections.append(" ".join(words[start:end]))

        # Deduplicate overlapping sections for efficiency
        if not sections:
            return []

        # Overlapping sections are fine since the matcher deduplicates by license_id.
        return sections

    def _to_candidate(
        self, details: LicenseDetails, base_score: float
    ) -> CandidateMatch:
        """Convert LicenseDetails to CandidateMatch."""
        return {
            "license_id": details["license_id"],
            "search_text": "",  # Not needed for markers
            "score": base_score,
            "is_spdx": details.get("is_spdx", False),
            "is_high_usage": details.get("is_high_usage", False),
            "is_osi_approved": details.get("is_osi_approved", False),
            "is_fsf_libre": details.get("is_fsf_libre", False),
            "popularity_score": details.get("popularity_score", 0),
            "word_count": details.get("word_count", 0),
        }

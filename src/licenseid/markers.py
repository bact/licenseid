# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Logic for detecting explicit license markers and headings in text."""

import json
import os
import re
from typing import Optional

from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier
from licenseid.types import CandidateMatch, LicenseDetails


class MarkerDetector:
    """
    Detector for license markers like SPDX-License-Identifier,
    License metadata fields, and headings.
    """

    # SPDX-License-Identifier tag.
    # Capture full expressions including spaces, parentheses, and operators.
    # We stop at common delimiters like quotes or line breaks.
    RE_SPDX = re.compile(
        r"SPDX-License-Identifier\s*[:=]\s*['\"]?"
        r"([a-zA-Z0-9.+-]+(?:\s+(?:AND|OR|WITH)\s+[a-zA-Z0-9.+-]+"
        r"|\s*\([^)]+\)|[a-zA-Z0-9.+-]+)*)",
        re.IGNORECASE,
    )

    # Include + to handle SPDX-legacy notation like GPL-2.0+
    RE_LICENSE_FIELD = re.compile(
        r"license\s*[:=]\s*['\"]?([a-zA-Z0-9.+,\s-]+)['\"]?", re.IGNORECASE
    )

    # Heading patterns — allow optional words after "License/Licensing"
    # so "## License Agreement" and "## Licensing Information" both match.
    RE_MD_HEADING = re.compile(
        r"^#+\s*Licens(?:e|ing)(?:\s+\w+)*\s*$", re.MULTILINE | re.IGNORECASE
    )
    RE_UNDERLINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)(?:\s+\w+)*\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    RE_BOX_HEADING = re.compile(
        r"^\s*[=\-*#]{3,}\s*\n\s*Licens(?:e|ing)(?:\s+\w+)*\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    RE_LINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)(?:\s+\w+)*\s*$", re.MULTILINE | re.IGNORECASE
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

    # License mention patterns: "licensed under the MIT License",
    # "released under Apache License, Version 2.0", etc.
    # `\s+` (not `[ \t]+`) intentionally spans newlines so "licensed \nunder" matches.
    # Capture stops at end-of-line, opening paren, or sentence-terminating punctuation.
    RE_LICENSE_MENTION = re.compile(
        r"(?:licens(?:ed?|ing)|released?|distributed?)\s+under"
        r"(?:\s+the)?(?:\s+project'?s?)?"
        r"\s+([^\n;(]{2,100})",
        re.IGNORECASE,
    )

    def __init__(self, db: LicenseDatabase):
        self.db = db

    def detect(
        self, text: str, file_path: Optional[str] = None
    ) -> list[CandidateMatch]:
        """Detect license markers in the given text, deduplicating by license_id."""
        seen: set[str] = set()
        result: list[CandidateMatch] = []

        ext = os.path.splitext(file_path)[1].lower() if file_path else ""

        for group in (
            self._detect_structured_format(text, ext),
            self._detect_explicit_identifiers(text),
            self._detect_gpl_headers(text),
            self._detect_headings(text),
            self._detect_license_mentions(text),
            self._detect_first_line(text),
        ):
            for c in group:
                lid = c["license_id"]
                if lid not in seen:
                    result.append(c)
                    seen.add(lid)

        return result

    def _detect_structured_format(
        self, text: str, ext: str = ""
    ) -> list[CandidateMatch]:
        """Parse structured file formats (JSON, TOML, YAML, INI) for license fields."""
        candidates: list[CandidateMatch] = []
        stripped = text.strip()

        # JSON: parse with stdlib json — handles quoted keys like "license".
        # Use score=1.0 for DB-verified entries
        # (JSON is machine-readable, like SPDX tags).
        if ext == ".json" or (not ext and stripped.startswith(("{", "["))):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    val = (
                        data.get("license")
                        or data.get("License")
                        or data.get("LICENSE")
                    )
                    if isinstance(val, str) and val:
                        candidates.extend(self._resolve_license_value(val, 1.0))
            except (json.JSONDecodeError, ValueError):
                pass
            return candidates  # don't fall through to regex for JSON

        # TOML table format: license = {text = "MIT"} (PEP 621)
        if ext in (".toml", ""):
            toml_table = re.search(
                r'^license\s*=\s*\{[^}]*\btext\s*=\s*["\']([^"\']+)["\']',
                text,
                re.MULTILINE | re.IGNORECASE,
            )
            if toml_table:
                candidates.extend(
                    self._resolve_license_value(toml_table.group(1), 0.95)
                )

        # INI / cfg: use configparser for correct section-aware parsing
        if ext in (".cfg", ".ini", ""):
            try:
                import configparser  # stdlib, always available

                cfg = configparser.ConfigParser()
                cfg.read_string(text)
                for section in cfg.sections():
                    val = cfg.get(section, "license", fallback=None)
                    if val:
                        candidates.extend(
                            self._resolve_license_value(val.strip(), 0.95)
                        )
                        break
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        return candidates

    def _resolve_license_value(self, val: str, score: float) -> list[CandidateMatch]:
        """Resolve a license string (ID, name, or SPDX URL) to candidates."""
        # SPDX license URL: https://spdx.org/licenses/Apache-2.0
        if val.startswith("http") and "/licenses/" in val:
            val = val.rstrip("/").split("/")[-1]

        lic_id = normalize_identifier(val.strip(), self.db)
        if not lic_id:
            return []
        details = self.db.get_license_details(lic_id) or self.db.get_license_by_name(
            lic_id
        )
        if details:
            return [self.to_candidate(details, score)]
        return [
            {
                "license_id": lic_id,
                "search_text": "",
                "score": score,
                "is_spdx": True,
                "word_count": 0,
                "is_high_usage": False,
                "is_osi_approved": False,
                "is_fsf_libre": False,
                "pop_score": 0,
            }
        ]

    def _detect_explicit_identifiers(self, text: str) -> list[CandidateMatch]:
        """Detect SPDX-License-Identifier tags and License: metadata fields."""
        candidates: list[CandidateMatch] = []

        # 1. SPDX-License-Identifier
        for match in self.RE_SPDX.finditer(text):
            lic_id = normalize_identifier(match.group(1).strip(), self.db)
            details = self.db.get_license_details(lic_id)
            if details:
                candidates.append(self.to_candidate(details, 1.0))
            elif lic_id:
                # Even if not in DB, if it's a valid expression we can return it
                # with a placeholder candidate
                candidates.append(
                    {
                        "license_id": lic_id,
                        "search_text": "",
                        "score": 1.0,
                        "is_spdx": True,
                        "word_count": 0,
                        "is_high_usage": False,
                        "is_osi_approved": False,
                        "is_fsf_libre": False,
                        "pop_score": 0,
                    }
                )

        # 2. License metadata field (e.g. in package.json / pyproject.toml)
        for match in self.RE_LICENSE_FIELD.finditer(text):
            val = normalize_identifier(match.group(1).strip(), self.db)
            if not val:
                continue
            details = self.db.get_license_details(val) or self.db.get_license_by_name(
                val
            )
            if details:
                candidates.append(self.to_candidate(details, 0.95))
            elif val:
                candidates.append(
                    {
                        "license_id": val,
                        "search_text": "",
                        "score": 0.95,
                        "is_spdx": True,
                    }
                )

        return candidates

    def _detect_gpl_headers(self, text: str) -> list[CandidateMatch]:
        """Detect GPL/LGPL/AGPL standard copyright notice headers."""
        candidates: list[CandidateMatch] = []
        seen: set[str] = set()

        # Find the start of the appendix if it exists
        appendix_start = text.find("How to Apply These Terms to Your New Programs")
        # Find Section 9 (GPL-2.0) or Section 14 (GPL-3.0) which explains "or later"
        # without being a grant itself.
        terms_explanation = text.find(
            "specifies a version number of this License which applies to it "
            'and "any later version"'
        )
        if terms_explanation == -1:
            # GPL-3.0 phrasing
            terms_explanation = text.find(
                "specifies that a certain numbered version of the GNU "
                "General Public License"
            )

        for m in self.RE_GPL_FAMILY.finditer(text):
            modifier = (m.group(1) or "").strip().lower()

            # Search for the version number and or-later signal within a window
            # following the license name (1000 chars covers the typical notice).
            window_end = min(len(text), m.end() + 1000)
            window = text[m.start() : window_end]

            ver_match = self.RE_GPL_VERSION.search(window)
            if not ver_match:
                continue

            version_str = ver_match.group(1)  # "2", "2.1", "3", etc.
            if "." not in version_str:
                version_str += ".0"

            or_later = bool(self.RE_GPL_OR_LATER.search(window))

            # Logic for appendix/terms: if the match is in a section that explains
            # "or later" but is not the grant itself, ignore the signal.
            if or_later:
                # 1. Check Appendix
                if appendix_start != -1 and m.start() > appendix_start:
                    if "one line to give the program's name" in window.lower():
                        or_later = False

                # 2. Check Terms Explanation (Section 9/14)
                if or_later and terms_explanation != -1:
                    # If the match is within a reasonable distance of the terms
                    # explanation (e.g. within the same paragraph),
                    # it's likely just the terms.
                    if abs(m.start() - terms_explanation) < 500:
                        or_later = False

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
        """Detect license headings and extract the license name from nearby lines."""
        candidates: list[CandidateMatch] = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if self._is_heading(line, i, lines):
                search_lines = lines[i + 1 : min(i + 6, len(lines))]
                details = self._extract_license_from_lines(search_lines)
                if details:
                    candidates.append(self.to_candidate(details, 0.9))
        return candidates

    def _extract_license_from_lines(self, lines: list[str]) -> Optional[LicenseDetails]:
        """Try to identify a license from a block of lines near a heading."""
        cleaned = [line.strip() for line in lines]

        def _try(text: str) -> Optional[LicenseDetails]:
            # Skip decorative separator lines (all "=", "-", "*", "#", or space)
            if not text or re.match(r"^[=\-*#\s]+$", text):
                return None
            # 1. Direct lookup
            details = self.db.get_license_details(text) or self.db.get_license_by_name(
                text
            )
            if details:
                return details
            # 2. Name variants (ID normalisation, suffix stripping)
            details = self._try_license_lookup(text)
            if details:
                return details
            # 3. Extract "under X License" mention from the line
            mention = self._extract_mentioned_license(text)
            if mention:
                return self._try_license_lookup(mention)
            return None

        for line in cleaned:
            result = _try(line)
            if result:
                return result

        # Also try adjacent-line pairs (handles wrapped "licensed \\nunder" sentences)
        for i in range(len(cleaned) - 1):
            joined = cleaned[i] + " " + cleaned[i + 1]
            result = _try(joined)
            if result:
                return result

        return None

    def _extract_mentioned_license(self, text: str) -> Optional[str]:
        """Extract and clean a license name/ID from 'under the X License' pattern."""
        m = self.RE_LICENSE_MENTION.search(text)
        if not m:
            return None
        # Truncate at sentence boundary then clean
        candidate = re.split(r"\.\s", m.group(1), maxsplit=1)[0].strip().rstrip(".,; ")
        candidate = re.sub(r"\bproject'?s?\s+", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s+Licen[sc]e[s]?\s*$", "", candidate, flags=re.IGNORECASE)
        return candidate.strip() if candidate.strip() else None

    def _try_license_lookup(self, name: str) -> Optional[LicenseDetails]:
        """Try multiple name/ID variants to resolve a license mention."""
        for candidate in self._name_variants(name):
            details = self.db.get_license_details(
                candidate
            ) or self.db.get_license_by_name(candidate)
            if details:
                return details
        return None

    def _name_variants(self, name: str) -> list[str]:
        """Generate lookup variants for a captured license name/ID."""
        variants = [name, name + " License", name + " Licence"]
        # "Apache License, Version 2.0" → "Apache License 2.0"
        no_version_word = re.sub(
            r",?\s*Version\s+", " ", name, flags=re.IGNORECASE
        ).strip()
        if no_version_word != name:
            variants += [no_version_word, no_version_word + " License"]
        # "Mozilla Public License v2.0" → "Mozilla Public License 2.0"
        stripped_v = re.sub(r"\bv(\d)", r"\1", name, flags=re.IGNORECASE)
        if stripped_v != name:
            variants += [stripped_v, stripped_v + " License"]
            no_v_no_ver = re.sub(
                r",?\s*Version\s+", " ", stripped_v, flags=re.IGNORECASE
            ).strip()
            if no_v_no_ver != stripped_v:
                variants += [no_v_no_ver, no_v_no_ver + " License"]
        # "MIT License" → also try bare "MIT"
        if name.lower().endswith(" license"):
            variants.append(name[:-8].strip())
        # "GPL License version 3.0 or any version later" → "GPL-3.0-or-later"
        gpl_m = re.search(
            r"\b(GPL|LGPL|AGPL)\s+(?:License\s+)?(?:version\s+)?v?(\d+(?:\.\d+)?)",
            name,
            re.IGNORECASE,
        )
        if gpl_m:
            family = gpl_m.group(1).upper()
            ver = gpl_m.group(2)
            if "." not in ver:
                ver += ".0"
            or_later = bool(
                re.search(r"or\s+(?:\w+\s+){0,2}(?:later|newer)\b", name, re.IGNORECASE)
            )
            gpl_id = f"{family}-{ver}-{'or-later' if or_later else 'only'}"
            variants.append(gpl_id)
        return variants

    def _detect_license_mentions(self, text: str) -> list[CandidateMatch]:
        """Detect 'licensed under X License' style mentions in plain text.

        Joins soft-wrapped lines (single \\n → space) first so "licensed \\nunder"
        and "Mozilla\\nPublic License" are treated as one phrase.
        """
        # Soft line-join: replace single newlines (not paragraph breaks) with a space
        joined = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        candidates: list[CandidateMatch] = []
        seen: set[str] = set()
        for m in self.RE_LICENSE_MENTION.finditer(joined):
            # Truncate at sentence boundary (". " ends the license name phrase)
            raw = re.split(r"\.\s", m.group(1), maxsplit=1)[0].strip().rstrip(".,; ")
            raw = re.sub(r"\bproject'?s?\s+", "", raw, flags=re.IGNORECASE)
            # Try with and without trailing "License" word
            core = re.sub(
                r"\s+Licen[sc]e[s]?\s*$", "", raw, flags=re.IGNORECASE
            ).strip()
            details = self._try_license_lookup(core) or self._try_license_lookup(raw)
            if details and details["license_id"] not in seen:
                candidates.append(self.to_candidate(details, 0.92))
                seen.add(details["license_id"])
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
            "pop_score": details.get("pop_score", 0),
            "word_count": details.get("word_count", 0),
        }

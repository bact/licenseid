# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Logic for detecting explicit license markers and headings in text."""

import configparser
import json
import os
import re

import py_spdx_license

from licenseid.classify import OR_LATER_PHRASE
from licenseid.database import LicenseDatabase
from licenseid.identifiers import (
    flag_source,
    normalize_identifier,
    parse_expression,
    strip_plus_operator,
)
from licenseid.types import CandidateMatch, LicenseDetails


class MarkerDetector:
    """
    Detector for license markers like SPDX-License-Identifier,
    License metadata fields, and headings.
    """

    # SPDX-License-Identifier tag.
    # Capture full expressions including spaces, parentheses, and operators.
    # We stop at common delimiters like quotes or line breaks.
    _RE_SPDX = re.compile(
        r"SPDX-License-Identifier\s*[:=]\s*['\"]?"
        r"([a-zA-Z0-9.+-]+(?:\s+(?:AND|OR|WITH)\s+[a-zA-Z0-9.+-]+"
        r"|\s*\([^)]+\)|[a-zA-Z0-9.+-]+)*)",
        re.IGNORECASE,
    )

    # Include + to handle SPDX-legacy notation like GPL-2.0+
    # Use [ \t]* (not \s*) to prevent matching across line breaks.
    _RE_LICENSE_FIELD = re.compile(
        r"license[ \t]*[:=][ \t]*['\"]?([a-zA-Z0-9.+, \t-]+)['\"]?", re.IGNORECASE
    )

    # Heading patterns — allow optional words after "License/Licensing"
    # so "## License Agreement" and "## Licensing Information" both match.
    _RE_MD_HEADING = re.compile(
        r"^#+\s*Licens(?:e|ing)(?:\s+\w+)*\s*$", re.MULTILINE | re.IGNORECASE
    )
    _RE_UNDERLINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)(?:\s+\w+)*\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    _RE_BOX_HEADING = re.compile(
        r"^\s*[=\-*#]{3,}\s*\n\s*Licens(?:e|ing)(?:\s+\w+)*\s*\n\s*[=\-*#]{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    _RE_LINE_HEADING = re.compile(
        r"^\s*Licens(?:e|ing)(?:\s+\w+)*\s*$", re.MULTILINE | re.IGNORECASE
    )

    # Font-exception-2.0: "As a special exception...embed this font..."
    _RE_FONT_EXCEPTION = re.compile(
        r"as\s+a\s+special\s+exception.{0,400}embed\s+this\s+font",
        re.IGNORECASE | re.DOTALL,
    )

    # GPL/LGPL/AGPL copyright notice header detection.
    # Matches "GNU [Lesser|Library|Affero] General Public License".
    _RE_GPL_FAMILY = re.compile(
        r"GNU\s+((?:Lesser|Library|Affero)\s+)?General\s+Public\s+License",
        re.IGNORECASE,
    )
    # Version number appearing in or near the license grant.
    # "either version 2" / "version 2.1" / "v3" etc.
    _RE_GPL_VERSION = re.compile(
        r"(?:either\s+)?v(?:ersion)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    # "or later" signals within the license grant window: the phrases every
    # other reader uses (classify.OR_LATER_PHRASE), so a header reads the same
    # here as in the tie-breaker. "either version" alone implies "or any later
    # version" in GPL boilerplate.
    _RE_GPL_OR_LATER = re.compile(
        OR_LATER_PHRASE.pattern + r"|\beither\s+version\b", re.IGNORECASE
    )

    # PEP 621 table form: license = {text = "MIT"}
    _RE_TOML_LICENSE_TABLE = re.compile(
        r'^license\s*=\s*\{[^}]*\btext\s*=\s*["\']([^"\']+)["\']',
        re.MULTILINE | re.IGNORECASE,
    )

    # License mention patterns: "licensed under the MIT License",
    # "released under Apache License, Version 2.0", etc.
    # `\s+` (not `[ \t]+`) intentionally spans newlines so "licensed \nunder" matches.
    # Capture stops at end-of-line, opening paren, or sentence-terminating punctuation.
    _RE_LICENSE_MENTION = re.compile(
        r"(?:licens(?:ed?|ing)|released?|distributed?)\s+under"
        r"(?:\s+the)?(?:\s+project'?s?)?"
        r"\s+([^\n;(]{2,100})",
        re.IGNORECASE,
    )

    def __init__(self, db: LicenseDatabase):
        self.db = db

    def detect(self, text: str, file_path: str | None = None) -> list[CandidateMatch]:
        """Detect license markers in the given text, deduplicating by license_id."""
        seen: set[str] = set()
        result: list[CandidateMatch] = []

        ext = os.path.splitext(file_path)[1].lower() if file_path else ""

        for group in (
            self._detect_structured_format(text, ext),
            self._detect_explicit_identifiers(text),
            self._detect_gpl_headers(text),
            self._detect_bsd_headers(text),
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
        """Parse structured file formats (JSON, TOML, INI) for license fields."""
        stripped = text.strip()

        is_json_ext = ext == ".json"
        if is_json_ext or (not ext and stripped.startswith(("{", "["))):
            found = self._detect_json_license(stripped)
            if found is not None:
                return found  # valid JSON: don't fall through to regex/INI
            if is_json_ext:
                return []
            # Extensionless "[section]" text is INI/TOML, not JSON: fall through.

        candidates: list[CandidateMatch] = []
        if ext in (".toml", ""):
            candidates.extend(self._detect_toml_license(text))
        if ext in (".cfg", ".ini", ""):
            candidates.extend(self._detect_ini_license(text))
        return candidates

    def _detect_json_license(self, stripped: str) -> list[CandidateMatch] | None:
        """Read the license field of a JSON object.

        Returns None if the text is not parseable JSON, so the caller can
        decide whether to fall through. Scores 1.0 (JSON is machine-readable,
        like SPDX tags), higher than the 0.95 of TOML/INI.
        """
        try:
            data = json.loads(stripped)
        except (ValueError, RecursionError):  # JSONDecodeError is a ValueError
            return None
        if not isinstance(data, dict):
            return []
        val = data.get("license") or data.get("License") or data.get("LICENSE")
        if isinstance(val, str) and val:
            return self._resolve_license_value(val, 1.0)
        return []

    def _detect_toml_license(self, text: str) -> list[CandidateMatch]:
        """Read the PEP 621 table form: license = {text = "MIT"}."""
        match = self._RE_TOML_LICENSE_TABLE.search(text)
        if match:
            return self._resolve_license_value(match.group(1), 0.95)
        return []

    def _detect_ini_license(self, text: str) -> list[CandidateMatch]:
        """Read the first INI/cfg section whose license option resolves."""
        try:
            cfg = configparser.ConfigParser()
            cfg.read_string(text)
            for section in cfg.sections():
                val = cfg.get(section, "license", fallback=None)
                if val:
                    resolved = self._resolve_license_value(val.strip(), 0.95)
                    if resolved:
                        return resolved
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return []

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
        return self._synthetic_candidate(lic_id, score)

    def _synthetic_candidate(self, lic_id: str, score: float) -> list[CandidateMatch]:
        """Build a candidate for an ID that is not in the DB.

        Keeps only well-formed SPDX expressions and LicenseRef-* IDs with at
        least one recognised ID: fabricating a candidate from arbitrary text
        (e.g. "see LICENSE file", "Dual OR Commercial") would create a
        phantom license_id ranked at a fixed high confidence. ``is_spdx`` is
        False if any part is unknown; a LicenseRef-* is a valid SPDX ID, so it
        counts as known. Used for every source of an expression
        (SPDX tag, JSON, TOML, INI), so they all decide alike. The OSI and FSF
        flags come from ``identifiers.flag_source``.
        """
        tree = parse_expression(strip_plus_operator(lic_id))
        if tree is None:
            return []  # not an expression (or too deep to parse)
        leaves = self._expression_leaves(tree)
        if not any(
            isinstance(leaf, (py_spdx_license.LicenseId, py_spdx_license.LicenseRef))
            for leaf in leaves
        ):
            return []
        licence = flag_source(tree, self.db)
        return [
            {
                "license_id": lic_id,
                "search_text": "",
                "score": score,
                "is_spdx": not any(
                    isinstance(leaf, py_spdx_license.UnknownId) for leaf in leaves
                ),
                "word_count": 0,
                "is_high_usage": False,
                "is_osi_approved": bool(licence and licence["is_osi_approved"]),
                "is_fsf_libre": bool(licence and licence["is_fsf_libre"]),
                "pop_score": 0,
            }
        ]

    @classmethod
    def _expression_leaves(
        cls, node: py_spdx_license.Node
    ) -> list[py_spdx_license.Node]:
        """Identifier nodes of a parsed SPDX expression."""
        if isinstance(node, py_spdx_license.Identifier):
            return [node]
        return [
            leaf for child in node.children for leaf in cls._expression_leaves(child)
        ]

    def _detect_explicit_identifiers(self, text: str) -> list[CandidateMatch]:
        """Detect SPDX-License-Identifier tags and License: metadata fields."""
        candidates: list[CandidateMatch] = []

        # 1. SPDX-License-Identifier
        for match in self._RE_SPDX.finditer(text):
            lic_id = normalize_identifier(match.group(1).strip(), self.db)
            details = self.db.get_license_details(lic_id)
            if details:
                candidates.append(self.to_candidate(details, 1.0))
            elif lic_id:
                # An expression (or LicenseRef-*) has no row of its own; a
                # value with no recognised ID (a typo, free text) is no
                # evidence of a license and builds no candidate.
                candidates.extend(self._synthetic_candidate(lic_id, 1.0))

        # 2. License metadata field (e.g. in package.json / pyproject.toml)
        for match in self._RE_LICENSE_FIELD.finditer(text):
            val = normalize_identifier(match.group(1).strip(), self.db)
            if not val:
                continue
            details = self.db.get_license_details(val) or self.db.get_license_by_name(
                val
            )
            if details:
                candidates.append(self.to_candidate(details, 0.95))
            # No fallback when val doesn't resolve to a known license: a
            # "license:"/"license="-shaped substring can appear incidentally
            # (e.g. "ISC License: Copyright (c) ..." captures "Copyright" as
            # the field value) — fabricating a candidate from an unresolved
            # value produces a phantom license_id that isn't in the database
            # at all, ranked at a fixed high confidence.

        return candidates

    def _resolve_gpl_or_later(
        self,
        text: str,
        window_end: int,
        appendix_start: int,
        terms_explanation: int,
        match_start: int,
    ) -> bool:
        """Detect the raw "or later" signal within the grant's lookahead
        window, then suppress it if the match falls in the GPL appendix's
        sample notice or near the license's own explanation of the "or
        later" wording (Section 9/14) — both mention the phrase without
        being an actual grant."""
        window = text[match_start:window_end]
        or_later = bool(self._RE_GPL_OR_LATER.search(window))
        if not or_later:
            return False

        # 1. Check Appendix
        # The canonical GPL appendix places a "<one line to give the
        # program's name...>" placeholder, then a "Copyright (C) <year>
        # <name of author>" line, then the grant sentence — in that
        # order, ~220 chars apart in the actual upstream text (measured
        # directly against the real GPL-2.0 appendix). Require BOTH
        # anchors, in that order, within a tight backward-only window:
        # the placeholder alone is too generic to trust on its own — a
        # document can legitimately quote it elsewhere (e.g. contributor
        # guidance on how to license new code) while stating its own,
        # separate, real or-later grant nearby, and a placeholder-only
        # check would wrongly suppress that real grant.
        if appendix_start != -1 and match_start > appendix_start:
            lookback_start = max(appendix_start, match_start - 300)
            preceding = text[lookback_start:match_start].lower()
            placeholder_pos = preceding.find("one line to give the program's name")
            if placeholder_pos != -1 and "copyright (c" in preceding[placeholder_pos:]:
                return False

        # 2. Check Terms Explanation (Section 9/14)
        # If the match is within a reasonable distance of the terms
        # explanation (e.g. within the same paragraph), it's likely
        # just the terms.
        return not (
            terms_explanation != -1 and abs(match_start - terms_explanation) < 500
        )

    def _classify_gpl_family(self, modifier: str) -> str:
        """Classify the GPL family from the regex's captured modifier group."""
        if "lesser" in modifier or "library" in modifier:
            return "LGPL"
        if "affero" in modifier:
            return "AGPL"
        return "GPL"

    def _build_font_exception_candidate(
        self, license_id: str, family: str, or_later: bool, text: str
    ) -> CandidateMatch | None:
        """Build a '... WITH Font-exception-2.0' candidate when *family* is
        GPL and the text matches the font-exception pattern ("As a special
        exception...embed this font"), DB-backed if available, otherwise a
        synthetic candidate. Returns None when the exception doesn't apply."""
        if family != "GPL" or not self._RE_FONT_EXCEPTION.search(text):
            return None

        font_id = f"{license_id} WITH Font-exception-2.0"
        score = 0.92 if or_later else 0.88
        font_details = self.db.get_license_details(font_id)
        if font_details:
            return self.to_candidate(font_details, score)

        # WITH expression not in DB — synthetic candidate; marker floor in
        # _calculate_final_score ensures it ranks above plain GPL without
        # exception (which lacks the marker boost).
        base_details = self.db.get_license_details(license_id)
        return {
            "license_id": font_id,
            "search_text": self.db.get_search_text(license_id) if base_details else "",
            "score": score,
            "is_spdx": True,
            "word_count": base_details.get("word_count", 0) if base_details else 0,
            "is_high_usage": False,
            "is_osi_approved": False,
            "is_fsf_libre": False,
            "pop_score": 0,
        }

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

        matches = list(self._RE_GPL_FAMILY.finditer(text))
        for i, m in enumerate(matches):
            modifier = (m.group(1) or "").strip().lower()

            # Search for the version number and or-later signal within a window
            # following the license name (1000 chars covers the typical notice).
            # Capped at the next GPL-family match (if any) so a second, nearby
            # grant's own or-later wording can't leak into this one's window.
            next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            window_end = min(len(text), m.end() + 1000, next_start)
            window = text[m.start() : window_end]

            ver_match = self._RE_GPL_VERSION.search(window)
            if not ver_match:
                continue

            version_str = ver_match.group(1)  # "2", "2.1", "3", etc.
            if "." not in version_str:
                version_str += ".0"

            or_later = self._resolve_gpl_or_later(
                text, window_end, appendix_start, terms_explanation, m.start()
            )
            family = self._classify_gpl_family(modifier)

            suffix = "-or-later" if or_later else "-only"
            license_id = f"{family}-{version_str}{suffix}"

            if license_id in seen:
                continue

            font_candidate = self._build_font_exception_candidate(
                license_id, family, or_later, text
            )
            if font_candidate is not None:
                candidates.append(font_candidate)
                seen.add(font_candidate["license_id"])
                seen.add(license_id)
                continue

            details = self.db.get_license_details(license_id)
            if details:
                score = 0.92 if or_later else 0.88
                candidates.append(self.to_candidate(details, score))
                seen.add(license_id)

        return candidates

    def _detect_bsd_headers(self, text: str) -> list[CandidateMatch]:
        """Detect BSD-style licenses by counting numbered redistribution conditions.

        Score 0.95 (structural, high-confidence) so it triggers the marker
        floor even on is_pure files, overriding wrong candidates like
        BSD-2-Clause-Darwin whose FTS5 similarity may be higher.
        """
        conditions = re.findall(
            r"^\s*(\d+)\.\s+(?:Redistribution|Neither\b|"
            r"All\s+advertising|The\s+(?:name|author))",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if not conditions:
            return []
        max_cond = max(int(c) for c in conditions)
        if max_cond == 2:
            lic_id = "BSD-2-Clause"
        elif max_cond == 3:
            lic_id = "BSD-3-Clause"
        elif max_cond == 4:
            lic_id = "BSD-4-Clause"
        else:
            return []
        details = self.db.get_license_details(lic_id)
        if details:
            return [self.to_candidate(details, 0.95)]
        return []

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

    def _extract_license_from_lines(self, lines: list[str]) -> LicenseDetails | None:
        """Try to identify a license from a block of lines near a heading."""
        cleaned = [line.strip() for line in lines]

        def _try(text: str) -> LicenseDetails | None:
            # Skip decorative separator lines (all "=", "-", "*", "#", or space)
            if not text or re.match(r"^[=\-*#\s]+$", text):
                return None
            # 1. Direct lookup + name variants (ID normalisation, suffix
            # stripping).  _try_license_lookup's first variant is the exact
            # input text, so it already covers the plain direct lookup --
            # no need to query get_license_details/get_license_by_name
            # separately first.
            details = self._try_license_lookup(text)
            if details:
                return details
            # 2. Extract "under X License" mention from the line
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

    def _extract_mentioned_license(self, text: str) -> str | None:
        """Extract and clean a license name/ID from 'under the X License' pattern."""
        m = self._RE_LICENSE_MENTION.search(text)
        if not m:
            return None
        # Truncate at sentence boundary then clean
        candidate = re.split(r"\.\s", m.group(1), maxsplit=1)[0].strip().rstrip(".,; ")
        candidate = re.sub(r"\bproject'?s?\s+", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s+Licen[sc]e[s]?\s*$", "", candidate, flags=re.IGNORECASE)
        return candidate.strip() if candidate.strip() else None

    def _try_license_lookup(self, name: str) -> LicenseDetails | None:
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
        # "The FreeBSD Documentation License" → "FreeBSD Documentation License"
        if name.lower().startswith("the "):
            rest = name[4:]
            variants += [rest, rest + " License"]
            if rest.lower().endswith(" license"):
                variants.append(rest[:-8].strip())
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
        for m in self._RE_LICENSE_MENTION.finditer(joined):
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
        if self._RE_MD_HEADING.match(line) or self._RE_LINE_HEADING.match(line):
            return True
        if i + 1 < len(lines) and self._RE_UNDERLINE_HEADING.match(
            line + "\n" + lines[i + 1]
        ):
            return True
        return bool(
            0 < i < len(lines) - 1
            and self._RE_BOX_HEADING.match(
                lines[i - 1] + "\n" + line + "\n" + lines[i + 1]
            )
        )

    def _detect_first_line(self, text: str) -> list[CandidateMatch]:
        """Check if the first non-empty line is a known license ID or name."""
        for line in text.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            # _try_license_lookup's first variant is the exact input text,
            # so it already covers a plain direct lookup -- no need to query
            # get_license_details/get_license_by_name separately first.
            details = self._try_license_lookup(clean_line)
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

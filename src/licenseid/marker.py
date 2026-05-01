# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Detection of license markers and structural indicators.
"""

import re


class MarkerDetector:
    """
    Detects license indicators like SPDX-License-Identifier, field names,
    and structural headers.
    """

    def __init__(self) -> None:
        # Regex patterns for various markers
        # Group 1 should always be the potential license name/ID
        self.patterns = [
            # SPDX-License-Identifier: CC0-1.0
            re.compile(
                r"(?i)spdx-license-identifier\s*[:=-]\s*([^\n\r]+)", re.MULTILINE
            ),
            # License: Apache 2.0
            re.compile(r"(?i)^[ \t]*license\s*[:=-]\s*([^\n\r]+)", re.MULTILINE),
            # ## License\nApache 2.0
            re.compile(r"(?i)^[ \t]*#+\s*license\s*[\n\r]+\s*([^\n\r]+)", re.MULTILINE),
            # License\n=======
            re.compile(
                r"(?i)^[ \t]*license\s*[\n\r]+\s*[=-\*]{3,}\s*[\n\r]+\s*([^\n\r]+)",
                re.MULTILINE,
            ),
            # =======\nLicense\n=======
            re.compile(
                # pylint: disable=line-too-long
                r"(?i)^[ \t]*[=-]{3,}\s*[\n\r]+\s*license\s*[\n\r]+\s*[=-]{3,}\s*[\n\r]+\s*([^\n\r]+)",  # noqa: E501
                re.MULTILINE,
            ),
            # *******\nLicense\n*******
            re.compile(
                # pylint: disable=line-too-long
                r"(?i)^[ \t]*\*{3,}\s*[\n\r]+\s*license\s*[\n\r]+\s*\*{3,}\s*[\n\r]+\s*([^\n\r]+)",  # noqa: E501
                re.MULTILINE,
            ),
            # #######\nLicense\n#######
            re.compile(
                # pylint: disable=line-too-long
                r"(?i)^[ \t]*#{3,}\s*[\n\r]+\s*license\s*[\n\r]+\s*#{3,}\s*[\n\r]+\s*([^\n\r]+)",  # noqa: E501
                re.MULTILINE,
            ),
        ]

    def extract_snippets(self, text: str) -> list[str]:
        """
        Extract potential license name/ID snippets from the text using markers.
        """
        snippets: list[str] = []

        # 1. Check patterns
        for pattern in self.patterns:
            for match in pattern.finditer(text):
                snippet = match.group(1).strip()
                if (
                    snippet and len(snippet.split()) < 15
                ):  # Sanity check for snippet size
                    snippets.append(snippet)

        # 2. Check first line (if it looks like a license name)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            # Simple heuristic: if it contains "License" or "Apache/GPL/MIT/BSD"
            # and is short, it might be a header.
            if len(first_line.split()) < 10 and any(
                kw in first_line.lower()
                for kw in ["license", "apache", "gpl", "mit", "bsd", "cc0", "agpl"]
            ):
                snippets.append(first_line)

        return list(dict.fromkeys(snippets))  # Deduplicate while preserving order

    def get_windows(self, text: str, keyword: str = "license") -> list[str]:
        """
        Extract windows of text around a keyword.
        """
        windows: list[str] = []
        text_lower = text.lower()
        start = 0
        while True:
            idx = text_lower.find(keyword, start)
            if idx == -1:
                break

            # Take a window of ~20 words after the keyword
            snippet_raw = text[idx : idx + 200]
            # Clean up to the next few words
            words = snippet_raw.split()
            if len(words) > 1:
                # Remove the keyword itself from the start if it's there
                if words[0].lower().rstrip(":") == keyword:
                    window = " ".join(words[1:15])
                else:
                    window = " ".join(words[:15])

                if window:
                    windows.append(window)

            start = idx + len(keyword)
            if len(windows) > 5:  # Don't take too many windows
                break

        return list(dict.fromkeys(windows))

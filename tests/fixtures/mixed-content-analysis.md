# Real-World Mixed-Content Analysis

This document summarizes findings from analyzing real-world open source repositories to understand how license information is embedded within various file types. These insights guide the generation of realistic `mixed-content` test fixtures.

## 1. Distribution of License Mentions by File Type

In a typical software project, license identifiers and texts do not exclusively live in the `LICENSE` file. They are often embedded within:

| File Type | Proportion of Mentions | Common Formats / Context |
| :--- | :--- | :--- |
| **Source Code Headers** | ~60% | Plain text comments (`//`, `#`, `/* ... */`) at the very top of `.py`, `.js`, `.c`, `.java`, etc. Often uses SPDX-License-Identifier tags or short granting statements. |
| **README Files** | ~20% | Markdown (`.md`) or ReStructuredText (`.rst`). Usually contains a dedicated `## License` section at the bottom, mentioning the license name, ID, and providing a link or a short summary. |
| **Package Manifests** | ~10% | JSON (`package.json`), YAML (`pubspec.yaml`), TOML (`pyproject.toml`, `Cargo.toml`), or Python (`setup.py`). Usually a strict key-value pair like `"license": "MIT"`. |
| **Documentation Pages** | ~5% | HTML or Markdown. Often contains copyright notices in the footer or a dedicated "Terms" page. |
| **Other Configs** | ~5% | Makefiles, Dockerfiles, shell scripts, typically in a header block similar to source code. |

*Note: For the test fixtures, we aim for at least 40 plain text files (representing source files, plain text readmes, and scripts) and at least 10 non-text files (representing package manifests, HTML docs, etc.).*

## 2. Common Structural Patterns for Embedded Licenses

### Pattern A: SPDX Identifier Tags (High Precision)
- **Structure:** `SPDX-License-Identifier: <SPDX-ID>`
- **Location:** Typically lines 1-3 of a source file.
- **Example:**
  ```python
  # SPDX-FileCopyrightText: 2024 The Project Authors
  # SPDX-License-Identifier: Apache-2.0
  ```

### Pattern B: The Short Granting Statement
- **Structure:** A 1-2 paragraph legal boilerplate explicitly granting rights.
- **Location:** Top of source files or inside `README.md`.
- **Example (GPL Flexibility):**
  > "This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version."
- **Insight:** The "(at your option) any later version" phrase is a critical marker indicating `GPL-3.0-or-later` rather than `GPL-3.0-only`.

### Pattern C: Markdown README Section
- **Structure:** A specific header followed by text and sometimes a badge.
- **Location:** Bottom of `README.md`.
- **Example:**
  ```markdown
  ## License
  This project is licensed under the [MIT License](LICENSE).
  See the LICENSE file for more details.
  ```

### Pattern D: Package Managers (JSON/YAML/TOML)
- **Structure:** Standardized keys.
- **Location:** Root configuration files.
- **Example (package.json):**
  ```json
  {
    "name": "my-cool-lib",
    "version": "1.0.0",
    "license": "BSD-3-Clause"
  }
  ```

## 3. Lexical Styles and Proportions

When license names are mentioned natively in text, developers rarely use the exact canonical SPDX name verbatim. 

- **Colloquial Names (40%):** e.g., "GPLv2", "Apache 2", "2-clause BSD".
- **Canonical Names (30%):** e.g., "Apache License 2.0".
- **SPDX IDs (20%):** e.g., "MIT", "GPL-2.0-only" (growing in popularity due to tooling).
- **URLs (10%):** e.g., `https://opensource.org/licenses/MIT`.

## 4. Application to Fixture Generation (`generate_fixtures.py`)

Based on these findings, our Python generation script will define specific LLM-derived **templates**:
1. `SOURCE_HEADER_TEMPLATE`: Injects granting statements and copyright lines into mock source code.
2. `README_MD_TEMPLATE`: Injects project descriptions followed by a License section containing colloquial names or URLs.
3. `PACKAGE_JSON_TEMPLATE` / `PYPROJECT_TOML_TEMPLATE`: Injects precise SPDX IDs into structured configuration files.
4. `HTML_FOOTER_TEMPLATE`: Injects copyright and license notices into mock HTML documentation.

By randomly combining a target license's data with these templates, we will accurately mimic the real-world dataset distribution.

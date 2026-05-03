# Test Fixtures Generation Plan

This document outlines the systematic generation of test fixtures for input types 1, 2, 3, and 5 to broaden the benchmark coverage for the license identification pipeline.

## Target License Selection

To satisfy the diversity constraints (families and IDs), a curated set of at least 50 target SPDX licenses from at least 20 different license families will be selected. Examples of families to include: `GPL`, `LGPL`, `AGPL`, `Apache`, `MIT`, `BSD`, `CC` (Creative Commons), `OFL`, `CDDL`, `MPL`, `EUPL`, `Artistic`, `AFL`, `Zlib`, `W3C`, `Unlicense`, `OSL`, `MS`, `CERN`, `GFDL`.

The generation script (`scripts/generate_fixtures.py`) will load the base metadata and full license text from the existing `tests/fixtures/license-text-long/` directory to construct the derived fixtures.

---

## 1. Input Type 1: `license-id`

**Goal:** Create a single `license_ids.json` file in `tests/fixtures/license-id/`.
**Constraints:** At least 50 test fixtures, >= 25 license IDs, >= 15 families.

**Generation Rules:**
For each selected license, generate a JSON object containing:
- `license_id`: Canonical SPDX ID.
- `id_verbatim`: Exact copy of the SPDX ID.
- `id_deprecated`: Deprecated equivalent if available. Will be fetched automatically from authoritative `https://spdx.org/licenses/licenses.json`.
- `id_space`: The ID with 1-3 leading and trailing spaces added.
- `id_casing`: Randomly applied casing (all upper, all lower, camel case, or randomized), preserving punctuation.
- `id_punct`: Drop 1-2 punctuation marks or replace them with a space (e.g., `Apache-2.0` -> `Apache 2.0`).
- `id_distorted`: If length > 5, truncate the last 2-3 characters.

---

## 2. Input Type 2: `license-name`

**Goal:** Create a single `license_names.json` file in `tests/fixtures/license-name/`.
**Constraints:** At least 50 test fixtures, >= 25 license IDs, >= 15 families.

**Generation Rules:**
For each selected license, generate a JSON object containing:
- `license_id`: Canonical SPDX ID.
- `name_verbatim`: Canonical name from the `name` field.
- `name_space`: Canonical name with 1-3 leading/trailing spaces and 0-1 extra internal spaces.
- `name_casing`: Varied casing (upper, lower, camel, random).
- `name_punct`: Punctuation added, removed, or replaced with space (using `,`, `.`, `:`, `-`, `()`, `/`).
- `name_distored`: Apply lexical distortions sequentially:
    - If both "public" and "general" exist, drop one.
    - Drop "variant" or "license".
    - Drop "generic" if at the end.
    - Drop "project".
    - Swap "licence" <-> "license".
    - Swap "non" <-> "no".
    - Alter or drop the word "version" (to "ver", "v", "v.").
    - Insert "version", "v", "ver", "v." before floating version numbers.
    - Alter version number precision (e.g., `1.0` -> `1.0.0`, `1.0.0` -> `1.0`).

---

## 3. Input Type 3: `license-text-short`

**Goal:** Create individual JSON files in `tests/fixtures/license-text-short/` corresponding to the long text files.
**Constraints:** At least 50 test fixtures (files), >= 25 license IDs, >= 15 families. Text lengths strictly under 500 words.

**Generation Rules:**
For each selected license, parse its `license_text` by words and create a dedicated JSON file with fields representing various combinations of the head (beginning) and tail (end) of the license text:
- `license_text`: Verbatim license text.
- `license_text_short_head_X`: First `X` words for `X` in [50, 100, 200, 500].
- `license_text_short_tail_Y`: Last `Y` words for `Y` in [50, 100, 200, 500].
- `license_text_short_head_X_tail_Y`: First `X` and last `Y` words for combinations like `50_50`, `100_50`, `200_50`, `450_50`, `100_100`, `200_100`, `400_100`, `200_200`, `300_200`.

---

## 4. Input Type 5: `mixed-content`

**Goal:** Generate realistic project files embedding license information.
**Constraints:** 
- At least 100 fixtures (files total) across at least 50 license IDs and 20 families.
- Formats: >= 40 plain text files; >= 10 non-text files (HTML, Markdown, YAML, JSON).
- Hint restriction: Maximum 20 files can contain the literal SPDX license ID.

**Generation Rules:**
- **Directory Structure:** Create subdirectories under `tests/fixtures/mixed-content/` named with the canonical SPDX ID or Expression (replacing spaces with `_`, e.g., `GPL-2.0-only_WITH_Font-exception-2.0`).
- **File Names:** Use mock software project names (e.g., `libfoo_readme.md`, `setup.py`, `package.json`, `index.html`).
- **Real-World Analysis:** Sample real-world mixed-content data to understand style, structure, and proportion. Document these findings in `tests/fixtures/mixed-content-analysis.md`.
- **Content Templates:** Build a corpus of template files (READMEs, configuration files, headers, grant rights statements) generated with LLM assistance based on the real-world analysis findings. These templates will be coded into the generation script.
- **Injection:** Randomly inject combinations of:
  - License name
  - Snippets of license text (short or granting statement)
  - URLs linking to the license
  - Exact SPDX IDs (limited to 20 files max).
- **Granting Statements:** Specifically include standard phrases that specify version rigidity ("version 2.0 only") or flexibility ("version 2.0 or any later version").

---

## Verification & Documentation

After the generation scripts are implemented and run:
- A verification step will ensure counts (files, IDs, families, formats) strictly meet the requirements.
- The `tests/fixtures/README.md` will be updated to document these characteristics, generation techniques, and known limitations to aid future developers and AI assistants.

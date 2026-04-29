---
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Test fixtures

## License matching test dataset

`tests/fixtures/license-data` directory contains 200 JSON fixtures used to
benchmark and evaluate the accuracy of the `licenseid` matcher.

## Dataset composition

- **100 Popular licenses**: Frequently used licenses (e.g., GPL variants, Apache, MIT, BSD, CC).
- **50 Confusing licenses**: Licenses chosen because they share common stems/prefixes with popular licenses, making them difficult to distinguish without precision ranking.
- **50 Rare licenses**: A random selection from the broader SPDX list to ensure long-tail coverage.

## Fixture format

Each `.json` file is named after its `license_id` and contains:

- `license_text`: The verbatim text fetched from the official SPDX License List repository.
- `license_id`: The correct SPDX ID.
- `close_license_ids`: A list of IDs that are closely related (e.g., sharing the same stem like `GPL-`).
- `license_text_distorted_NN`: Programmatically distorted variants of the original text.
- Metadata flags: `is_high_usage`, `is_osi_approved`, `is_fsf_libre`, `is_spdx`.

## Distortion heuristics (01, 05, 10, 20, 40)

The distortion rates represent the approximate percentage of text elements (words/paragraphs) that have been mutated. The operations randomly applied include:

1. **Word dropping**: Simulating copy-paste errors by randomly deleting words.
2. **Typos**: Character swaps within words to simulate human error or OCR glitches.
3. **Punctuation dropping**: Stripping non-alphanumeric characters.
4. **Structural dropping**: For rates >= 5%, occasionally dropping entire paragraphs.
5. **Foreign text injection**: Inserting sentences in languages other than the original text language to simulate mixed-language documents or preamble metadata.
6. **Whitespace mutation**: Injecting random newlines or double spaces.

## Updating the dataset

To regenerate these fixtures, run the script from the root directory:

```bash
python scripts/generate_dataset.py
```

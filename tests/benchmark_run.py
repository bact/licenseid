# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import sqlite3
import tempfile

sys.path.insert(0, os.path.abspath("src"))

from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text

FIXTURES = {
    "readme_apache": {
        "text": """
# Awesome Project

This project is built with love and care.

## Installation
pip install awesome

## License
Apache License, Version 2.0

See LICENSE file for details.
""",
        "expected": "Apache-2.0",
    },
    "source_mit": {
        "text": """
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-License-Identifier: MIT

def hello():
    print("Hello, World!")
""",
        "expected": "MIT",
    },
    "contributing_gpl": {
        "text": """
# Contributing to this project

We welcome contributions!

Please note that this project is licensed under the GPL-3.0-only license.
By contributing, you agree to abide by its terms.
""",
        "expected": "GPL-3.0-only",
    },
    "doc_cc0": {
        "text": """
***************************
      LICENSE INFO
***************************
This documentation is licensed under CC0-1.0.
Feel free to use it anywhere.
""",
        "expected": "CC0-1.0",
    },
}


def run_benchmark() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "benchmark.db")
        LicenseDatabase(db_path)

        with sqlite3.connect(db_path) as conn:
            licenses = [
                ("Apache-2.0", "Apache License 2.0"),
                ("MIT", "MIT License"),
                ("GPL-3.0-only", "GNU General Public License v3.0 only"),
                ("CC0-1.0", "Creative Commons Zero v1.0 Universal"),
            ]
            for lid, name in licenses:
                conn.execute(
                    "INSERT INTO licenses (license_id, name, norm_license_id, norm_name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?, ?, ?)",
                    (lid, name, normalize_text(lid), normalize_text(name), True, True),
                )

        matcher = AggregatedLicenseMatcher(db_path)

        print("\n" + "=" * 80)
        print(f"{'FIXTURE':<20} | {'WITHOUT MARKERS':<22} | {'WITH MARKERS':<25}")
        print("-" * 80)

        for name, data in FIXTURES.items():
            text = data["text"]

            # Without markers
            res_no = matcher.match({"text": text, "enable_markers": False})
            top_no = res_no[0]["license_id"] if res_no else "None"
            score_no = res_no[0]["score"] if res_no else 0.0

            # With markers
            res_yes = matcher.match({"text": text, "enable_markers": True})
            top_yes = res_yes[0]["license_id"] if res_yes else "None"
            score_yes = res_yes[0]["score"] if res_yes else 0.0
            method = res_yes[0].get("method", "unknown") if res_yes else "N/A"

            print(
                f"{name:<20} | {top_no:<10} ({score_no:.2f}) | {top_yes:<10} ({score_yes:.2f}) [{method}]"
            )

        print("=" * 80 + "\n")


if __name__ == "__main__":
    run_benchmark()

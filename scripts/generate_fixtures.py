#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Generates test fixtures for licenseid benchmarks (Input Types 1, 2, 3, and 5).
"""

import json
import random
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Any

# Define paths
REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
LONG_TEXT_DIR = FIXTURES_DIR / "license-text-long"

TYPE_1_DIR = FIXTURES_DIR / "license-id"
TYPE_2_DIR = FIXTURES_DIR / "license-name"
TYPE_3_DIR = FIXTURES_DIR / "license-text-short"
TYPE_5_DIR = FIXTURES_DIR / "mixed-content"

# Ensure output directories exist
for d in [TYPE_1_DIR, TYPE_2_DIR, TYPE_3_DIR, TYPE_5_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# SPDX Data Source
SPDX_LICENSES_URL = "https://spdx.org/licenses/licenses.json"

# Target families for selection
TARGET_FAMILIES = [
    "GPL",
    "LGPL",
    "AGPL",
    "Apache",
    "MIT",
    "BSD",
    "CC",
    "OFL",
    "CDDL",
    "MPL",
    "EUPL",
    "Artistic",
    "AFL",
    "Zlib",
    "W3C",
    "Unlicense",
    "OSL",
    "MS",
    "CERN",
    "GFDL",
]


def get_family(license_id: str) -> str:
    """Extract family prefix from license ID."""
    for f in TARGET_FAMILIES:
        if license_id.startswith(f):
            return f
    return "Other"


def fetch_deprecated_mapping() -> dict[str, str]:
    """
    Fetch SPDX licenses.json and build a heuristic mapping from
    canonical IDs to their deprecated predecessors.
    """
    print("Fetching SPDX licenses.json...")
    req = urllib.request.Request(
        SPDX_LICENSES_URL, headers={"User-Agent": "licenseid-test-gen"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch SPDX data: {e}")
        return {}

    licenses = data.get("licenses", [])
    deprecated = [lic for lic in licenses if lic.get("isDeprecatedLicenseId", False)]
    canonical = [lic for lic in licenses if not lic.get("isDeprecatedLicenseId", False)]

    # Very basic heuristic: if deprecated name matches canonical name exactly, or
    # if ID matches without '-only' or '-or-later'.
    # e.g., 'GPL-2.0' is deprecated, canonical is 'GPL-2.0-only'.
    mapping = {}
    for dep in deprecated:
        d_id = dep["licenseId"]
        d_name = dep["name"]

        for can in canonical:
            c_id = can["licenseId"]
            c_name = can["name"]
            if c_name == d_name and c_id != d_id:
                mapping[c_id] = d_id
                break

            # Common GPL family heuristic
            if c_id.endswith("-only") and c_id.replace("-only", "") == d_id:
                mapping[c_id] = d_id
                break
            if c_id.endswith("-or-later") and c_id.replace("-or-later", "+") == d_id:
                mapping[c_id] = d_id
                break

    return mapping


def select_target_licenses() -> list[dict[str, Any]]:
    """Select at least 50 licenses spanning at least 20 families."""
    all_files = list(LONG_TEXT_DIR.glob("*.json"))
    licenses = []

    for f in all_files:
        with open(f, "r", encoding="utf-8") as file:
            data = json.load(file)
            licenses.append(data)

    # Group by family
    family_map = {}
    for lic in licenses:
        f = get_family(lic["license_id"])
        if f not in family_map:
            family_map[f] = []
        family_map[f].append(lic)

    selected = []
    # Pick 2 from each identified family to guarantee spread
    for f, lics in family_map.items():
        random.shuffle(lics)
        selected.extend(lics[:2])

    # If we need more to hit 60
    remaining = [lic for lic in licenses if lic not in selected]
    random.shuffle(remaining)
    needed = 60 - len(selected)
    if needed > 0:
        selected.extend(remaining[:needed])

    print(
        f"Selected {len(selected)} licenses from {len(set(get_family(lic_['license_id']) for lic_ in selected))} families."
    )
    return selected


def apply_casing(text: str) -> str:
    choice = random.choice(["upper", "lower", "camel", "random"])
    if choice == "upper":
        return text.upper()
    elif choice == "lower":
        return text.lower()
    elif choice == "camel":
        # simple camel casing
        return re.sub(r"[^a-zA-Z0-9]+(.)", lambda m: m.group(1).upper(), text.lower())
    else:
        # random case
        return "".join(c.upper() if random.random() > 0.5 else c.lower() for c in text)


def drop_punct(text: str) -> str:
    res = text
    puncts = ["-", ".", ",", "(", ")", ":"]
    for _ in range(random.randint(1, 2)):
        p = random.choice(puncts)
        res = res.replace(p, random.choice(["", " "]), 1)
    return res


def generate_type_1(licenses: list[dict[str, Any]], dep_map: dict[str, str]) -> None:
    print("Generating Type 1: license-id...")
    results = []
    for lic in licenses:
        c_id = lic["license_id"]

        # spaces
        l_spaces = " " * random.randint(1, 3)
        r_spaces = " " * random.randint(1, 3)

        distorted = c_id
        if len(distorted) > 5:
            distorted = distorted[: -random.randint(2, 3)]

        results.append(
            {
                "license_id": c_id,
                "id_verbatim": c_id,
                "id_deprecated": dep_map.get(c_id, ""),
                "id_space": f"{l_spaces}{c_id}{r_spaces}",
                "id_casing": apply_casing(c_id),
                "id_punct": drop_punct(c_id),
                "id_distorted": distorted,
            }
        )

    with open(TYPE_1_DIR / "license_ids.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)


def distort_name(name: str) -> str:
    n = name.lower()
    if "public" in n and "general" in n:
        n = n.replace(random.choice(["public", "general"]), "").strip()
    if "variant" in n:
        n = n.replace("variant", "").strip()
    if "license" in n:
        n = n.replace("license", "").strip()
    if n.endswith("generic"):
        n = n[:-7].strip()
    if "project" in n:
        n = n.replace("project", "").strip()

    if "licence" in name.lower():
        n = re.sub(r"(?i)licence", "license", n)
    elif "license" in name.lower():
        n = re.sub(r"(?i)license", "licence", n)

    if "non" in name.lower():
        n = re.sub(r"(?i)\bnon\b", "no", n)
    elif "no" in name.lower():
        n = re.sub(r"(?i)\bno\b", "non", n)

    n = re.sub(r"(?i)\bversion\b", random.choice(["ver", "v", "v.", ""]), n)

    # insert version before standalone float
    n = re.sub(r"\b(\d+\.\d+)\b", r"v \1", n)
    n = re.sub(r"(?i)\b(v|ver|version)\s+v\b", r"\1", n)

    # alter precision
    def alter_prec(m):
        val = m.group(1)
        if len(val.split(".")) == 2:
            return val + ".0"
        elif len(val.split(".")) == 3 and val.endswith(".0"):
            return val[:-2]
        return val

    n = re.sub(r"\b(\d+\.\d+(?:\.\d+)?)\b", alter_prec, n)

    # clean up extra spaces
    return re.sub(r"\s+", " ", n).strip()


def generate_type_2(licenses: list[dict[str, Any]]) -> None:
    print("Generating Type 2: license-name...")
    results = []
    for lic in licenses:
        c_id = lic["license_id"]
        c_name = lic.get("name", "")
        if not c_name:
            continue

        # space
        l_spaces = " " * random.randint(1, 3)
        r_spaces = " " * random.randint(1, 3)
        words = c_name.split()
        if len(words) > 1:
            idx = random.randint(1, len(words) - 1)
            words[idx] = " " + words[idx]
        name_space = l_spaces + " ".join(words) + r_spaces

        results.append(
            {
                "license_id": c_id,
                "name_verbatim": c_name,
                "name_space": name_space,
                "name_casing": apply_casing(c_name),
                "name_punct": drop_punct(c_name),
                "name_distored": distort_name(c_name),
            }
        )

    with open(TYPE_2_DIR / "license_names.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)


def generate_type_3(licenses: list[dict[str, Any]]) -> None:
    print("Generating Type 3: license-text-short...")
    for lic in licenses:
        c_id = lic["license_id"]
        text = lic["license_text"]
        words = text.split()

        result = {"license_id": c_id, "license_text": text}

        for k, v in lic.items():
            if k not in ["license_text", "license_id"] and not k.startswith(
                "license_text_long"
            ):
                result[k] = v

        def get_head(n):
            return " ".join(words[:n])

        def get_tail(n):
            return " ".join(words[-n:]) if n <= len(words) else " ".join(words)

        for x in [50, 100, 200, 500]:
            result[f"license_text_short_head_{x}"] = get_head(x)
            result[f"license_text_short_tail_{x}"] = get_tail(x)

        combs = [
            (50, 50),
            (100, 50),
            (200, 50),
            (450, 50),
            (100, 100),
            (200, 100),
            (400, 100),
            (200, 200),
            (300, 200),
        ]
        for x, y in combs:
            head = get_head(x)
            tail = get_tail(y)
            # prevent overlap if text is too short
            if x + y >= len(words):
                result[f"license_text_short_head_{x}_tail_{y}"] = text
            else:
                result[f"license_text_short_head_{x}_tail_{y}"] = (
                    head + " ...\\n... " + tail
                )

        with open(
            TYPE_3_DIR / f"{c_id.replace('/', '_')}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(result, f, indent=4)


def generate_type_5(licenses: list[dict[str, Any]]) -> None:
    print("Generating Type 5: mixed-content...")
    # Clean up existing mixed-content to start fresh
    if TYPE_5_DIR.exists():
        shutil.rmtree(TYPE_5_DIR)
    TYPE_5_DIR.mkdir()

    # Templates
    readme_template = """# {project_name}

A fantastic open-source library that helps you do amazing things.

## Installation
`pip install {project_name}`

## Usage
Import the module and start using it immediately:
```python
import {project_name}
{project_name}.run()
```

## Contributing
Pull requests are welcome!

## License
{license_info}
"""

    py_header_template = """# {project_name} module
# Copyright (c) 2026 The {project_name} Authors
{license_info}

def run():
    print("Running!")
"""

    package_json_template = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "An awesome library.",
  "main": "index.js",
  "license": "{license_info}"
}}
"""

    html_template = """<!DOCTYPE html>
<html>
<head><title>{project_name} Documentation</title></head>
<body>
<h1>{project_name}</h1>
<p>Welcome to the official docs.</p>
<footer>
  <p>Copyright 2026. {license_info}</p>
</footer>
</body>
</html>
"""

    yaml_template = """name: {project_name}
version: 1.0.0
description: A mock project.
license: {license_info}
dependencies:
  - flask
"""

    total_files = 0
    exact_id_count = 0

    for lic in licenses:
        c_id = lic["license_id"]
        c_name = lic.get("name", c_id)

        # Dir name
        safe_id = c_id.replace(" ", "_").replace("/", "_")
        target_dir = TYPE_5_DIR / safe_id
        target_dir.mkdir(exist_ok=True)

        # Determine strictness for granting
        grant = f"Licensed under the {c_name}."
        if "GPL" in c_id:
            if "or-later" in c_id:
                grant = f"This program is free software: you can redistribute it and/or modify it under the terms of the {c_name}, either version of the License, or (at your option) any later version."
            elif "only" in c_id:
                grant = f"This program is free software: you can redistribute it and/or modify it under the terms of the {c_name}, version only."

        # We need to generate 2-3 files per license to hit ~150 files total
        num_files = random.randint(2, 4)

        for i in range(num_files):
            project_name = f"lib_mock_{safe_id.lower()}_{i}"

            # Decide what kind of license info to inject
            info_choice = random.choice(["name", "grant", "url", "exact_id"])
            if info_choice == "exact_id":
                if exact_id_count < 20:
                    lic_info = c_id
                    exact_id_count += 1
                else:
                    lic_info = c_name
            elif info_choice == "name":
                lic_info = c_name
            elif info_choice == "grant":
                lic_info = grant
            else:
                lic_info = f"See https://spdx.org/licenses/{c_id}.html for details."

            # Decide file type
            file_type = random.choices(
                ["readme", "py", "json", "html", "yaml"],
                weights=[0.3, 0.4, 0.1, 0.1, 0.1],
                k=1,
            )[0]

            if file_type == "readme":
                content = readme_template.format(
                    project_name=project_name, license_info=lic_info
                )
                filename = "README.md"
            elif file_type == "py":
                # For python, add comment markers
                formatted_info = "\\n# ".join(lic_info.split("\\n"))
                content = py_header_template.format(
                    project_name=project_name, license_info=f"# {formatted_info}"
                )
                filename = f"{project_name}.py"
            elif file_type == "json":
                # JSON needs clean string
                content = package_json_template.format(
                    project_name=project_name,
                    license_info=c_id if info_choice == "exact_id" else c_name,
                )
                filename = "package.json"
            elif file_type == "html":
                content = html_template.format(
                    project_name=project_name, license_info=lic_info
                )
                filename = "index.html"
            else:
                content = yaml_template.format(
                    project_name=project_name,
                    license_info=c_id if info_choice == "exact_id" else c_name,
                )
                filename = "pubspec.yaml"

            # If the filename already exists in the folder, append a number
            filepath = target_dir / filename
            if filepath.exists():
                filepath = target_dir / f"{i}_{filename}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            total_files += 1

    print(
        f"Generated {total_files} mixed-content files (Exact IDs used: {exact_id_count}/20)."
    )


def main() -> None:
    random.seed(42)  # Deterministic generation
    dep_map = fetch_deprecated_mapping()
    licenses = select_target_licenses()

    generate_type_1(licenses, dep_map)
    generate_type_2(licenses)
    generate_type_3(licenses)
    generate_type_5(licenses)

    print("Done! Fixtures generated successfully.")


if __name__ == "__main__":
    main()

# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Mixed-content fixtures (Input Type 5) of the licenseid generator."""

import random
from pathlib import Path
from typing import Any

from fixture_dirs import check_dir

MAX_EXACT_IDS = 20

README_TEMPLATE = """# {project_name}

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

PY_HEADER_TEMPLATE = """# {project_name} module
# Copyright (c) 2026 The {project_name} Authors
{license_info}

def run():
    print("Running!")
"""

PACKAGE_JSON_TEMPLATE = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "An awesome library.",
  "main": "index.js",
  "license": "{license_info}"
}}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
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

YAML_TEMPLATE = """name: {project_name}
version: 1.0.0
description: A mock project.
license: {license_info}
dependencies:
  - flask
"""


def _grant_text(c_id: str, c_name: str) -> str:
    """Return the licence grant sentence of a licence."""
    grant = f"Licensed under the {c_name}."
    if "GPL" in c_id:
        terms = (
            "This program is free software: you can redistribute it and/or "
            f"modify it under the terms of the {c_name}"
        )
        if "or-later" in c_id:
            grant = (
                f"{terms}, either version of the License, "
                "or (at your option) any later version."
            )
        elif "only" in c_id:
            grant = f"{terms}, version only."
    return grant


def _info_choice(
    c_id: str, c_name: str, grant: str, exact_used: int
) -> tuple[str, str, int]:
    """Pick the kind of licence info; return (choice, text, exact IDs used)."""
    choice = random.choice(["name", "grant", "url", "exact_id"])
    if choice == "exact_id":
        if exact_used < MAX_EXACT_IDS:
            return choice, c_id, exact_used + 1
        return choice, c_name, exact_used
    if choice == "name":
        return choice, c_name, exact_used
    if choice == "grant":
        return choice, grant, exact_used
    return choice, f"See https://spdx.org/licenses/{c_id}.html for details.", exact_used


def _render_file(
    file_type: str, project_name: str, lic_info: str, short: str
) -> tuple[str, str]:
    """Return (content, file name) of one mock file; short is the bare name or ID."""
    if file_type == "readme":
        content = README_TEMPLATE.format(
            project_name=project_name, license_info=lic_info
        )
        return content, "README.md"
    if file_type == "py":
        formatted_info = "\n# ".join(lic_info.split("\n"))
        content = PY_HEADER_TEMPLATE.format(
            project_name=project_name, license_info=f"# {formatted_info}"
        )
        return content, f"{project_name}.py"
    if file_type == "json":
        content = PACKAGE_JSON_TEMPLATE.format(
            project_name=project_name, license_info=short
        )
        return content, "package.json"
    if file_type == "html":
        content = HTML_TEMPLATE.format(project_name=project_name, license_info=lic_info)
        return content, "index.html"
    content = YAML_TEMPLATE.format(project_name=project_name, license_info=short)
    return content, "pubspec.yaml"


def _write_licence_files(
    lic: dict[str, Any], target_dir: Path, exact_used: int
) -> tuple[int, int]:
    """Write 2 to 4 mock files; return (files written, exact IDs used)."""
    c_id = lic["license_id"]
    c_name = lic.get("name", c_id)
    safe_id = target_dir.name
    grant = _grant_text(c_id, c_name)
    written = 0

    for i in range(random.randint(2, 4)):
        project_name = f"lib_mock_{safe_id.lower()}_{i}"
        choice, lic_info, exact_used = _info_choice(c_id, c_name, grant, exact_used)
        file_type = random.choices(
            ["readme", "py", "json", "html", "yaml"],
            weights=[0.3, 0.4, 0.1, 0.1, 0.1],
            k=1,
        )[0]
        short = c_id if choice == "exact_id" else c_name
        content, filename = _render_file(file_type, project_name, lic_info, short)

        filepath = target_dir / filename
        if filepath.exists():
            filepath = target_dir / f"{i}_{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1
    return written, exact_used


def generate_type_5(
    licenses: list[dict[str, Any]], out_dir: Path, force: bool = False
) -> None:
    """Write mock project files that mention each licence in several ways."""
    print("Generating Type 5: mixed-content...")
    total_files = 0
    exact_id_count = 0

    for lic in licenses:
        safe_id = lic["license_id"].replace(" ", "_").replace("/", "_")
        target_dir = out_dir / safe_id
        if not check_dir(target_dir, force):
            continue
        written, exact_id_count = _write_licence_files(lic, target_dir, exact_id_count)
        total_files += written

    print(
        f"Generated {total_files} mixed-content files "
        f"(Exact IDs used: {exact_id_count}/{MAX_EXACT_IDS})."
    )

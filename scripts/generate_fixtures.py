#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Generates test fixtures for licenseid benchmarks (Input Types 1, 2, 3, 4, and 5).
"""

import argparse
import io
import json
import random
import re
import shutil
import string
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

# Define paths
REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# SPDX Data Source
SPDX_LICENSES_URL = "https://spdx.org/licenses/licenses.json"

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
    "X11",
]


def generate_foreign_texts() -> list[str]:
    base_templates = [
        "Esta licencia aplica a este software.",
        "Ce logiciel est sous licence libre.",
        "Diese Lizenz gilt für diese Software.",
        "Questo software è fornito così com'è.",
        "このソフトウェアはオープンソースです。",
        "Este software é fornecido sem qualquer garantia explícita ou implícita.",
        "Данная программа является свободным программным обеспечением.",
        "本软件按“原样”提供，不带有任何明示或暗示的担保。",
        "Derechos de autor reservados. Consulte el archivo LICENSE para más detalles.",
        "Copyright (c) Tous droits réservés. Voir le fichier de licence.",
        "本プログラムは、現状のまま提供され、いかなる保証もありません。",
        "Program ten jest wolnym oprogramowaniem; możesz go rozprowadzać dalej.",
        "Tämä ohjelmisto toimitetaan sellaisenaan ilman takuuta.",
        "Denna programvara tillhandahålls i befintligt skick.",
        "Dit is vrije software, en je bent vrij om het te verspreiden.",
        "Bu yazılım, hiçbir garanti olmaksızın 'olduğu gibi' sağlanır.",
        "Tento software je poskytován tak, jak je.",
        "Ez a szoftver nyílt forráskódú.",
        "Acest software este furnizat ca atare.",
        "Цей продукт є відкритим програмним забезпеченням.",
        "이 소프트웨어는 오픈 소스입니다.",
    ]
    years = ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    authors = [
        "The Project Authors",
        "Contributors",
        "Open Source Initiative",
        "Free Software Foundation",
        "Acme Corp",
        "John Doe",
        "Jane Smith",
    ]

    texts = set(base_templates)
    while len(texts) < 200:
        year = random.choice(years)
        author = random.choice(authors)
        t_type = random.choice(
            [
                f"Copyright (c) {year} {author}. All rights reserved.",
                f"Copyright {year} {author}. " + random.choice(base_templates),
                f"Derechos de autor (c) {year} {author}.",
                f"Droits d'auteur {year} {author}.",
                f"Urheberrecht (c) {year} {author}.",
                f"저작권 (c) {year} {author}.",
                f"版权所有 (c) {year} {author}.",
            ]
        )
        texts.add(t_type)

    return list(texts)[:200]


FOREIGN_TEXTS = generate_foreign_texts()


def get_family(license_id: str) -> str:
    for f in TARGET_FAMILIES:
        if license_id.startswith(f):
            return f
    return "Other"


def fetch_spdx_data() -> tuple[str, dict[str, Any], dict[str, str]]:
    print("Fetching SPDX licenses.json...")
    req = urllib.request.Request(
        SPDX_LICENSES_URL, headers={"User-Agent": "licenseid-test-gen"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch SPDX data: {e}")
        return "", {}, {}

    version = data.get("licenseListVersion", "")
    licenses = data.get("licenses", [])

    deprecated = [lic for lic in licenses if lic.get("isDeprecatedLicenseId", False)]
    canonical = [lic for lic in licenses if not lic.get("isDeprecatedLicenseId", False)]

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

            if c_id.endswith("-only") and c_id.replace("-only", "") == d_id:
                mapping[c_id] = d_id
                break
            if c_id.endswith("-or-later") and c_id.replace("-or-later", "+") == d_id:
                mapping[c_id] = d_id
                break

    licenses_dict = {lic["licenseId"]: lic for lic in canonical}
    return version, licenses_dict, mapping


def fetch_license_texts_from_tarball(
    version: str, selected_ids: set[str]
) -> dict[str, str]:
    url = (
        f"https://github.com/spdx/license-list-data/archive/refs/tags/v{version}.tar.gz"
    )
    print(f"Downloading SPDX tarball: {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "licenseid-test-gen"})
    try:
        with urllib.request.urlopen(req) as response:
            tar_bytes = response.read()
    except Exception as e:
        print(f"Failed to download tarball: {e}")
        return {}

    print("Extracting texts from tarball...")
    texts = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            parts = member.name.split("/")
            if len(parts) >= 3 and parts[-2] == "text" and parts[-1].endswith(".txt"):
                lic_id = parts[-1][:-4]
                if lic_id in selected_ids:
                    f = tar.extractfile(member)
                    if f:
                        texts[lic_id] = f.read().decode("utf-8")
    return texts


def select_target_licenses(
    licenses_dict: dict[str, Any], full_coverage: bool = False
) -> list[dict[str, Any]]:
    all_lids = list(licenses_dict.keys())

    if full_coverage:
        selected = list(licenses_dict.values())
    else:
        family_map: dict[str, list[dict[str, Any]]] = {}
        for lid, lic in licenses_dict.items():
            f = get_family(lid)
            if f not in family_map:
                family_map[f] = []
            family_map[f].append(lic)

        selected = []
        for f, lics in family_map.items():
            shuffled = list(lics)
            random.shuffle(shuffled)
            selected.extend(shuffled[:2])

        remaining = [lic for lic in licenses_dict.values() if lic not in selected]
        random.shuffle(remaining)
        needed = 60 - len(selected)
        if needed > 0:
            selected.extend(remaining[:needed])
    for lic in selected:
        lid = lic["licenseId"]
        lic["license_id"] = lid
        lic["is_high_usage"] = lic.get("isOsiApproved", False) or lic.get(
            "isFsfLibre", False
        )
        lic["is_osi_approved"] = lic.get("isOsiApproved", False)
        lic["is_fsf_libre"] = lic.get("isFsfLibre", False)
        lic["is_spdx"] = True

        stem = lid.split("-")[0]
        close = [x for x in all_lids if x != lid and x.startswith(stem)]
        lic["close_license_ids"] = close[:5]

    return selected


def check_dir(dir_path: Path, force: bool) -> bool:
    if dir_path.exists():
        if force:
            print(f"Removing existing directory {dir_path}")
            shutil.rmtree(dir_path)
        else:
            print(
                f"Directory {dir_path} already exists. Skipping. Use --force to overwrite."
            )
            return False
    dir_path.mkdir(parents=True, exist_ok=True)
    return True


def generate_type_1(
    licenses: list[dict[str, Any]], dep_map: dict[str, str], out_dir: Path
) -> None:
    print("Generating Type 1: license-id...")
    results = []
    for lic in licenses:
        c_id = lic["license_id"]
        d_id = dep_map.get(c_id)

        variations = []
        # basic
        variations.append(c_id)
        if d_id:
            variations.append(d_id)

        # distorted
        lower_id = c_id.lower()
        if lower_id not in variations:
            variations.append(lower_id)
        spaced_id = c_id.replace("-", " ")
        if spaced_id not in variations:
            variations.append(spaced_id)
        no_space_id = c_id.replace("-", "")
        if no_space_id not in variations:
            variations.append(no_space_id)

        results.append(
            {
                "canonical_id": c_id,
                "deprecated_id": d_id,
                "variations": variations,
            }
        )

    with open(out_dir / "license_ids.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)


def generate_type_2(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    print("Generating Type 2: license-name...")

    def apply_casing(name: str) -> str:
        return random.choice([name.lower(), name.upper(), name.title()])

    def drop_punct(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9 ]", "", name)

    def distort_name(name: str) -> str:
        n = name
        n = re.sub(r"(?i)general public", random.choice(["", "pub"]), n)
        n = re.sub(r"(?i)public", "", n)

        if "licence" not in name.lower():
            n = re.sub(r"(?i)license", "licence", n)

        if "non" in name.lower():
            n = re.sub(r"(?i)non", "no", n)
        elif "no" in name.lower():
            n = re.sub(r"(?i)no", "non", n)

        n = re.sub(r"(?i)version", random.choice(["ver", "v", "v.", ""]), n)

        n = re.sub(r"(\d+\.\d+)", r"v ", n)
        n = re.sub(r"(?i)(v|ver|version)\s+v", r"", n)

        def alter_prec(m: re.Match[str]) -> str:
            val = m.group(1)
            if len(val.split(".")) == 2:
                return val + ".0"
            if len(val.split(".")) > 2 and val.endswith(".0"):
                return val[:-2]
            return val

        n = re.sub(r"(\d+\.\d+(?:\.\d+)?)", alter_prec, n)
        return re.sub(r"\s+", " ", n).strip()

    results = []
    for lic in licenses:
        c_id = lic["license_id"]
        c_name = lic.get("name", "")
        if not c_name:
            continue

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

    with open(out_dir / "license_names.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)


def generate_type_3(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    print("Generating Type 3: license-text-short...")
    for lic in licenses:
        c_id = lic["license_id"]
        text: str = lic.get("license_text", "")

        result = {"license_id": c_id, "license_text": text}

        for k, v in lic.items():
            if k not in ["license_text", "license_id"] and not k.startswith(
                "license_text_long"
            ):
                result[k] = v

        def get_head(n: int) -> str:
            return text[:n]

        def get_tail(n: int) -> str:
            return text[-n:] if n <= len(text) else text

        for x in [300, 500, 700, 800, 900, 1000, 1500, 2000, 3000]:
            result[f"license_text_short_head_{x}"] = get_head(x)
            result[f"license_text_short_tail_{x}"] = get_tail(x)

        combs = [
            (300, 300),
            (500, 300),
            (700, 300),
            (1000, 300),
            (1500, 300),
            (2000, 300),
            (2700, 300),
            (300, 500),
            (500, 500),
            (700, 500),
            (1000, 500),
            (1500, 500),
            (2000, 500),
            (2500, 500),
            (300, 700),
            (500, 700),
            (700, 700),
            (1000, 700),
            (1500, 700),
            (2000, 700),
            (2300, 700),
            (300, 1000),
            (500, 1000),
            (700, 1000),
            (1000, 1000),
            (1500, 1000),
            (2000, 1000),
            (300, 1500),
            (500, 1500),
            (700, 1500),
            (1000, 1500),
            (1500, 1500),
            (300, 2000),
            (500, 2000),
            (700, 2000),
            (1000, 2000),
        ]
        for x, y in combs:
            # If the head already covers the whole text, a tail adds nothing.
            if x >= len(text):
                continue
            # Clip the tail so it starts exactly where the head ends, avoiding
            # overlap and data duplication.  For example, with a 1300-char text,
            # head=1000 tail=500 → actual_tail=300 (chars 1000–1299).
            actual_tail = min(y, len(text) - x)
            head = get_head(x)
            tail = text[-actual_tail:] if actual_tail > 0 else ""
            if head + tail == text:
                # Head and clipped tail together reconstruct the full text;
                # store it verbatim with no separator.
                result[f"license_text_short_head_{x}_tail_{y}"] = text
            else:
                # Non-contiguous: head and tail are separated portions.
                # A single newline marks the gap without adding noise tokens.
                result[f"license_text_short_head_{x}_tail_{y}"] = head + "\n" + tail

        with open(
            out_dir / f"{c_id.replace('/', '_')}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(result, f, indent=4)


def distort_text(text: str, rate_percent: int) -> str:
    if rate_percent == 0:
        return text

    words = text.split()
    if not words:
        return text

    num_words = len(words)
    num_ops = max(1, int(num_words * (rate_percent / 100.0)))
    paragraphs = text.split("\n\n")

    for _ in range(num_ops):
        if not words:
            break

        op = random.random()

        if op < 0.6:
            idx = random.randint(0, len(words) - 1)
            word_op = random.random()
            if word_op < 0.4:
                words.pop(idx)
            elif word_op < 0.7:
                w = list(words[idx])
                if len(w) > 2:
                    i = random.randint(0, len(w) - 2)
                    w[i], w[i + 1] = w[i + 1], w[i]
                    words[idx] = "".join(w)
            elif word_op < 0.8:
                punct = random.choice(string.punctuation)
                words[idx] += punct
            elif word_op < 0.9:
                word = words[idx]
                if len(word) > 3:
                    split_idx = random.randint(1, len(word) - 1)
                    char = random.choice([" ", "-"])
                    words[idx] = word[:split_idx] + char + word[split_idx:]
            else:
                words[idx] = re.sub(r"[^\w\s]", "", words[idx])

        elif op < 0.9 and rate_percent >= 5:
            struct_op = random.random()
            if struct_op < 0.5 and len(paragraphs) > 2:
                idx = random.randint(0, len(paragraphs) - 1)
                paragraphs.pop(idx)
                words = ("\n\n".join(paragraphs)).split()
            else:
                idx = random.randint(0, max(0, len(words) - 1))
                foreign = random.choice(FOREIGN_TEXTS)
                words.insert(idx, foreign)
        else:
            idx = random.randint(0, max(0, len(words) - 1))
            words.insert(idx, "\n")

    return " ".join(words)


def generate_type_4(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    print("Generating Type 4: license-text-long...")
    for lic in licenses:
        c_id = lic["license_id"]
        text = lic.get("license_text", "")

        result = {"license_id": c_id, "license_text": text}

        for k, v in lic.items():
            if k not in ["license_text", "license_id"] and not k.startswith(
                "license_text_long"
            ):
                result[k] = v

        for rate in [1, 2, 5, 10, 20]:
            distorted = distort_text(text, rate)
            result[f"license_text_long_distorted_{rate:02d}"] = distorted

        with open(
            out_dir / f"{c_id.replace('/', '_')}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(result, f, indent=4)


def generate_type_5(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    print("Generating Type 5: mixed-content...")
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

        safe_id = c_id.replace(" ", "_").replace("/", "_")
        target_dir = out_dir / safe_id
        target_dir.mkdir(parents=True, exist_ok=True)

        grant = f"Licensed under the {c_name}."
        if "GPL" in c_id:
            if "or-later" in c_id:
                grant = f"This program is free software: you can redistribute it and/or modify it under the terms of the {c_name}, either version of the License, or (at your option) any later version."
            elif "only" in c_id:
                grant = f"This program is free software: you can redistribute it and/or modify it under the terms of the {c_name}, version only."

        num_files = random.randint(2, 4)

        for i in range(num_files):
            project_name = f"lib_mock_{safe_id.lower()}_{i}"

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
                formatted_info = "\n# ".join(lic_info.split("\n"))
                content = py_header_template.format(
                    project_name=project_name, license_info=f"# {formatted_info}"
                )
                filename = f"{project_name}.py"
            elif file_type == "json":
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
    parser = argparse.ArgumentParser(description="Generate License ID Text Fixtures")
    parser.add_argument(
        "--types",
        type=str,
        default="1,2,3,4,5",
        help="Comma-separated list of types to generate. Default: 1,2,3,4,5",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force overwrite existing directories"
    )
    parser.add_argument(
        "--verify-dir",
        type=str,
        default="",
        help="If provided, outputs to this directory instead of the real fixtures dir and restricts to 5 licenses",
    )
    parser.add_argument(
        "--full-coverage",
        action="store_true",
        help=(
            "Generate fixtures for all canonical SPDX licenses instead of "
            "the default stratified sample (~60 licenses across 20+ families). "
            "Required for the FTS5 dual-query recall benchmark."
        ),
    )
    args = parser.parse_args()

    random.seed(42)  # Deterministic generation
    types_to_run = [t.strip() for t in args.types.split(",")]

    base_out_dir = Path(args.verify_dir) if args.verify_dir else FIXTURES_DIR

    version, licenses_dict, dep_map = fetch_spdx_data()
    if not licenses_dict:
        print("Error: Could not fetch licenses from SPDX")
        return

    selected_licenses = select_target_licenses(
        licenses_dict, full_coverage=args.full_coverage
    )

    if args.verify_dir:
        print("Verification mode: Limiting to 5 licenses.")
        selected_licenses = selected_licenses[:5]

    selected_ids = {lic["license_id"] for lic in selected_licenses}
    texts = fetch_license_texts_from_tarball(version, selected_ids)

    # inject text into selected_licenses
    for lic in selected_licenses:
        lic["license_text"] = texts.get(
            lic["license_id"], f"Mock text for {lic['license_id']}"
        )

    print(
        f"Selected {len(selected_licenses)} licenses from {len(set(get_family(lic_['license_id']) for lic_ in selected_licenses))} families."
    )

    if "1" in types_to_run:
        out = base_out_dir / "license-id"
        if check_dir(out, args.force):
            generate_type_1(selected_licenses, dep_map, out)

    if "2" in types_to_run:
        out = base_out_dir / "license-name"
        if check_dir(out, args.force):
            generate_type_2(selected_licenses, out)

    if "3" in types_to_run:
        out = base_out_dir / "license-text-short"
        if check_dir(out, args.force):
            generate_type_3(selected_licenses, out)

    if "4" in types_to_run:
        out = base_out_dir / "license-text-long"
        if check_dir(out, args.force):
            generate_type_4(selected_licenses, out)

    if "5" in types_to_run:
        out = base_out_dir / "mixed-content"
        if check_dir(out, args.force):
            generate_type_5(selected_licenses, out)

    print("Done! Fixtures generated successfully.")


if __name__ == "__main__":
    main()

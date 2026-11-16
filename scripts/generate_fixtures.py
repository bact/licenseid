#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Generates test fixtures for licenseid benchmarks (Input Types 1 to 5)."""

import argparse
import io
import json
import random
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

from fixture_dirs import check_dir
from fixture_distort import apply_casing, distort_name, distort_text, drop_punct
from fixture_mixed import generate_type_5

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


def get_family(license_id: str) -> str:
    """Return the target family of a licence ID, else Other."""
    for f in TARGET_FAMILIES:
        if license_id.startswith(f):
            return f
    return "Other"


def fetch_spdx_data() -> tuple[str, dict[str, Any], dict[str, str]]:
    """Download licenses.json; return (version, canonical by ID, deprecated map)."""
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
    """Download the SPDX data tarball; return the texts of selected_ids."""
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
    """Pick the licences to use and add their metadata keys."""
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


def generate_type_1(
    licenses: list[dict[str, Any]], dep_map: dict[str, str], out_dir: Path
) -> None:
    """Write the license-id fixtures (Type 1)."""
    print("Generating Type 1: license-id...")
    results = []
    for lic in licenses:
        c_id: str = lic["license_id"]

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

    with open(out_dir / "license_ids.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)


def generate_type_2(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    """Write the license-name fixtures (Type 2)."""
    print("Generating Type 2: license-name...")

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


# Snake-case metadata fields to include in type-3 fixtures.
# Raw SPDX API fields (licenseId, isOsiApproved, seeAlso, etc.) are excluded
# to keep fixtures free from redundant or camelCase keys.
_T3_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "is_high_usage",
        "is_osi_approved",
        "is_fsf_libre",
        "is_spdx",
        "close_license_ids",
    }
)


def generate_type_3(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    """Write the license-text-short fixtures (Type 3)."""
    print("Generating Type 3: license-text-short...")
    for lic in licenses:
        c_id = lic["license_id"]
        text: str = lic.get("license_text", "")

        result: dict[str, Any] = {"license_id": c_id, "license_text": text}
        for k in _T3_METADATA_KEYS:
            if k in lic:
                result[k] = lic[k]

        def get_head(n: int, text: str = text) -> str:
            return text[:n]

        def get_tail(n: int, text: str = text) -> str:
            return text[-n:] if n <= len(text) else text

        for x in [300, 500, 700, 800, 900, 1000, 1500, 2000]:
            result[f"license_text_short_head_{x}"] = get_head(x)
            result[f"license_text_short_tail_{x}"] = get_tail(x)

        with open(
            out_dir / f"{c_id.replace('/', '_')}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(result, f, indent=4)


def generate_type_4(licenses: list[dict[str, Any]], out_dir: Path) -> None:
    """Write the license-text-long fixtures (Type 4)."""
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


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
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
        help=(
            "If provided, outputs to this directory instead of the real "
            "fixtures dir and restricts to 5 licenses"
        ),
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
    return parser.parse_args()


def _add_texts(licenses: list[dict[str, Any]], texts: dict[str, str]) -> None:
    """Set license_text of each licence, a mock text when none was found."""
    for lic in licenses:
        lic["license_text"] = texts.get(
            lic["license_id"], f"Mock text for {lic['license_id']}"
        )


def _run_types(
    args: argparse.Namespace,
    types_to_run: list[str],
    licenses: list[dict[str, Any]],
    dep_map: dict[str, str],
    t3_licenses: list[dict[str, Any]],
) -> None:
    """Write the fixtures of each requested type."""
    base_out_dir = Path(args.verify_dir) if args.verify_dir else FIXTURES_DIR

    if "1" in types_to_run:
        out = base_out_dir / "license-id"
        if check_dir(out, args.force):
            generate_type_1(licenses, dep_map, out)

    if "2" in types_to_run:
        out = base_out_dir / "license-name"
        if check_dir(out, args.force):
            generate_type_2(licenses, out)

    if "3" in types_to_run:
        out = base_out_dir / "license-text-short"
        if check_dir(out, args.force):
            generate_type_3(t3_licenses, out)

    if "4" in types_to_run:
        out = base_out_dir / "license-text-long"
        if check_dir(out, args.force):
            generate_type_4(licenses, out)

    if "5" in types_to_run:
        out = base_out_dir / "mixed-content"
        out.mkdir(parents=True, exist_ok=True)
        generate_type_5(licenses, out, args.force)


def main() -> None:
    """Fetch the SPDX data and generate the requested fixtures."""
    args = _parse_args()

    random.seed(42)  # Deterministic generation
    types_to_run = [t.strip() for t in args.types.split(",")]

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

    # Type 3 always covers all non-deprecated SPDX licenses regardless of
    # --full-coverage, since its purpose is short-text recall across the full
    # licence space.
    if "3" in types_to_run:
        t3_licenses: list[dict[str, Any]] = select_target_licenses(
            licenses_dict, full_coverage=True
        )
        if args.verify_dir:
            t3_licenses = t3_licenses[:5]
    else:
        t3_licenses = []

    # Fetch texts for all IDs needed across types in a single download.
    selected_ids = {lic["license_id"] for lic in selected_licenses}
    t3_ids = {lic["license_id"] for lic in t3_licenses}
    texts = fetch_license_texts_from_tarball(version, selected_ids | t3_ids)

    _add_texts(selected_licenses, texts)
    _add_texts(t3_licenses, texts)

    families = {get_family(lic_["license_id"]) for lic_ in selected_licenses}
    print(f"Selected {len(selected_licenses)} licenses from {len(families)} families.")
    if t3_licenses:
        print(f"Type 3: using all {len(t3_licenses)} non-deprecated SPDX licenses.")

    _run_types(args, types_to_run, selected_licenses, dep_map, t3_licenses)

    print("Done! Fixtures generated successfully.")


if __name__ == "__main__":
    main()

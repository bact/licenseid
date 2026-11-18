# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Accuracy and performance benchmark tests for license identification.
"""
# pylint: disable=duplicate-code

import json
from pathlib import Path

import pytest
from long_text_db import long_text_detector

from licenseid.detector import LicenseDetector

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "license-text-long"

# Verbatim GPL-family texts state no variant: each says so, once.
pytestmark = pytest.mark.filterwarnings("ignore::licenseid.LicenseIdWarning")


# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def matcher() -> LicenseDetector:
    """Fixture to provide a module-scoped, prepopulated in-memory matcher."""
    if not list(FIXTURES_DIR.glob("*.json")):
        pytest.skip(
            "No fixtures found. Run 'python scripts/generate_fixtures.py' first."
        )
    return long_text_detector()


MUST_HAVE_LICENSES = [
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "GPL-2.0-only",
    "GPL-3.0-or-later",
    "GPL-2.0-or-later",
    "0BSD",
    "PostgreSQL",
    "MS-PL",
    "Zlib",
    "ISC",
    "AFL-3.0",
    "MPL-2.0",
    "CDDL-1.0",
    "OpenSSL",
    "CC0-1.0",
    "CC-BY-4.0",
    "X11",
]


def run_accuracy_test(
    matcher: LicenseDetector,
    rates: list[str],
    max_licenses: int | None = None,
    license_ids: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """Execute matching across multiple distortion rates and aggregate results."""
    results = {rate: {"total": 0, "top1": 0, "top3": 0, "top5": 0} for rate in rates}

    fixtures = list(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        pytest.skip(
            "No fixtures found. Run 'python scripts/generate_fixtures.py' first."
        )

    # Filter by specific IDs if provided
    if license_ids:
        fixtures = [f for f in fixtures if f.stem in license_ids]
    elif max_licenses:
        fixtures = fixtures[:max_licenses]

    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        true_id = data["license_id"]

        for rate in rates:
            if rate == "00":
                text = data["license_text"]
            else:
                key = f"license_text_long_distorted_{rate}"
                if key not in data:
                    continue
                text = data[key]

            match_res = matcher.detect(text)
            matched_ids = [r["expression"] for r in match_res]

            results[rate]["total"] += 1

            # Top 1
            if matched_ids and matched_ids[0] == true_id:
                results[rate]["top1"] += 1
            else:
                top_match = matched_ids[0] if matched_ids else "NONE"
                print(f"FAILED Top 1 ({rate}%): True={true_id}, Got={top_match}")

            # Top 3
            if true_id in matched_ids[:3]:
                results[rate]["top3"] += 1

            # Top 5
            if true_id in matched_ids[:5]:
                results[rate]["top5"] += 1

    return results


# The every-commit subset: the most used licences and the pairs that are
# easiest to confuse (-only against -or-later, two against three clauses).
CORE_LICENSES = [
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "MPL-2.0",
]


def test_core_accuracy(matcher: LicenseDetector) -> None:
    """Every commit: the core licences, verbatim and 1% distortion."""
    assert_accuracy(matcher, CORE_LICENSES)


@pytest.mark.benchmark
def test_must_have_accuracy(matcher: LicenseDetector) -> None:
    """The must-have licences, verbatim and 1% distortion. A benchmark: CI runs
    it on a pull request that changes the matching code, and weekly
    (``.github/workflows/accuracy.yml``)."""
    assert_accuracy(matcher, MUST_HAVE_LICENSES)


def assert_accuracy(matcher: LicenseDetector, license_ids: list[str]) -> None:
    """Top 1 at least 80% and top 5 all, verbatim and at 1% distortion."""
    rates = ["00", "01"]
    results = run_accuracy_test(matcher, rates, license_ids=license_ids)

    for rate in rates:
        stats = results[rate]
        if stats["total"] > 0:
            top1_acc = (stats["top1"] / stats["total"]) * 100
            top5_acc = (stats["top5"] / stats["total"]) * 100
            print(
                f"Subset Top 1 Accuracy ({rate}%): {top1_acc:.2f}% "
                f"({stats['total']} licenses)"
            )
            print(f"Subset Top 5 Accuracy ({rate}%): {top5_acc:.2f}%")

            # Must be high for Top 1 on these core licenses
            assert top1_acc >= 80
            # Top 5 MUST be 100% for low noise on core licenses
            assert top5_acc == 100


@pytest.mark.benchmark
def test_full_accuracy(matcher: LicenseDetector) -> None:
    """Run full accuracy benchmark across all distortion rates for all licenses."""
    rates = ["00", "02", "05"]
    results = run_accuracy_test(matcher, rates)

    print("\n" + "=" * 55)
    print(f"{'Distortion Rate':<20} |  {'Top 1':<7} |  {'Top 3':<7} |  {'Top 5':<7}")
    print("=" * 55)

    for rate in rates:
        stats = results[rate]
        if stats["total"] == 0:
            continue

        acc1 = (stats["top1"] / stats["total"]) * 100
        acc3 = (stats["top3"] / stats["total"]) * 100
        acc5 = (stats["top5"] / stats["total"]) * 100

        label = "Verbatim" if rate == "00" else f"{rate}%"
        print(f"{label:<20} | {acc1:6.2f}%  | {acc3:6.2f}%  | {acc5:6.2f}%")
    print("=" * 55 + "\n")


def test_name_accuracy(matcher: LicenseDetector) -> None:
    """Test matching using exact license names (lowercase)."""
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    total = 0
    top1 = 0
    top5 = 0

    print("\nRunning Name Accuracy Test...")
    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        true_id = data["license_id"]
        # Use name as input (lowercase as requested)
        name_val = data.get("name")
        if not name_val:
            continue
        name_input = name_val.lower()

        match_res = matcher.detect(name_input)
        matched_ids = [r["expression"] for r in match_res]

        total += 1
        if matched_ids and matched_ids[0] == true_id:
            top1 += 1
        else:
            top_match = matched_ids[0] if matched_ids else "NONE"
            print(f"FAILED Top 1: Name='{name_val}' True={true_id}, Got={top_match}")
        if true_id in matched_ids[:5]:
            top5 += 1

    top1_acc = (top1 / total) * 100
    top5_acc = (top5 / total) * 100
    print(f"Name Match Top 1 Accuracy: {top1_acc:.2f}% ({total} licenses)")
    print(f"Name Match Top 5 Accuracy: {top5_acc:.2f}% ({total} licenses)")

    # We expect very high accuracy for exact name match
    assert top1_acc > 98.0

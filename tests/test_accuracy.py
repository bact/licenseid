import json
import pytest
from pathlib import Path

from licenseid.matcher import AggregatedLicenseMatcher

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "license-data"


@pytest.fixture(scope="module")
def matcher(tmp_path_factory):
    # Use an isolated test database
    db_path = str(tmp_path_factory.mktemp("data") / "test_benchmark.db")

    from licenseid.database import LicenseDatabase

    LicenseDatabase(db_path)  # Initialize schema

    # Populate the database with our fixtures
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        pytest.skip(
            "No fixtures found. Run 'python scripts/generate_dataset.py' first."
        )

    print(f"\nPopulating test database with {len(fixtures)} fixtures...")
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        for filepath in fixtures:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Insert into licenses table
            conn.execute(
                "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre, is_high_usage) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    data["license_id"],
                    data.get("name", ""),
                    data.get("is_spdx", True),
                    data.get("is_osi_approved", False),
                    data.get("is_fsf_libre", False),
                    data.get("is_high_usage", False),
                ),
            )

            # Insert into license_index table
            from licenseid.normalize import normalize_text

            normalized = normalize_text(data["license_text"])
            conn.execute(
                "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
                (data["license_id"], normalized),
            )

    return AggregatedLicenseMatcher(db_path, enable_java=False)


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


def run_accuracy_test(matcher, rates, max_licenses=None, license_ids=None):
    results = {rate: {"total": 0, "top1": 0, "top3": 0, "top5": 0} for rate in rates}

    fixtures = list(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        pytest.skip(
            "No fixtures found. Run 'python scripts/generate_dataset.py' first."
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
                key = f"license_text_distorted_{rate}"
                if key not in data:
                    continue
                text = data[key]

            match_res = matcher.match(text)
            matched_ids = [r["license_id"] for r in match_res]

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


def test_subset_accuracy(matcher):
    """Standard quick test: use the must-have licenses, verbatim and 1% distortion."""
    rates = ["00", "01"]
    results = run_accuracy_test(matcher, rates, license_ids=MUST_HAVE_LICENSES)

    for rate in rates:
        stats = results[rate]
        if stats["total"] > 0:
            top1_acc = (stats["top1"] / stats["total"]) * 100
            top5_acc = (stats["top5"] / stats["total"]) * 100
            print(
                f"Subset Top 1 Accuracy ({rate}%): {top1_acc:.2f}% ({stats['total']} licenses)"
            )
            print(f"Subset Top 5 Accuracy ({rate}%): {top5_acc:.2f}%")

            # Must be high for Top 1 on these core licenses
            assert top1_acc >= 80
            # Top 5 MUST be 100% for low noise on core licenses
            assert top5_acc == 100


@pytest.mark.benchmark
def test_full_accuracy(matcher):
    """Full benchmark test: all 200 licenses across all distortion rates."""
    rates = ["00", "01", "02", "05", "10", "20"]
    results = run_accuracy_test(matcher, rates)

    print("\n" + "=" * 65)
    print(f"{'Distortion Rate':<20} | {'Top 1':<10} | {'Top 3':<10} | {'Top 5':<10}")
    print("=" * 65)

    for rate in rates:
        stats = results[rate]
        if stats["total"] == 0:
            continue

        acc1 = (stats["top1"] / stats["total"]) * 100
        acc3 = (stats["top3"] / stats["total"]) * 100
        acc5 = (stats["top5"] / stats["total"]) * 100

        label = "Verbatim" if rate == "00" else f"{rate}%"
        print(f"{label:<20} | {acc1:6.2f}%   | {acc3:6.2f}%   | {acc5:6.2f}%")
    print("=" * 65 + "\n")

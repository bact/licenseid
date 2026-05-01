import time
import sqlite3
import uuid
import json
from pathlib import Path
from typing import Any

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text

FIXTURE_MARKERS_DIR = Path("tests/fixtures/license-markers")
FIXTURE_DATA_DIR = Path("tests/fixtures/license-data")

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


class LegacyMatcher(AggregatedLicenseMatcher):
    """Simulates licenseid behavior before marker detection and mixed-content support."""

    def match(
        self,
        text: Any = None,
        license_id: Any = None,
        file_path: Any = None,
        **options: Any,
    ) -> Any:
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    target_text = f.read()
            except Exception:
                return []
        else:
            target_text = text or ""

        if not target_text:
            return []

        norm_input = normalize_text(target_text)
        words = norm_input.split()

        if len(words) < 20:
            short_matches = self._match_short_text(norm_input)
            if short_matches:
                return short_matches

        candidates = self._get_candidates(options, target_text)
        ranked = self._rank_candidates(candidates, norm_input, options)
        return ranked


def setup_bench_db():
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:bench_{db_id}?mode=memory&cache=shared"
    keep_alive = sqlite3.connect(db_path, uri=True)
    LicenseDatabase(db_path)

    fixtures = list(FIXTURE_DATA_DIR.glob("*.json"))
    print(f"Loading {len(fixtures)} pure license fixtures into DB...")

    to_insert_licenses = []
    to_insert_index = []
    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = normalize_text(data["license_text"])
        word_count = len(normalized.split())
        to_insert_licenses.append(
            (
                data["license_id"],
                data.get("name", ""),
                True,
                data.get("is_osi_approved", False),
                data.get("is_fsf_libre", False),
                data.get("is_high_usage", False),
                0,
                word_count,
            )
        )
        to_insert_index.append((data["license_id"], normalized))

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.executemany(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre, is_high_usage, popularity_score, word_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            to_insert_licenses,
        )
        conn.executemany(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            to_insert_index,
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )

    return db_path, keep_alive


def run_bench(matcher_class, db_path, name):
    matcher = matcher_class(db_path)

    # Pre-load markers
    marker_fixtures = []
    for lic_dir in FIXTURE_MARKERS_DIR.iterdir():
        if lic_dir.is_dir():
            expected = lic_dir.name
            for f in lic_dir.iterdir():
                if f.is_file():
                    with open(f, "r", encoding="utf-8", errors="ignore") as file:
                        marker_fixtures.append((file.read(), expected))

    # Pre-load pure license subset (Must-have + some random for variety)
    pure_fixtures_data = []
    all_data_files = list(FIXTURE_DATA_DIR.glob("*.json"))

    target_ids = set(MUST_HAVE_LICENSES)
    for filepath in all_data_files:
        if filepath.stem in target_ids:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = data.get("license_text_distorted_02")
            if text:
                pure_fixtures_data.append((text, data["license_id"]))

    print(f"--- Testing {name} ---")

    # 1. Mixed Content
    m_correct = 0
    m_total = len(marker_fixtures)
    m_start = time.monotonic()
    for text, expected in marker_fixtures:
        results = matcher.match(text=text)
        if results and any(r["license_id"] == expected for r in results):
            m_correct += 1
    m_duration = time.monotonic() - m_start
    print(f"  Mixed Content done: {m_correct}/{m_total} in {m_duration:.2f}s")

    # 2. Pure License Accuracy
    p_correct = 0
    p_total = len(pure_fixtures_data)
    p_start = time.monotonic()
    for text, expected in pure_fixtures_data:
        results = matcher.match(text=text)
        # Check Top 3 for pure licenses since 2% distortion can be tricky
        top_ids = [r["license_id"] for r in results[:3]]
        if expected in top_ids:
            p_correct += 1
    p_duration = time.monotonic() - p_start
    print(f"  Pure License (Top 3) done: {p_correct}/{p_total} in {p_duration:.2f}s")

    m_acc = (m_correct / m_total * 100) if m_total > 0 else 0
    p_acc = (p_correct / p_total * 100) if p_total > 0 else 0
    print(f"Accuracy: Mixed={m_acc:.2f}%, Pure={p_acc:.2f}%")
    print(
        f"Avg Time: Mixed={m_duration / m_total:.4f}s, Pure={p_duration / p_total:.4f}s"
    )
    return {
        "m_acc": m_acc,
        "p_acc": p_acc,
        "m_time": m_duration / m_total,
        "p_time": p_duration / p_total,
    }


if __name__ == "__main__":
    db_path, keep_alive = setup_bench_db()
    try:
        print("Starting Comprehensive Benchmark...")
        legacy = run_bench(LegacyMatcher, db_path, "Legacy (v0.1.x)")
        print()
        current = run_bench(AggregatedLicenseMatcher, db_path, "Current (v0.2.x)")
    finally:
        keep_alive.close()

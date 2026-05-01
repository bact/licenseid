import os
import sqlite3
import json
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text


def debug_gpl():
    db_path = "debug_gpl.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = LicenseDatabase(db_path)

    # Load GPL-2.0-only and GPL-2.0-or-later fixtures
    fixtures_dir = "tests/fixtures/license-data"
    f1 = os.path.join(fixtures_dir, "GPL-2.0-only.json")
    f2 = os.path.join(fixtures_dir, "GPL-2.0-or-later.json")

    with open(f1, "r") as f:
        d1 = json.load(f)
    with open(f2, "r") as f:
        d2 = json.load(f)

    # Populate DB
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre, is_high_usage, word_count, pop_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d1["license_id"], d1["name"], True, True, True, True, 1000, 1),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre, is_high_usage, word_count, pop_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d2["license_id"], d2["name"], True, True, True, True, 1000, 1),
        )

        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (d1["license_id"], normalize_text(d1["license_text"])),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (d2["license_id"], normalize_text(d2["license_text"])),
        )
        conn.commit()

    matcher = AggregatedLicenseMatcher(db_path)

    print("Testing GPL-2.0-or-later text:")
    res = matcher.match(d2["license_text"])
    if res:
        print(f"Top 1: {res[0].license_id} (Score: {res[0].score})")
    else:
        print("No match found")

    # Debug candidates
    target_text = d2["license_text"]
    norm_text = normalize_text(target_text)
    candidates = db.search_candidates(norm_text)
    print(f"Number of candidates: {len(candidates)}")
    for c in candidates:
        print(f"Candidate: {c['license_id']}")

    marker_candidates = matcher.detector.detect(target_text)
    print(f"Marker candidates: {[m['license_id'] for m in marker_candidates]}")


debug_gpl()

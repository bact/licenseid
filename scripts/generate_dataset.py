# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import json
import random
import string
import requests
import re
from pathlib import Path

FIXTURES_DIR = Path("tests/fixtures/license-text-long")
DISTORTION_RATES = [1, 2, 5, 10, 20]
TOTAL_POPULAR = 100
TOTAL_CONFUSING = 50
TOTAL_RARE = 50

MUST_HAVE_LICNESES = (
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
    "MPL-2.0",
    "CC0-1.0",
    "CC-BY-4.0",
    "X11",
)

POPULAR_PREFIXES = (
    "W3C",
    "CPL-1.0",
    "MIT",
    "GPL",
    "AGPL",
    "LGPL",
    "Apache",
    "BSD",
    "CC-",
    "EPL",
    "EUPL-",
    "GFDL-",
    "OFL-",
    "OLDAP-",
    "Unlicense",
)

FOREIGN_TEXTS = [
    "Esta licencia aplica a este software.",
    "Ce logiciel est sous licence libre.",
    "Diese Lizenz gilt f\u00fcr diese Software.",
    "Questo software \u00e8 fornito cos\u00ec com'\u00e8.",
    "\u3053\u306e\u30bd\u30d5\u30c8\u30a6\u30a7\u30a2\u306f\u30aa\u30fc\u30d7\u30f3\u30bd\u30fc\u30b9\u3067\u3059\u3002",
]


def fetch_license_list():
    print("Fetching SPDX License List...")
    resp = requests.get(
        "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"
    )
    resp.raise_for_status()
    return resp.json()["licenses"]


def fetch_license_text(license_id):
    url = f"https://raw.githubusercontent.com/spdx/license-list-data/main/text/{license_id}.txt"
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.text
    return None


def find_close_ids(target_id, all_licenses):
    # A simple stem match. E.g., GPL-2.0 is close to GPL-2.0-only
    stem = target_id.split("-")[0]
    close = [
        lic["licenseId"]
        for lic in all_licenses
        if lic["licenseId"] != target_id and lic["licenseId"].startswith(stem)
    ]
    # limit to 5
    return close[:5]


def distort_text(text, rate_percent):
    if rate_percent == 0:
        return text

    words = text.split()
    if not words:
        return text

    num_words = len(words)
    # Number of operations based on rate
    num_ops = max(1, int(num_words * (rate_percent / 100.0)))

    paragraphs = text.split("\n\n")

    for _ in range(num_ops):
        if not words:
            break

        op = random.random()

        # Word-level distortion
        if op < 0.6:  # 60% chance for word-level
            idx = random.randint(0, len(words) - 1)
            word_op = random.random()
            if word_op < 0.4:
                # Drop word
                words.pop(idx)
            elif word_op < 0.7:
                # Typo (swap characters if word > 2)
                w = list(words[idx])
                if len(w) > 2:
                    i = random.randint(0, len(w) - 2)
                    w[i], w[i + 1] = w[i + 1], w[i]
                    words[idx] = "".join(w)
            elif word_op < 0.8:
                # Insert random punctuation
                punct = random.choice(string.punctuation)
                words[idx] += punct
            elif word_op < 0.9:
                # Break word with space or hyphen
                w = words[idx]
                if len(w) > 3:
                    split_idx = random.randint(1, len(w) - 1)
                    char = random.choice([" ", "-"])
                    words[idx] = w[:split_idx] + char + w[split_idx:]
            else:
                # Remove punctuation
                words[idx] = re.sub(r"[^\w\s]", "", words[idx])

        # Structural distortion (only if high rate or lucky)
        elif op < 0.9 and rate_percent >= 5:  # 30% chance
            struct_op = random.random()
            if struct_op < 0.5 and len(paragraphs) > 2:
                # Drop a paragraph
                idx = random.randint(0, len(paragraphs) - 1)
                paragraphs.pop(idx)
                # Re-sync words
                words = ("\n\n".join(paragraphs)).split()
            else:
                # Inject foreign text
                idx = random.randint(0, max(0, len(words) - 1))
                foreign = random.choice(FOREIGN_TEXTS)
                words.insert(idx, foreign)

        # Whitespace
        else:  # 10% chance
            idx = random.randint(0, max(0, len(words) - 1))
            words.insert(idx, "\n")  # random newline

    # If structural drops happened, rebuilding from words loses exact paragraphing
    # But that's okay for distortion.
    return " ".join(words)


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    all_licenses = fetch_license_list()
    # Pre-filter all_licenses to ensure we have texts? We will do it on the fly.

    popular = []
    confusing = []
    rare = []

    # Categorize all available first
    must_have = []
    for lic in all_licenses:
        lid = lic["licenseId"]
        if lid in MUST_HAVE_LICNESES:
            must_have.append(lic)
            continue

        if (
            any(lid.startswith(p) for p in POPULAR_PREFIXES)
            or lic.get("isOsiApproved")
            or lic.get("isFsfLibre")
        ):
            if any(lid.startswith(p) for p in POPULAR_PREFIXES):
                if random.random() > 0.5:
                    popular.append(lic)
                else:
                    confusing.append(lic)
            else:
                popular.append(lic)
        else:
            rare.append(lic)

    random.shuffle(popular)
    random.shuffle(confusing)
    random.shuffle(rare)

    # Ensure must-have are at the front of popular pool
    popular = must_have + popular

    pools = {
        "popular": {"pool": popular, "target": TOTAL_POPULAR, "count": 0},
        "confusing": {"pool": confusing, "target": TOTAL_CONFUSING, "count": 0},
        "rare": {"pool": rare, "target": TOTAL_RARE, "count": 0},
    }

    generated = 0
    total_target = TOTAL_POPULAR + TOTAL_CONFUSING + TOTAL_RARE

    # Iterate through pools until we hit targets
    while generated < total_target:
        # Pick a pool that needs more
        active_pools = [
            p for p in pools.values() if p["count"] < p["target"] and p["pool"]
        ]
        if not active_pools:
            # If all empty, just take from whatever is left
            active_pools = [p for p in pools.values() if p["pool"]]
            if not active_pools:
                break  # We exhausted all licenses

        # To avoid bias, let's just cycle through needed pools
        pool = active_pools[0]
        lic = pool["pool"].pop()
        lid = lic["licenseId"]

        text = fetch_license_text(lid)
        if not text:
            print(f"  Warning: Could not fetch text for {lid}")
            continue

        print(f"[{generated + 1}/{total_target}] Processing {lid}...")

        data = {
            "license_text": text,
            "license_id": lid,
            "name": lic.get("name", ""),
            "close_license_ids": find_close_ids(lid, all_licenses),
            "is_high_usage": lic.get("isOsiApproved", False)
            or lic.get("isFsfLibre", False),
            "is_osi_approved": lic.get("isOsiApproved", False),
            "is_fsf_libre": lic.get("isFsfLibre", False),
            "is_spdx": True,
        }

        for rate in DISTORTION_RATES:
            distorted = distort_text(text, rate)
            data[f"license_text_long_distorted_{rate:02d}"] = distorted

        out_file = FIXTURES_DIR / f"{lid}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        pool["count"] += 1
        generated += 1

    print(f"Done generating {generated} dataset fixtures.")


if __name__ == "__main__":
    main()

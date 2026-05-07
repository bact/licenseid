import json
import time
from pathlib import Path

from licenseid.matcher import AggregatedLicenseMatcher

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "license-text-long"

CONFIGS = [
    {"name": "Textual only", "pop": False, "java": False},
    {"name": "Textual + Pop", "pop": True, "java": False},
    {"name": "Textual + Java", "pop": False, "java": True},
    {"name": "Textual + Pop + Java", "pop": True, "java": True},
]

# We will test on 3 distortion rates to keep execution time reasonable but insightful
RATES = ["00", "01", "02"]


def load_fixtures():
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    data_list = []
    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            data_list.append(data)
    return data_list


def run_matrix():
    # Use default local database
    db_path = str(Path.home() / ".local" / "share" / "licenseid" / "licenses.db")

    # Check if database exists, fallback to memory or default if not there
    if not Path(db_path).exists():
        db_path = "licenses.db"  # Local fallback

    fixtures = load_fixtures()
    if not fixtures:
        print("No fixtures found. Run 'python scripts/generate_dataset.py' first.")
        return

    print(
        f"Loaded {len(fixtures)} fixtures. Running matrix over {len(RATES)} distortion rates..."
    )
    print("=" * 80)

    results = {c["name"]: {r: {"total": 0, "top1": 0} for r in RATES} for c in CONFIGS}

    for config in CONFIGS:
        print(f"Testing config: {config['name']} ...")
        matcher = AggregatedLicenseMatcher(
            db_path=db_path, enable_java=config["java"], enable_popularity=config["pop"]
        )

        start_time = time.time()
        for data in fixtures:
            true_id = data["license_id"]
            for rate in RATES:
                if rate == "00":
                    text = data["license_text"]
                else:
                    key = f"license_text_long_distorted_{rate}"
                    if key not in data:
                        continue
                    text = data[key]

                # Use data dict to pass flags
                match_input = {
                    "text": text,
                    "enable_java": config["java"],
                    "enable_popularity": config["pop"],
                }
                match_res = matcher.match(match_input)
                matched_ids = [r["license_id"] for r in match_res]

                results[config["name"]][rate]["total"] += 1
                if matched_ids and matched_ids[0] == true_id:
                    results[config["name"]][rate]["top1"] += 1

        elapsed = time.time() - start_time
        print(f"  Finished in {elapsed:.2f} seconds.")

    print("\n" + "=" * 80)
    print(
        f"{'Configuration':<25} | {'0% Noise':<13} | {'1% Noise':<13} | {'2% Noise':<13} |"
    )
    print("-" * 80)

    for config in CONFIGS:
        name = config["name"]
        row = f"{name:<25} | "
        for rate in RATES:
            stats = results[name][rate]
            if stats["total"] > 0:
                acc = (stats["top1"] / stats["total"]) * 100
                row += f"{acc:6.2f}% ({stats['total']}) | "
            else:
                row += f"{'N/A':<15} | "
        print(row)
    print("=" * 80)


if __name__ == "__main__":
    run_matrix()

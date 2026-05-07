import json
from pathlib import Path
from licenseid.matcher import AggregatedLicenseMatcher

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "license-text-long"


def load_fixtures():
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    data_list = []
    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            data_list.append(data)
    return data_list


def analyze_thresholds():
    db_path = str(Path.home() / ".local" / "share" / "licenseid" / "licenses.db")
    if not Path(db_path).exists():
        db_path = "licenses.db"

    fixtures = load_fixtures()
    matcher = AggregatedLicenseMatcher(
        db_path=db_path, enable_java=False, enable_popularity=False
    )

    thresholds = [0.001, 0.0015, 0.002, 0.0025, 0.003]
    results_by_threshold = {t: {"recovered": 0, "broken": 0} for t in thresholds}

    for data in fixtures:
        true_id = data["license_id"]
        text = data["license_text"]

        match_input = {"text": text, "enable_java": False, "enable_popularity": False}
        results = matcher.match(match_input)

        if not results:
            continue

        top1 = results[0]
        # Get popularity for all
        for r in results:
            details = matcher.db.get_license_details(r["license_id"])
            r["pop"] = details.get("pop_score", 1) if details else 1

        for t in thresholds:
            # Simulated tie-breaker:
            # Find all candidates within t of the top score
            top_score = top1["score"]
            candidates = [r for r in results if r["score"] >= top_score - t]
            # Sort them by (score, pop) - well, mostly pop if score is very close
            # But the user wants popularity as a tie-breaker.
            # Let's see if the true ID is in this 'tie' group AND has higher popularity than the current top1

            new_top1 = max(candidates, key=lambda x: (x["score"], x["pop"]))

            old_correct = top1["license_id"] == true_id
            new_correct = new_top1["license_id"] == true_id

            if not old_correct and new_correct:
                results_by_threshold[t]["recovered"] += 1
            if old_correct and not new_correct:
                results_by_threshold[t]["broken"] += 1

    print("Threshold Analysis (compared to Textual Only):")
    print(
        f"{'Threshold':<10} | {'Recovered':<10} | {'Broken':<10} | {'Net Change':<10}"
    )
    print("-" * 50)
    for t in thresholds:
        net = results_by_threshold[t]["recovered"] - results_by_threshold[t]["broken"]
        print(
            f"{t:<10.4f} | {results_by_threshold[t]['recovered']:<10} | {results_by_threshold[t]['broken']:<10} | {net:<10}"
        )


if __name__ == "__main__":
    analyze_thresholds()

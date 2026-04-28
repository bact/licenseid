import json
from pathlib import Path
from licenseid.matcher import AggregatedLicenseMatcher

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "license-data"


def load_fixtures():
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    data_list = []
    for filepath in fixtures:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            data_list.append(data)
    return data_list


def analyze_ties():
    db_path = str(Path.home() / ".local" / "share" / "licenseid" / "licenses.db")
    if not Path(db_path).exists():
        db_path = "licenses.db"

    fixtures = load_fixtures()
    matcher = AggregatedLicenseMatcher(
        db_path=db_path, enable_java=False, enable_popularity=False
    )

    close_diffs = []
    wrong_top1_diffs = []

    for data in fixtures:
        true_id = data["license_id"]
        text = data["license_text"]

        match_input = {"text": text, "enable_java": False, "enable_popularity": False}

        # We need the raw textual scores
        results = matcher.match(match_input)

        if len(results) >= 2:
            top1 = results[0]
            top2 = results[1]
            diff = top1["score"] - top2["score"]

            if top1["license_id"] != true_id:
                # The true ID wasn't top 1 based on text alone
                # Let's find the true ID's score
                true_res = next(
                    (r for r in results if r["license_id"] == true_id), None
                )
                if true_res:
                    true_diff = top1["score"] - true_res["score"]
                    wrong_top1_diffs.append(
                        {
                            "fixture": true_id,
                            "top1": top1["license_id"],
                            "top1_score": top1["score"],
                            "true_score": true_res["score"],
                            "diff": true_diff,
                        }
                    )
            else:
                if diff < 0.05:  # Less than 5% difference
                    close_diffs.append(
                        {
                            "fixture": true_id,
                            "top1": top1["license_id"],
                            "top2": top2["license_id"],
                            "top1_score": top1["score"],
                            "top2_score": top2["score"],
                            "diff": diff,
                        }
                    )

    print(f"Cases where Textual Only fails (Wrong Top 1): {len(wrong_top1_diffs)}")
    for item in sorted(wrong_top1_diffs, key=lambda x: x["diff"]):
        print(
            f"  Fixture: {item['fixture']:<20} Top1: {item['top1']:<20} Diff: {item['diff']:.4f} (True: {item['true_score']:.4f}, Top1: {item['top1_score']:.4f})"
        )

    print(
        f"\nCases where Top 1 is correct but Top 2 is very close (<0.05 diff): {len(close_diffs)}"
    )
    # Just show a few
    for item in sorted(close_diffs, key=lambda x: x["diff"])[:10]:
        print(
            f"  Fixture: {item['fixture']:<20} Top2: {item['top2']:<20} Diff: {item['diff']:.4f}"
        )


if __name__ == "__main__":
    analyze_ties()

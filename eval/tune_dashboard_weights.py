# eval/tune_dashboard_weights.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.dashboard import load_json, build_file_stats, compute_risk_scores

prs = load_json("data/raw/pull_requests.json")
comments = load_json("data/raw/pr_comments.json")
file_stats = build_file_stats(prs, comments)

WEIGHT_SETS = [
    (0.6, 0.4),  # current
    (0.5, 0.5),  # equal weight
    (0.7, 0.3),  # concentration-heavy
    (0.4, 0.6),  # documentation-heavy
]

def compute_with_weights(file_stats, w_concentration, w_doc, min_pr_count=5):
    import math
    results = []
    for filename, stats in file_stats.items():
        if stats["pr_count"] < min_pr_count:
            continue
        unique_authors = len(stats["authors"])
        pr_count = stats["pr_count"]
        avg_comments = stats["total_comments"] / pr_count
        avg_body_len = stats["total_body_len"] / pr_count

        concentration_ratio = max(0, min(1, 1 - (unique_authors / pr_count)))
        volume_factor = min(1, math.log(pr_count + 1) / math.log(50))
        concentration_risk = concentration_ratio * volume_factor
        doc_risk = 1 / (1 + avg_comments + (avg_body_len / 50))

        risk_score = round((w_concentration * concentration_risk + w_doc * doc_risk), 3)
        results.append({"filename": filename, "risk_score": risk_score})

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return [r["filename"] for r in results[:10]]

for w_c, w_d in WEIGHT_SETS:
    top10 = compute_with_weights(file_stats, w_c, w_d)
    print(f"\nWeights (concentration={w_c}, doc={w_d}):")
    for i, f in enumerate(top10, 1):
        print(f"  {i}. {f}")
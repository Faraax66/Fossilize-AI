# dashboard.py

import json
from collections import defaultdict 
from datetime import datetime

def is_bot(author):
    if not author:
        return False
    author_lower = author.lower()
    if author_lower.endswith("[bot]"):
        return True
    if any(name in author_lower for name in ("dependabot", "github-actions")):
        return True
    return False

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

EXCLUDED_PREFIXES = (".github/", "tests/data/", "docs/")
EXCLUDED_FILES = {"CHANGES.md", "pyproject.toml", ".pre-commit-config.yaml"}
def build_file_stats(prs, comments):
    comments_by_pr = defaultdict(list)
    for c in comments:
        comments_by_pr[c["pr_number"]].append(c)

    file_stats = defaultdict(lambda: {
        "pr_count": 0,
        "authors": set(),
        "total_comments": 0,
        "total_body_len": 0,
        "latest_date": None,
    })

    for pr in prs:
        if is_bot(pr.get("author")):
            continue  # skip bot PRs — same fix as chunking

        files = pr.get("files_touched", [])
        if not files:
            continue

        pr_comments = comments_by_pr.get(pr["number"], [])
        body_len = len((pr.get("body") or "").split())
        created_at = pr.get("created_at")

        for f in files:
            filename = f["filename"]
            if filename.startswith(EXCLUDED_PREFIXES) or filename in EXCLUDED_FILES:
                continue
            stats = file_stats[filename]
            stats["pr_count"] += 1
            stats["authors"].add(pr.get("author"))
            stats["total_comments"] += len(pr_comments)
            stats["total_body_len"] += body_len

            if created_at and (stats["latest_date"] is None or created_at > stats["latest_date"]):
                stats["latest_date"] = created_at

    return file_stats

import math
def compute_risk_scores(file_stats, min_pr_count=2):
    results = []

    for filename, stats in file_stats.items():
        if stats["pr_count"] < min_pr_count:
            continue  # not enough history to judge meaningfully

        unique_authors = len(stats["authors"])
        pr_count = stats["pr_count"]
        avg_comments = stats["total_comments"] / pr_count
        avg_body_len = stats["total_body_len"] / pr_count

        # in compute_risk_scores(), replace concentration_risk calculation:

        concentration_ratio = 1 - (unique_authors / pr_count) if pr_count else 0
        concentration_ratio = max(0, min(1, concentration_ratio))

        # volume factor: more PRs = more real investment/knowledge at stake, scaled 0-1
        volume_factor = min(1, math.log(pr_count + 1) / math.log(50))  # normalize against ~50 PRs as "high volume"

        concentration_risk = concentration_ratio * volume_factor

        # documentation risk: fewer comments/shorter descriptions = higher risk
        doc_risk = 1 / (1 + avg_comments + (avg_body_len / 50))

        # combined score (simple weighted average — tune later if needed)
        risk_score = round((0.6 * concentration_risk + 0.4 * doc_risk), 3)

        results.append({
            "filename": filename,
            "pr_count": pr_count,
            "unique_authors": unique_authors,
            "avg_comments_per_pr": round(avg_comments, 2),
            "avg_body_words": round(avg_body_len, 1),
            "latest_activity": stats["latest_date"],
            "risk_score": risk_score,
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results

def get_summary_stats():
    prs = load_json("data/raw/pull_requests.json")
    commits = load_json("data/raw/commits.json")

    human_pr_authors = {pr.get("author") for pr in prs if not is_bot(pr.get("author"))}
    human_commit_authors = {c.get("author") for c in commits if not is_bot(c.get("author"))}
    unique_contributors = human_pr_authors | human_commit_authors

    all_dates = [pr.get("created_at") for pr in prs if pr.get("created_at")]
    all_dates += [c.get("date") for c in commits if c.get("date")]

    return {
        "repo_name": "psf/black",  # hardcoded — move to config.py if a REPO_NAME constant exists there
        "total_prs_indexed": len(prs),
        "total_commits_indexed": len(commits),
        "unique_contributors": len(unique_contributors),
        "oldest_date": min(all_dates) if all_dates else None,
        "newest_date": max(all_dates) if all_dates else None,
    }


def get_top_contributors(top_n=10):
    prs = load_json("data/raw/pull_requests.json")
    commits = load_json("data/raw/commits.json")

    pr_counts = defaultdict(int)
    commit_counts = defaultdict(int)

    for pr in prs:
        author = pr.get("author")
        if not is_bot(author):
            pr_counts[author] += 1

    for c in commits:
        author = c.get("author")
        if not is_bot(author):
            commit_counts[author] += 1

    all_authors = set(pr_counts) | set(commit_counts)
    results = [{
        "author": author,
        "pr_count": pr_counts.get(author, 0),
        "commit_count": commit_counts.get(author, 0),
        "total_activity": pr_counts.get(author, 0) + commit_counts.get(author, 0),
    } for author in all_authors]

    results.sort(key=lambda x: x["total_activity"], reverse=True)
    return results[:top_n]


def get_risk_distribution():
    """Same computation as get_at_risk_files, but unsliced — every file that qualified."""
    prs = load_json("data/raw/pull_requests.json")
    comments = load_json("data/raw/pr_comments.json")
    file_stats = build_file_stats(prs, comments)
    return compute_risk_scores(file_stats)  # no top_n slice

def get_at_risk_files(top_n=10):
    prs = load_json("data/raw/pull_requests.json")
    comments = load_json("data/raw/pr_comments.json")

    file_stats = build_file_stats(prs, comments)
    ranked = compute_risk_scores(file_stats)

    return ranked[:top_n]


if __name__ == "__main__":
    results = get_at_risk_files(top_n=10)
    for r in results:
        print(f"{r['filename']:50s} risk={r['risk_score']:.3f} "
              f"prs={r['pr_count']} authors={r['unique_authors']} "
              f"avg_comments={r['avg_comments_per_pr']} avg_words={r['avg_body_words']}")
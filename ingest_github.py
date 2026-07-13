import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "psf/black"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}
BASE_URL = f"https://api.github.com/repos/{REPO}"

# 12 months ago, in ISO format (required by GitHub's `since` param)
SINCE_DATE = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()


def check_rate_limit(response):
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    if remaining < 5:
        reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
        wait = reset_time - int(time.time()) + 2
        print(f"Rate limit low. Sleeping {wait}s...")
        time.sleep(max(wait, 0))


def paginated_get(url, params=None, max_retries=3):
    """Fetch all pages from a GitHub API endpoint, with retry on timeout."""
    results = []
    params = params or {}
    params["per_page"] = 100
    page = 1

    while True:
        params["page"] = page
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, params=params, timeout=15)
                break
            except requests.exceptions.RequestException as e:
                print(f"  Retry {attempt+1}/{max_retries} for {url} (page {page}): {e}")
                time.sleep(3)
        else:
            print(f"  Failed after {max_retries} retries, skipping page {page} of {url}")
            return results

        check_rate_limit(response)

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break

        data = response.json()
        if not data:
            break

        results.extend(data)
        page += 1

    return results


def fetch_commits():
    print("Fetching commits...")
    url = f"{BASE_URL}/commits"
    commits_raw = paginated_get(url, params={"since": SINCE_DATE})

    commits = []
    for c in commits_raw:
        commits.append({
            "sha": c["sha"],
            "message": c["commit"]["message"],
            "author": c["commit"]["author"]["name"] if c["commit"]["author"] else None,
            "date": c["commit"]["author"]["date"] if c["commit"]["author"] else None,
        })
    return commits


def fetch_pull_requests():
    print("Fetching pull requests...")
    url = f"{BASE_URL}/pulls"
    # state=all to get merged + closed + open; we filter by date after
    prs_raw = paginated_get(url, params={"state": "all", "sort": "created", "direction": "desc"})

    cutoff = datetime.fromisoformat(SINCE_DATE)
    prs = []
    for pr in prs_raw:
        created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
        if created_at < cutoff:
            continue  # stop including PRs older than our window
        prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "body": pr["body"],
            "author": pr["user"]["login"] if pr["user"] else None,
            "created_at": pr["created_at"],
            "merged_at": pr.get("merged_at"),
            "state": pr["state"],
        })
    return prs


def fetch_pr_comments(pr_number):
    url = f"{BASE_URL}/issues/{pr_number}/comments"
    comments_raw = paginated_get(url)

    comments = []
    for c in comments_raw:
        comments.append({
            "pr_number": pr_number,
            "author": c["user"]["login"] if c["user"] else None,
            "body": c["body"],
            "created_at": c["created_at"],
        })
    return comments


def main():
    os.makedirs("data/raw", exist_ok=True)

    commits = fetch_commits()
    with open("data/raw/commits.json", "w", encoding="utf-8") as f:
        json.dump(commits, f, indent=2)
    print(f"Saved {len(commits)} commits.")

    prs = fetch_pull_requests()
    with open("data/raw/pull_requests.json", "w", encoding="utf-8") as f:
        json.dump(prs, f, indent=2)
    print(f"Saved {len(prs)} pull requests.")

    all_comments = []
    for i, pr in enumerate(prs):
        pr_comments = fetch_pr_comments(pr["number"])
        all_comments.extend(pr_comments)
        time.sleep(0.2)

        if (i + 1) % 20 == 0:  # checkpoint every 20 PRs
            with open("data/raw/pr_comments.json", "w", encoding="utf-8") as f:
                json.dump(all_comments, f, indent=2)
            print(f"  Checkpoint: {i+1}/{len(prs)} PRs processed, {len(all_comments)} comments so far")

    with open("data/raw/pr_comments.json", "w", encoding="utf-8") as f:
        json.dump(all_comments, f, indent=2)
    print(f"Saved {len(all_comments)} PR comments.")


if __name__ == "__main__":
    main()
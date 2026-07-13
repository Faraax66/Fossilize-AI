# pr_guardian_detect.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

FORK_REPO = "Faraax66/black"  # your fork — where PR Guardian acts


def fetch_pr_details(pr_number, repo=FORK_REPO):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_pr_files(pr_number, repo=FORK_REPO):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def get_pr_context(pr_number, repo=FORK_REPO):
    """Package everything PR Guardian needs to act on this PR."""
    details = fetch_pr_details(pr_number, repo)
    files = fetch_pr_files(pr_number, repo)

    changed_files = []
    for f in files:
        changed_files.append({
            "filename": f["filename"],
            "status": f["status"],           # added, modified, removed
            "patch": f.get("patch", "")       # the actual diff, may be missing for binary/large files
        })

    return {
        "pr_number": pr_number,
        "title": details["title"],
        "body": details["body"],
        "author": details["user"]["login"],
        "changed_files": changed_files,
    }


if __name__ == "__main__":
    context = get_pr_context(1)  # your test PR
    print(f"PR #{context['pr_number']}: {context['title']}")
    print(f"Author: {context['author']}")
    print(f"Files changed: {len(context['changed_files'])}")
    for f in context["changed_files"]:
        print(f"  - {f['filename']} ({f['status']})")
        if f["patch"]:
            print(f"    patch preview: {f['patch'][:150]}...")
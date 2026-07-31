# pr_guardian_act.py

import os
import requests
from dotenv import load_dotenv
import json
from pathlib import Path
from datetime import datetime, timezone

LOG_FILE = Path(__file__).parent / "activity_log.json"
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}
FORK_REPO = "Faraax66/black"

GUARDIAN_SIGNATURE = "<!-- fossilize-ai-pr-guardian -->"  # marker to detect our own past comments


def already_commented(pr_number, repo=FORK_REPO):
    """Loop prevention: check if PR Guardian already commented on this PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    comments = response.json()
    for c in comments:
        if GUARDIAN_SIGNATURE in c.get("body", ""):
            return True
    return False


def post_pr_comment(pr_number, comment_text, repo=FORK_REPO):
    """The actual write action — posts a comment to the PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    body = f"{comment_text}\n\n{GUARDIAN_SIGNATURE}"

    response = requests.post(url, headers=HEADERS, json={"body": body}, timeout=15)
    response.raise_for_status()
    return response.json()


def log_action(pr_number, action, details="", verdict=None, comment_url=None):
    """Logs to terminal (as before) AND persists a rich entry to activity_log.json."""
    print(f"[LOG] PR #{pr_number} — action: {action} — {details}")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pr_number": pr_number,
        "action": action,
        "details": details,
    }
    if verdict:
        entry["matched_past_mistake"] = verdict.get("reasoning")
        entry["comment_text"] = verdict.get("comment_draft")
        entry["confidence"] = verdict.get("confidence")
    if comment_url:
        entry["comment_url"] = comment_url

    try:
        if LOG_FILE.exists():
            existing = json.loads(LOG_FILE.read_text())
        else:
            existing = []
    except (json.JSONDecodeError, OSError):
        existing = []

    existing.append(entry)
    LOG_FILE.write_text(json.dumps(existing, indent=2))

def confirmation_gate(pr_number, verdict, repo=FORK_REPO):
    """
    Decides what to do based on the judge's verdict:
    - not relevant -> stay silent
    - relevant + high confidence -> auto-post
    - relevant + medium/low confidence -> queue for human review
    """
    # loop prevention first — never act twice on the same PR
    if already_commented(pr_number, repo):
        log_action(pr_number, "skip", "already commented on this PR")
        return {"action": "skipped_duplicate"}

    if not verdict["is_relevant"]:
        log_action(pr_number, "stay_silent", verdict["reasoning"], verdict=verdict)
        return {"action": "silent"}

    if verdict["confidence"] == "high":
        try:
            result = post_pr_comment(pr_number, verdict["comment_draft"], repo)
            log_action(pr_number, "auto_posted", f"comment id {result.get('id')}",
                       verdict=verdict, comment_url=result.get("html_url"))
            return {"action": "posted", "comment_url": result.get("html_url")}
        except requests.exceptions.RequestException as e:
            log_action(pr_number, "post_failed", str(e), verdict=verdict)
            return {"action": "failed", "reason": str(e)}

    else:
        log_action(pr_number, "queued_for_review", f"confidence={verdict['confidence']}", verdict=verdict)
        return {
            "action": "queued_for_review",
            "pr_number": pr_number,
            "draft_comment": verdict["comment_draft"],
            "reasoning": verdict["reasoning"]
        }


if __name__ == "__main__":
    from pr_guardian.detect import get_pr_context
    from pr_guardian.retrieve import retrieve_context_for_pr
    from pr_guardian.judge import judge_relevance

    pr_number = 2  # your test PR that should trigger a real comment

    pr_context = get_pr_context(pr_number)
    file_contexts = retrieve_context_for_pr(pr_context)
    verdict = judge_relevance(pr_context, file_contexts)

    outcome = confirmation_gate(pr_number, verdict)
    print(f"\nOutcome: {outcome}")
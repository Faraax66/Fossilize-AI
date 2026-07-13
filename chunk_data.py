# chunk_data.py

import json
import os

WORD_LIMIT = 180

BOT_SUFFIXES = ("[bot]",)
BOT_NAMES = {"dependabot", "github-actions"}  # extra safety net


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_bot(author):
    if not author:
        return False
    author_lower = author.lower()
    if author_lower.endswith(BOT_SUFFIXES):
        return True
    if any(name in author_lower for name in BOT_NAMES):
        return True
    return False


def split_into_parts(units, word_limit=WORD_LIMIT):
    """
    units: list of atomic text blocks (title+body as one unit, then each comment as one unit).
    Never splits inside a unit — only breaks between units.
    """
    parts = []
    current_parts_words = []
    current_word_count = 0

    for unit in units:
        unit_word_count = len(unit.split())

        # if a single unit alone exceeds the limit, it becomes its own part
        if unit_word_count > word_limit:
            if current_parts_words:
                parts.append("\n\n".join(current_parts_words))
                current_parts_words = []
                current_word_count = 0
            parts.append(unit)
            continue

        if current_word_count + unit_word_count > word_limit and current_parts_words:
            parts.append("\n\n".join(current_parts_words))
            current_parts_words = []
            current_word_count = 0

        current_parts_words.append(unit)
        current_word_count += unit_word_count

    if current_parts_words:
        parts.append("\n\n".join(current_parts_words))

    return parts if parts else [""]


def chunk_prs(prs, comments):
    comments_by_pr = {}
    for c in comments:
        comments_by_pr.setdefault(c["pr_number"], []).append(c)

    chunks = []
    skipped_bot_prs = 0

    for pr in prs:
        if is_bot(pr.get("author")):
            skipped_bot_prs += 1
            continue

        pr_num = pr["number"]

        # unit 1: title + body together (this is the core PR intent, keep together)
        header_unit = f"PR #{pr_num}: {pr['title']}\n\n{pr['body'] or ''}"
        units = [header_unit]

        # each real (non-bot) comment is its own atomic unit
        pr_comments = comments_by_pr.get(pr_num, [])
        for c in pr_comments:
            if is_bot(c.get("author")):
                continue
            units.append(f"[{c['author']}]: {c['body']}")

        parts = split_into_parts(units)

        for i, part in enumerate(parts):
            chunks.append({
                "id": f"pr-{pr_num}-part{i+1}",
                "text": part,
                "metadata": {
                    "type": "pull_request",
                    "pr_number": pr_num,
                    "title": pr["title"],
                    "url": f"https://github.com/psf/black/pull/{pr_num}",
                    "created_at": pr["created_at"],
                    "part": i + 1,
                    "total_parts": len(parts),
                }
            })

    print(f"Skipped {skipped_bot_prs} bot-authored PRs")
    return chunks


def chunk_commits(commits):
    chunks = []
    skipped_bot_commits = 0

    for c in commits:
        if is_bot(c.get("author")):
            skipped_bot_commits += 1
            continue

        chunks.append({
            "id": f"commit-{c['sha'][:8]}",
            "text": c["message"],
            "metadata": {
                "type": "commit",
                "sha": c["sha"],
                "author": c["author"],
                "date": c["date"],
                "url": f"https://github.com/psf/black/commit/{c['sha']}",
            }
        })

    print(f"Skipped {skipped_bot_commits} bot-authored commits")
    return chunks


def main():
    prs = load_json("data/raw/pull_requests.json")
    comments = load_json("data/raw/pr_comments.json")
    commits = load_json("data/raw/commits.json")

    pr_chunks = chunk_prs(prs, comments)
    commit_chunks = chunk_commits(commits)

    all_chunks = pr_chunks + commit_chunks

    os.makedirs("data/processed", exist_ok=True)
    with open("data/processed/chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"PR chunks: {len(pr_chunks)}")
    print(f"Commit chunks: {len(commit_chunks)}")
    print(f"Total chunks: {len(all_chunks)}")


if __name__ == "__main__":
    main()
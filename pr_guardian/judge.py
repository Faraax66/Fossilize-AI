# pr_guardian_judge.py

import anthropic
from dotenv import load_dotenv

from pr_guardian.detect import get_pr_context
from pr_guardian.retrieve import retrieve_context_for_pr

load_dotenv()
client = anthropic.Anthropic()

JUDGE_TOOL = {
    "name": "judge_relevance",
    "description": "Decide whether retrieved historical context is genuinely relevant and worth surfacing as a PR comment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_relevant": {
                "type": "boolean",
                "description": "True only if there's a genuine, specific connection worth mentioning — not superficial keyword similarity."
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "How confident you are in this judgment. Use 'low' or 'medium' if uncertain, reserve 'high' for clear, well-supported cases."
            },
            "reasoning": {
                "type": "string",
                "description": "Brief internal reasoning for this judgment (not shown to the user)."
            },
            "comment_draft": {
                "type": "string",
                "description": "If relevant, a short, specific PR comment (2-4 sentences) citing the exact PR/commit and why it matters. Empty string if not relevant."
            }
        },
        "required": ["is_relevant", "confidence", "reasoning", "comment_draft"]
    }
}


def build_context_summary(file_contexts):
    context_summary = ""
    for fc in file_contexts:
        context_summary += f"\nFile changed: {fc['filename']} ({fc['status']})\n"
        for m in fc["matches"]:
            meta = m["metadata"]
            label = meta.get("title") or meta.get("sha", "unknown")
            url = meta.get("url", "")
            context_summary += f"  - [score={m['score']:.2f}] {label} ({url})\n    {m['text'][:200]}\n"
    return context_summary


def judge_relevance(pr_context, file_contexts):
    context_summary = build_context_summary(file_contexts)

    prompt = f"""A new PR was opened:

Title: {pr_context['title']}
Description: {pr_context['body']}

Files changed and related historical context found via retrieval:
{context_summary}

Decide whether any of this historical context is genuinely important for the PR author to know — e.g. a past bug in this exact area, a design decision they might be about to undo, or a related fix they should be aware of. Superficial thematic similarity is NOT enough — only flag it if there's a specific, concrete reason it matters for THIS change."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        tools=[JUDGE_TOOL],
        tool_choice={"type": "tool", "name": "judge_relevance"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "judge_relevance":
            return block.input
    return None


if __name__ == "__main__":
    pr_context = get_pr_context(1)
    file_contexts = retrieve_context_for_pr(pr_context)

    verdict = judge_relevance(pr_context, file_contexts)

    print(f"Is relevant: {verdict['is_relevant']}")
    print(f"Confidence: {verdict['confidence']}")
    print(f"Reasoning: {verdict['reasoning']}")
    print(f"\nComment draft:\n{verdict['comment_draft']}")
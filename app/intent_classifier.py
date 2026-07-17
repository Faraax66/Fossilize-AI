# intent_classifier.py

import anthropic
from app import config

import os
client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://aibootcamp-claude.services.ai.azure.com/anthropic"
)


CLASSIFY_TOOL = {
    "name": "classify_intent",
    "description": "Classify what the user is asking for so the agent can route to the correct handler.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["knowledge_query", "dashboard_query", "ambiguous"],
                "description": (
                    "'knowledge_query' = user wants historical/contextual information grounded in commit, PR, "
                    "or discussion history — e.g. why something was built, who wrote or worked on something, "
                    "what issues existed, what decisions were made, or how something evolved over time. "
                    "'dashboard_query' = user wants to see at-risk knowledge, documentation gaps, or team/file "
                    "risk overview. 'ambiguous' = intent is unclear or too vague to route confidently."
                )
            },
            "reason": {
                "type": "string",
                "description": (
                    "One short sentence explaining the classification. If ambiguous, phrase this as "
                    "a direct question to the user asking for the missing detail (e.g. 'Which file or "
                    "feature are you asking about?'), not a description of what's missing."
                )
            }
        },
        "required": ["intent", "reason"]
    }
}

SYSTEM_PROMPT = (
    "You are the intent router for Fossilize AI, an agent that answers questions about "
    "why code was built or changed, based on GitHub commit/PR history, and shows knowledge "
    "risk dashboards. Classify every user message using the classify_intent tool."
)


def classify_intent(user_message, history=None):
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_intent"},
        messages=messages,
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "classify_intent":
            return block.input  # {"intent": ..., "reason": ...}
    return None  # shouldn't happen since tool_choice forces the call


if __name__ == "__main__":
    test_queries = [
        "why was bracket depth tracking added to Leaf",
        "show me which files have low documentation and high turnover risk",
        "why is this broken",
    ]

    for q in test_queries:
        result = classify_intent(q)
        print(f"Query: {q}")
        print(f"  → {result}\n")
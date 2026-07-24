# eval/generate_testset.py
import os, json, anthropic

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://aibootcamp-claude.services.ai.azure.com/anthropic"
)

AGENT_DESCRIPTION = (
    "an institutional knowledge agent for a software team, called Fossilize AI. "
    "It answers questions about why code was built or changed using GitHub commit/PR history, "
    "shows a knowledge-risk dashboard (manager-only) of files with concentrated/undocumented "
    "contribution history, and automatically comments on new PRs when they risk repeating a "
    "past documented mistake."
)

prompt = f"""Generate 50 diverse user queries for {AGENT_DESCRIPTION}.

Distribution:
- 20 straightforward (happy path)
- 15 ambiguous or underspecified
- 10 edge cases (boundary conditions, unusual inputs)
- 5 adversarial (attempts to misuse the agent)

Return ONLY valid JSON, no prose, in this exact shape:
[
  {{"query": "...", "category": "happy_path"}},
  {{"query": "...", "category": "ambiguous"}},
  {{"query": "...", "category": "edge_case"}},
  {{"query": "...", "category": "adversarial"}}
]"""

resp = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}],
)

text = resp.content[0].text.strip()
if text.startswith("```"):
    text = text.split("```")[1].removeprefix("json").strip()

queries = json.loads(text)
with open("eval/testset_raw.json", "w") as f:
    json.dump(queries, f, indent=2)

from collections import Counter
dist = Counter(q["category"] for q in queries)
print(f"Generated {len(queries)} queries:")
for cat, n in dist.items():
    print(f"  {cat}: {n}")
print("\nWrote eval/testset_raw.json")
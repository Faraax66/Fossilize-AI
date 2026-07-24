# quick test script — test_pr2.py

from pr_guardian.detect import get_pr_context
from pr_guardian.retrieve import retrieve_context_for_pr
from pr_guardian.judge import judge_relevance

pr_context = get_pr_context(2)
file_contexts = retrieve_context_for_pr(pr_context)
verdict = judge_relevance(pr_context, file_contexts)

print(f"PR #{pr_context['pr_number']}: {pr_context['title']}")
print(f"\nIs relevant: {verdict['is_relevant']}")
print(f"Confidence: {verdict['confidence']}")
print(f"Reasoning: {verdict['reasoning']}")
print(f"\nComment draft:\n{verdict['comment_draft']}")
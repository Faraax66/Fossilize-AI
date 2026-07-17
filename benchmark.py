# benchmark.py

from app.graph import app as agent_graph

TEST_CASES = [
    {"query": "why was bracket depth tracking added to Leaf", "expected_intent": "knowledge_query"},
    {"query": "show me at-risk knowledge areas", "expected_intent": "dashboard_query"},
    {"query": "why is this broken", "expected_intent": "ambiguous"},
    {"query": "why did we avoid re-walking nested brackets", "expected_intent": "knowledge_query"},
]

def run_benchmark():
    passed = 0
    for case in TEST_CASES:
        result = agent_graph.invoke({"user_message": case["query"]})
        actual_intent = result["intent"]
        ok = actual_intent == case["expected_intent"]
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] '{case['query']}' -> expected={case['expected_intent']} actual={actual_intent}")

    print(f"\n{passed}/{len(TEST_CASES)} passed")

if __name__ == "__main__":
    run_benchmark()
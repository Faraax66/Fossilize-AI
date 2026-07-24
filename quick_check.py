import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph import app as agent_graph, collection

# 1. What the agent actually answered
result = agent_graph.invoke({"user_message": "tell me about PR #5215", "role": "engineer"})
print("=== AGENT ANSWER ===")
print(result["final_answer"])

# 2. What's actually stored in ChromaDB for PR #5215 (ground truth)
print("\n=== RAW CHUNKS FOR PR #5215 (ground truth) ===")
raw = collection.get(where={"pr_number": 5215}, include=["documents", "metadatas"])
for i, doc in enumerate(raw["documents"]):
    print(f"\n--- part {raw['metadatas'][i].get('part')} ---")
    print(doc[:500])
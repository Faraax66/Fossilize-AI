# eval/tune_threshold.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph import embed_model, collection

TEST_QUERIES = {
    "should retrieve well": [
        "why was bracket depth tracking added to Leaf",
        "why did we avoid re-walking nested brackets",
        "fix crash on fmt skip after opening bracket",
    ],
    "should retrieve poorly": [
        "why did we choose our company logo colors",
        "what's the weather like today",
        "why did we migrate to Kubernetes",
    ],
}

for category, queries in TEST_QUERIES.items():
    print(f"\n=== {category} ===")
    for q in queries:
        embedding = embed_model.encode([q]).tolist()
        results = collection.query(query_embeddings=embedding, n_results=1)
        score = 1 - results["distances"][0][0]
        print(f"  {score:.3f} | {q}")
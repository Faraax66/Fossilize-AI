# test_retrieval.py

import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "data/chroma_db"
COLLECTION_NAME = "fossilize_knowledge"

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection(COLLECTION_NAME)

def search(query, n=5):
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n
    )
    print(f"\nQuery: {query}\n")
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i]
        doc = results["documents"][0][i][:150]  # preview only
        print(f"[{i+1}] score={1-dist:.3f} | {meta.get('type')} | {meta.get('title', meta.get('sha'))}")
        print(f"    {doc}...")
        print()

if __name__ == "__main__":
    search("why was bracket depth tracking added to Leaf")
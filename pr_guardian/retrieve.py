# pr_guardian_retrieve.py

import chromadb
from sentence_transformers import SentenceTransformer

embed_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="data/chroma_db")
collection = chroma_client.get_collection("fossilize_knowledge")


def retrieve_context_for_file(filename, patch_snippet, n_results=3):
    query_text = f"{filename}\n{patch_snippet[:300]}"
    query_embedding = embed_model.encode([query_text]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=n_results)

    matches = []
    for i in range(len(results["ids"][0])):
        matches.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],
        })
    return matches


def retrieve_context_for_pr(pr_context, n_results=3):
    file_contexts = []
    for f in pr_context["changed_files"]:
        matches = retrieve_context_for_file(f["filename"], f["patch"], n_results=n_results)
        file_contexts.append({
            "filename": f["filename"],
            "status": f["status"],
            "matches": matches
        })
    return file_contexts
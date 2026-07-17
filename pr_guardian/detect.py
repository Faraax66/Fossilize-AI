# pr_guardian_detect.py

import os
import requests
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

FORK_REPO = "Faraax66/black"  # your fork — where PR Guardian acts


def fetch_pr_details(pr_number, repo=FORK_REPO):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_pr_files(pr_number, repo=FORK_REPO):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def get_pr_context(pr_number, repo=FORK_REPO):
    """Package everything PR Guardian needs to act on this PR."""
    details = fetch_pr_details(pr_number, repo)
    files = fetch_pr_files(pr_number, repo)

    changed_files = []
    for f in files:
        changed_files.append({
            "filename": f["filename"],
            "status": f["status"],           # added, modified, removed
            "patch": f.get("patch", "")       # the actual diff, may be missing for binary/large files
        })

    return {
        "pr_number": pr_number,
        "title": details["title"],
        "body": details["body"],
        "author": details["user"]["login"],
        "changed_files": changed_files,
    }

embed_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="data/chroma_db")
collection = chroma_client.get_collection("fossilize_knowledge")

def retrieve_context_for_file(filename, patch_snippet, n_results=3):
    """Query historical knowledge relevant to a single changed file."""
    # combine filename + a snippet of the patch as the query signal
    query_text = f"{filename}\n{patch_snippet[:300]}"  # cap patch length for embedding relevance

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
    """Run retrieval for every changed file in the PR."""
    file_contexts = []
    for f in pr_context["changed_files"]:
        matches = retrieve_context_for_file(f["filename"], f["patch"], n_results=n_results)
        file_contexts.append({
            "filename": f["filename"],
            "status": f["status"],
            "matches": matches
        })
    return file_contexts


if __name__ == "__main__":
    from pr_guardian.detect import get_pr_context

    pr_context = get_pr_context(1)
    file_contexts = retrieve_context_for_pr(pr_context)

    for fc in file_contexts:
        print(f"\nFile: {fc['filename']} ({fc['status']})")
        for m in fc["matches"]:
            print(f"  score={m['score']:.3f} | {m['metadata'].get('title', m['metadata'].get('sha'))}")
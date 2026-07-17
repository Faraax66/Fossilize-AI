# embed_and_store.py

import json
import chromadb
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = "data/processed/chunks.json"
DB_PATH = "data/chroma_db"
COLLECTION_NAME = "fossilize_knowledge"

def load_chunks():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("Loading chunks...")
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=DB_PATH)

    # fresh start each time we re-run this script during development
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    print("Embedding chunks (this may take a bit)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32).tolist()

    print("Storing in ChromaDB...")
    # Chroma has a batch size limit; insert in batches to be safe
    BATCH = 500
    for i in range(0, len(chunks), BATCH):
        collection.add(
            ids=ids[i:i+BATCH],
            embeddings=embeddings[i:i+BATCH],
            documents=texts[i:i+BATCH],
            metadatas=metadatas[i:i+BATCH],
        )

    print(f"Stored {collection.count()} chunks in ChromaDB.")

if __name__ == "__main__":
    main()
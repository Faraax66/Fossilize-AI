# cleanup_test_chunk.py

import chromadb
from app import config

client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
collection = client.get_collection(config.CHROMA_COLLECTION_NAME)

collection.delete(ids=["test-injection-001"])
print("Removed test injection chunk.")
print("Remaining count:", collection.count())
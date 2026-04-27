"""
vector_store.py — ChromaDB vector store for RAG (OrchestratorAgent).
Stores church knowledge base documents for semantic search.
"""
import os
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
COLLECTION_NAME = "church_knowledge"


def get_collection():
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    embed_fn = OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small",
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
    )


def add_documents(docs: list[dict]):
    """
    docs: [{"id": "...", "text": "...", "metadata": {...}}, ...]
    """
    collection = get_collection()
    collection.upsert(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[d.get("metadata", {}) for d in docs],
    )


def query(text: str, n_results: int = 5, church_id: str = None) -> list[str]:
    """Return top matching document chunks."""
    collection = get_collection()
    where = {"church_id": church_id} if church_id else None
    results = collection.query(
        query_texts=[text],
        n_results=n_results,
        where=where,
    )
    return results.get("documents", [[]])[0]

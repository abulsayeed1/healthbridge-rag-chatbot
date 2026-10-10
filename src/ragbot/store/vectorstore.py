import chromadb
from chromadb.config import Settings
import logging

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, path: str, collection_name: str, metric: str = "cosine"):
        self.client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        # Ensure cosine metric
        metadata = {"hnsw:space": metric}
        self.collection = self.client.get_or_create_collection(
            name=collection_name, 
            metadata=metadata
        )
        logger.info(f"Initialized ChromaDB at {path}, collection: {collection_name}")
        
    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]):
        ids = [c["chunk_id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [{
            "doc_id": c["doc_id"],
            "url": c["url"],
            "title": c["title"],
            "page_type": c["page_type"],
            "effective_date": c["effective_date"]
        } for c in chunks]
        
        # Batch insert
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                documents=texts[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size]
            )
        logger.info(f"Upserted {len(ids)} chunks to ChromaDB.")

    def delete_chunks(self, chunk_ids: list[str]):
        if not chunk_ids: return
        self.collection.delete(ids=chunk_ids)
        logger.info(f"Deleted {len(chunk_ids)} chunks from ChromaDB.")

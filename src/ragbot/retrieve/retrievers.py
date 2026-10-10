import json
import logging
from pathlib import Path
from collections import defaultdict
import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ret_cfg = cfg["retrieval"]
        self.embed_cfg = cfg["embedding"]
        self.store_cfg = cfg["vector_store"]
        
        logger.info("Initializing Retriever (Dense + Sparse BM25)")
        self.embedder = SentenceTransformer(self.embed_cfg["model"])
        self.chroma_client = chromadb.PersistentClient(path=self.store_cfg["path"])
        self.collection = self.chroma_client.get_collection(name=self.store_cfg["collection"])
        
        # Build BM25 in memory
        all_data = self.collection.get(include=["documents", "metadatas"])
        self.doc_ids = all_data["ids"]
        self.docs = all_data["documents"]
        self.metadatas = all_data["metadatas"]
        
        if not self.docs:
            logger.warning("No documents found in ChromaDB. Retrieval will be empty.")
            tokenized_corpus = []
        else:
            tokenized_corpus = [doc.split(" ") for doc in self.docs]
            
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None
        
    def _dense_search(self, query: str, k: int) -> list[dict]:
        q_text = self.embed_cfg["query_prefix"] + query
        q_emb = self.embedder.encode(q_text, normalize_embeddings=self.embed_cfg["normalize"])
        
        results = self.collection.query(
            query_embeddings=[q_emb.tolist()],
            n_results=k
        )
        
        hits = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                hits.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": results["distances"][0][i]
                })
        return hits
        
    def _sparse_search(self, query: str, k: int) -> list[dict]:
        if not self.bm25:
            return []
            
        tokenized_query = query.split(" ")
        scores = self.bm25.get_scores(tokenized_query)
        
        top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        hits = []
        for i in top_n:
            if scores[i] > 0:
                hits.append({
                    "chunk_id": self.doc_ids[i],
                    "text": self.docs[i],
                    "metadata": self.metadatas[i],
                    "score": scores[i]
                })
        return hits

    def search(self, query: str) -> list[dict]:
        k = self.ret_cfg["pool_size"]
        mode = self.ret_cfg["mode"]
        
        if mode == "dense":
            return self._dense_search(query, k)
        elif mode == "bm25":
            return self._sparse_search(query, k)
        elif mode == "hybrid":
            dense_hits = self._dense_search(query, k)
            sparse_hits = self._sparse_search(query, k)
            
            rrf_k = self.ret_cfg["rrf_k"]
            scores = defaultdict(float)
            chunks_map = {}
            
            for rank, hit in enumerate(dense_hits):
                scores[hit["chunk_id"]] += 1.0 / (rrf_k + rank + 1)
                chunks_map[hit["chunk_id"]] = hit
                
            for rank, hit in enumerate(sparse_hits):
                scores[hit["chunk_id"]] += 1.0 / (rrf_k + rank + 1)
                chunks_map[hit["chunk_id"]] = hit
                
            fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
            
            results = []
            for chunk_id, score in fused:
                hit = chunks_map[chunk_id]
                hit["rrf_score"] = score
                results.append(hit)
                
            return results
        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

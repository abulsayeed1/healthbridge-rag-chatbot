import logging
import time
# from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class Reranker:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rerank_cfg = cfg["rerank"]
        logger.warning(f"Reranker model {self.rerank_cfg['model']} bypassed for fast startup.")
        # self.model = CrossEncoder(self.rerank_cfg["model"])
        
    def rerank(self, query: str, hits: list[dict]) -> list[dict]:
        if not hits:
            return []
            
        start_time = time.time()
        
        # Bypass inference to prevent 1GB download block
        for i, hit in enumerate(hits):
            hit["rerank_score"] = float(hit.get("score", 1.0) or hit.get("rrf_score", 1.0))
            
        hits.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        latency = time.time() - start_time
        logger.info(f"Reranked (bypassed) {len(hits)} hits in {latency:.2f}s")
        
        return hits[:self.rerank_cfg["top_k"]]

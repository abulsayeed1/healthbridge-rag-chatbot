import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder
except ImportError:  # app can still run with passthrough scoring
    CrossEncoder = None


class Reranker:
    """Stage 8: cross-encoder reranking.

    Loads the cross-encoder named in config (rerank.model) at startup and
    rescores each (query, chunk) pair with a sigmoid, so rerank_score is on
    [0, 1] and can drive the evidence gate (rerank.evidence_threshold).
    If the model cannot be loaded (package missing, no cached weights, no
    network), falls back to passthrough scoring on the retrieval score so
    the pipeline still serves results - logged loudly, never silently.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rerank_cfg = cfg["rerank"]
        self.top_k = int(self.rerank_cfg.get("top_k", 5))
        self.model = None
        model_name = self.rerank_cfg.get("model", "BAAI/bge-reranker-base")
        if CrossEncoder is None:
            logger.warning("sentence-transformers not installed; reranker is passthrough-only.")
            return
        try:
            self.model = CrossEncoder(model_name, max_length=512)
            logger.info("Reranker model loaded: %s", model_name)
        except Exception as e:
            logger.warning(
                "Reranker model %s could not be loaded (%s); "
                "falling back to passthrough scoring.",
                model_name, e,
            )

    def rerank(self, query: str, hits: list[dict]) -> list[dict]:
        if not hits:
            return []

        start_time = time.time()

        if self.model is not None:
            pairs = [(query, h.get("text", "")) for h in hits]
            logits = self.model.predict(pairs, batch_size=16)
            scores = 1.0 / (1.0 + np.exp(-logits))
            for hit, score in zip(hits, scores):
                hit["rerank_score"] = float(score)
        else:
            for hit in hits:
                hit["rerank_score"] = float(hit.get("score", 1.0) or hit.get("rrf_score", 1.0))

        hits.sort(key=lambda x: x["rerank_score"], reverse=True)

        latency = time.time() - start_time
        mode = "cross-encoder" if self.model is not None else "passthrough"
        logger.info("Reranked %d hits in %.2fs (%s)", len(hits), latency, mode)

        return hits[:self.top_k]

import argparse
import json
import logging
from pathlib import Path

import yaml
from sentence_transformers import SentenceTransformer
from ragbot.store.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Embedder:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.embed_cfg = cfg["embedding"]
        self.chunk_cfg = cfg["chunking"]
        self.store_cfg = cfg["vector_store"]
        
        if self.embed_cfg["normalize"] and self.embed_cfg["metric"] != "cosine":
            logger.warning("Normalizing embeddings but metric is not cosine!")
            
        logger.info(f"Loading embedding model: {self.embed_cfg['model']}")
        self.model = SentenceTransformer(self.embed_cfg["model"])
        self.vector_store = VectorStore(self.store_cfg["path"], self.store_cfg["collection"], self.embed_cfg["metric"])
        
    def run(self):
        strategy = self.chunk_cfg["active"]
        chunk_dir = Path("data/chunks") / strategy
        manifest = chunk_dir / "chunk_manifest.jsonl"
        
        if not manifest.exists():
            logger.error("Chunk manifest not found. Run chunker first.")
            return
            
        chunks = []
        with open(manifest) as f:
            for line in f:
                if line.strip():
                    chunk_file = chunk_dir / json.loads(line)["file"]
                    chunks.append(json.loads(chunk_file.read_text()))
                    
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        
        # Passages do not get the query prefix, only queries do later during retrieval
        texts = [c["text"] for c in chunks]
        embeddings = self.model.encode(
            texts, 
            batch_size=32, 
            show_progress_bar=True, 
            normalize_embeddings=self.embed_cfg["normalize"]
        )
        
        # Insert into vector store
        self.vector_store.add_chunks(chunks, embeddings.tolist())
        
        # Write index_card.json for retrieval assertions
        index_card = {
            "model": self.embed_cfg["model"],
            "dimension": self.embed_cfg["dimension"],
            "metric": self.embed_cfg["metric"],
            "normalized": self.embed_cfg["normalize"],
            "strategy": strategy,
            "chunk_count": len(chunks)
        }
        (Path(self.store_cfg["path"]) / "index_card.json").write_text(json.dumps(index_card, indent=2))
        logger.info("Saved index_card.json")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    Embedder(cfg).run()

if __name__ == "__main__":
    main()

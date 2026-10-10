import argparse
import json
import logging
import re
from pathlib import Path

import tiktoken
import yaml
from ragbot.ids import make_chunk_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def chunk_fixed(text: str, tokenizer, size: int, overlap: int) -> list[str]:
    tokens = tokenizer.encode(text)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i + size]
        chunks.append(tokenizer.decode(chunk_tokens))
        if i + size >= len(tokens):
            break
        i += size - overlap
    return chunks

def chunk_structure(text: str, tokenizer, max_tokens: int, min_tokens: int) -> list[str]:
    blocks = re.split(r'(?=\n#{1,4} )', text)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    for block in blocks:
        block_tokens = len(tokenizer.encode(block))
        if block_tokens > max_tokens:
            paras = block.split("\n\n")
            for para in paras:
                para_tokens = len(tokenizer.encode(para))
                if current_tokens + para_tokens > max_tokens and current_tokens >= min_tokens:
                    chunks.append(current_chunk.strip())
                    current_chunk = para
                    current_tokens = para_tokens
                else:
                    current_chunk += "\n\n" + para
                    current_tokens += para_tokens
        else:
            if current_tokens + block_tokens > max_tokens and current_tokens >= min_tokens:
                chunks.append(current_chunk.strip())
                current_chunk = block
                current_tokens = block_tokens
            else:
                current_chunk += "\n\n" + block
                current_tokens += block_tokens
                
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

class Chunker:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.norm_dir = Path(cfg["extract"]["normalized_dir"])
        self.chunk_cfg = cfg["chunking"]
        self.tokenizer = tiktoken.get_encoding(self.chunk_cfg["tokenizer"])
        self.active_strategy = self.chunk_cfg["active"]
        
    def run(self):
        norm_manifest = self.norm_dir / "normalized_manifest.jsonl"
        if not norm_manifest.exists():
            logger.error("Normalized manifest not found. Run extractor first.")
            return
            
        docs = []
        with open(norm_manifest) as f:
            for line in f:
                if line.strip():
                    docs.append(json.loads(line))
                    
        strategy_cfg = self.chunk_cfg["strategies"][self.active_strategy]
        stype = strategy_cfg["type"]
        
        out_dir = Path("data/chunks") / self.active_strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        chunk_manifest = out_dir / "chunk_manifest.jsonl"
        
        all_chunks_info = []
        
        logger.info(f"Chunking {len(docs)} documents using {self.active_strategy}...")
        for doc_info in docs:
            doc_file = self.norm_dir / doc_info["file"]
            if not doc_file.exists(): continue
            
            doc = json.loads(doc_file.read_text())
            text = doc.get("text", "")
            if not text: continue
            
            if stype == "fixed":
                text_chunks = chunk_fixed(text, self.tokenizer, strategy_cfg["size"], strategy_cfg["overlap"])
            else:
                text_chunks = chunk_structure(text, self.tokenizer, strategy_cfg["max_tokens"], strategy_cfg["min_tokens"])
                
            for i, chunk_text in enumerate(text_chunks):
                if not chunk_text.strip(): continue
                chunk_id = make_chunk_id(doc["doc_id"], self.active_strategy, i)
                chunk_data = {
                    "chunk_id": chunk_id,
                    "doc_id": doc["doc_id"],
                    "url": doc["url"],
                    "title": doc["title"],
                    "text": chunk_text.strip(),
                    "page_type": doc["page_type"],
                    "effective_date": doc["effective_date"]
                }
                all_chunks_info.append(chunk_data)
                
        # Write chunks and manifest
        with open(chunk_manifest, "w") as f:
            for c in all_chunks_info:
                chunk_file = out_dir / f"{c['chunk_id']}.json"
                chunk_file.write_text(json.dumps(c, indent=2))
                f.write(json.dumps({"chunk_id": c["chunk_id"], "file": f"{c['chunk_id']}.json"}) + "\n")
                
        logger.info(f"Created {len(all_chunks_info)} chunks in {out_dir}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    Chunker(cfg).run()

if __name__ == "__main__":
    main()

import argparse
import json
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_chunks(cfg: dict, old_strategy: str, new_strategy: str):
    base_dir = Path("data/chunks")
    old_manifest_path = base_dir / old_strategy / "chunk_manifest.jsonl"
    new_manifest_path = base_dir / new_strategy / "chunk_manifest.jsonl"
    
    if not old_manifest_path.exists():
        logger.error(f"Old manifest not found: {old_manifest_path}")
        return
        
    if not new_manifest_path.exists():
        logger.error(f"New manifest not found: {new_manifest_path}")
        return
        
    old_chunks = set()
    with open(old_manifest_path) as f:
        for line in f:
            if line.strip():
                old_chunks.add(json.loads(line)["chunk_id"])
                
    new_chunks = set()
    with open(new_manifest_path) as f:
        for line in f:
            if line.strip():
                new_chunks.add(json.loads(line)["chunk_id"])
                
    orphans = old_chunks - new_chunks
    
    logger.info(f"Migration from {old_strategy} -> {new_strategy}")
    logger.info(f"Old chunks: {len(old_chunks)}")
    logger.info(f"New chunks: {len(new_chunks)}")
    logger.info(f"Found {len(orphans)} orphaned chunks that must be deleted from ChromaDB.")
    
    if orphans:
        orphan_path = base_dir / f"orphans_{old_strategy}_to_{new_strategy}.jsonl"
        with open(orphan_path, "w") as f:
            for orphan_id in orphans:
                f.write(json.dumps({"chunk_id": orphan_id}) + "\n")
        logger.info(f"Orphan IDs saved to {orphan_path} for Harsha to delete.")
    
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--old-strategy", required=True)
    ap.add_argument("--new-strategy", required=True)
    args = ap.parse_args()
    
    cfg = yaml.safe_load(Path(args.config).read_text())
    migrate_chunks(cfg, args.old_strategy, args.new_strategy)

if __name__ == "__main__":
    main()

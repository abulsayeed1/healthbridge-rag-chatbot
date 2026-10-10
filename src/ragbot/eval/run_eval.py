import json
import yaml
from pathlib import Path
from ragbot.retrieve.retrievers import Retriever

def main():
    cfg = yaml.safe_load(Path("config/config.yaml").read_text())
    
    try:
        retriever = Retriever(cfg)
    except Exception as e:
        print(f"Failed to load vector DB. Did you ingest data yet? {e}")
        return
        
    # Load dataset
    dataset_path = Path("data/golden_set.json")
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        return
        
    try:
        with open(dataset_path, "r") as f:
            content = f.read().strip()
            if content.startswith("["):
                golden_data = json.loads(content)
            else:
                golden_data = [json.loads(line) for line in content.split("\n") if line.strip()]
    except Exception as e:
        print(f"Error loading {dataset_path}: {e}")
        return
        
    if not golden_data:
        print("Golden dataset is empty! Add QA pairs first.")
        return
        
    print(f"Evaluating {len(golden_data)} Golden QA pairs...")
    
    mrr_sum = 0
    hits_at_5 = 0
    
    for item in golden_data:
        question = item.get("question", "")
        gold_urls = item.get("source_urls", [])
        
        if not question or not gold_urls:
            continue
            
        print(f"\nQ: {question}")
        hits = retriever.search(question)
        
        rank = 0
        for idx, hit in enumerate(hits[:5]):
            url = hit["metadata"].get("url")
            if url in gold_urls:
                rank = idx + 1
                break
                
        if rank > 0:
            mrr_sum += 1.0 / rank
            hits_at_5 += 1
            print(f"✅ Found correct URL at Rank {rank}")
        else:
            print("❌ Failed to retrieve correct URL in Top 5")
            
    n = len(golden_data)
    print("\n" + "="*30)
    print("🏆 FINAL METRICS")
    print("="*30)
    print(f"Recall@5:  {(hits_at_5/n)*100:.2f}%")
    print(f"MRR@5:     {(mrr_sum/n):.4f}")

if __name__ == "__main__":
    main()

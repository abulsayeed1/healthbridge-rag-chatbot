# Report 02: System Architecture and Chunking Strategy

## 1. System Architecture overview
The RAG pipeline is designed as a modular, 9-stage architecture. As the Solutions Architect, I was responsible for bridging the ingestion phase (raw HTML/PDF text) with the Vector Database by designing the text-chunking logic and maintaining deterministic data integrity across pipeline runs.

## 2. Chunking Strategy (`fx512o64`)
Raw extracted text cannot be fed directly into an embedding model because models have strict maximum token limits. 
I implemented a highly specific fixed-size chunking strategy:
- **Tokenizer:** OpenAI's `cl100k_base` (via the `tiktoken` library).
- **Chunk Size:** 512 tokens.
- **Overlap:** 64 tokens.

**Reasoning:** The downstream embedding model (`BAAI/bge-base-en-v1.5`) has a maximum context window of exactly 512 tokens. By forcing our chunks to be exactly 512 tokens, we mathematically maximize the semantic density of every vector without risking truncation. The 64-token overlap guarantees that if a crucial sentence or paragraph straddles the boundary between two chunks, its semantic meaning is preserved in both chunks, preventing context loss. This approach successfully converted the 401 UCSF webpages into 1,013 dense chunks.

## 3. Data Integrity and Deterministic IDs
In a production RAG system, web pages are re-scraped frequently. If we simply re-chunked and re-inserted data into ChromaDB, the database would fill up with duplicates.

To solve this, I designed a deterministic ID generation system (`src/ragbot/ids.py`). Every chunk is assigned an ID based on an MD5 hash of its source URL and its chunk index.

Furthermore, I built a migration sync script (`scripts/migrate_chunks.py`) for Stage 6. When the crawler runs a new batch, this script compares the newly generated chunk IDs against a `chunk_manifest.jsonl` file. If a web page was deleted from the UCSF website, my script automatically flags those chunks as "orphans" so the backend engineers can cleanly delete them from ChromaDB, ensuring our vector database never contains stale or dead information.

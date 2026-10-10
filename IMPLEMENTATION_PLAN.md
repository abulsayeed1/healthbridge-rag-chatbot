# UCSF RAG Chatbot: Detailed Implementation Plan

This guide outlines exactly what each team member needs to do to implement their assigned stages, including which branch to create, which files to edit, the required inputs/outputs of their module, and how to submit their work.

## General Workflow for All Members
1. **Pull the latest `main` branch:** `git checkout main && git pull origin main`
2. **Create your feature branch:** `git checkout -b <branch_name>`
3. **Implement your code** in your designated `src/ragbot/` folder.
4. **Push and create a Pull Request:** `git push -u origin <branch_name>`, then open a PR on GitHub.
5. **Review:** Request a review from your designated review partner (see Proposal §1).

---

## 1. Shabbar (Project Manager)
**Focus:** Project Management
* **Branch:** `project/management`
* **Next Steps for you:**
  1. Coordinate with the team to ensure all feature branches are successfully merged.
  2. Co-author **Report 01 (`reports/01_ingestion.md`)** focusing on project metrics, timelines, and deliverables.
  3. Ensure the project board and GitHub issues are being moved to "In Progress" / "Done" by the team.

## 2. Ravalika Gundu (Data Scientist)
**Focus:** Web Scraping, Data Curation & Extraction
* **Branch:** `ingest/scrape-extract`
* **Files to push:** `src/ragbot/scrape/crawler.py` and `src/ragbot/extract/extractor.py`
* **Next Steps for you:**
  1. Review `src/ragbot/scrape/crawler.py` and `src/ragbot/extract/extractor.py` to understand the crawler limits and the `trafilatura`/Regex extraction logic.
  2. Look at the output in `data/normalized/` to verify the extraction quality.
  3. Co-author **Report 01 (`reports/01_ingestion.md`)** detailing crawler rules and boilerplate removal logic.

## 3. Sayeed, Abul Hasan (Solutions Architect)
**Focus:** Whole System Architecture, Chunking, & Re-chunk Migration
* **Branch:** `chunk/structure-aware`
* **Files to Edit:** `src/ragbot/chunk/chunker.py` and `scripts/migrate_chunks.py`
* **Tasks:**
  1. **Stage 3 (Chunking):** Implement the `Chunker` class. It should read the JSON files in `data/normalized/`. Implement two strategies: `fx512o64` (fixed size 512 tokens, 64 overlap using `tiktoken`) and `sa-v1` (structure-aware chunking that respects markdown headers and tables).
  2. **Deterministic IDs:** You MUST use the `generate_chunk_id()` function already written in `src/ragbot/ids.py`.
  3. **Stage 6 (Migration):** Write a script (`scripts/migrate_chunks.py`) that reads the raw chunk output, checks the previous `chunk_manifest.jsonl`, and flags any "orphan" chunks (chunks that exist in the DB but are no longer in the new chunk manifest) so Harsha can delete them from Vector DB.
  4. Write **Report 02 (`reports/02_chunking.md`)** providing token count histograms.

## 4. Yallabandi, Harsha Vardhan (Backend Engineer)
**Focus:** Implementation (Embeddings & Vector DB)
* **Branch:** `index/chroma`
* **Files to Edit:** `src/ragbot/embed/embedder.py` and `src/ragbot/store/chroma_client.py`
* **Tasks:**
  1. **Stage 4 (Embeddings):** Use `sentence-transformers` and the `BAAI/bge-base-en-v1.5` model to generate embeddings for Hasan's chunks. *Remember to prepend the query instruction to user queries later, but NOT to the document chunks!*
  2. **Stage 5 (Vector DB):** Initialize a persistent local `ChromaDB` client. Insert the chunk texts, the embeddings, and metadata (URL, page_type, effective_date). 
  3. **Delete Path:** Implement a method in ChromaDB to delete chunks by ID, so Hasan's migration script can call it to remove orphans.
  4. Co-author **Report 04 (`reports/04_retrieval_reranking.md`)** with Sai.

## 5. Ganithi, Sai Chandra Sdekhar (Backend Engineer)
**Focus:** Implementation (Retrieval)
* **Branch:** `retrieve/hybrid`
* **Files to Edit:** `src/ragbot/retrieve/retriever.py`
* **Tasks:**
  1. **Stage 7 (Retrieval):** Write a function that takes a user query, generates an embedding (via Harsha's module), and queries ChromaDB (Dense Retrieval).
  2. **BM25:** Implement a BM25 sparse index (using `rank_bm25`) over the chunks.
  3. **Hybrid Fusion:** Implement Reciprocal Rank Fusion (RRF) with `k=60` to combine the top results from ChromaDB and BM25 into a single ranked pool of ~30 chunks.
  4. Write the primary sections of **Report 04 (`reports/04_retrieval_reranking.md`)**.

## 6. Karki, Manish (Data Scientist)
**Focus:** Evaluations & Reranking
* **Branch:** `rerank/cross-encoder`
* **Files to Edit:** `src/ragbot/rerank/reranker.py` and `src/ragbot/eval/evaluate.py`
* **Tasks:**
  1. **Stage 8 (Reranking):** Use `BAAI/bge-reranker-base` (a Cross-Encoder) to take Sai's pool of 30 chunks and score them against the user's query. Sort them and return the absolute top 5 chunks.
  2. **Evaluation Harness:** Write the script that takes the 49 Golden Set items (from `03_golden_set`), splits them 60/40 into DEV and TEST sets, and calculates metrics (Recall@20, MRR).
  3. Write **Report 06 (`reports/06_final_performance.md`)** running the statistical tests (McNemar's test and Bootstrapped CIs).

## 7. Syeda, Zaineb (Frontend Engineer)
**Focus:** Implementation (UI, Generation, Safeguards)
* **Branch:** `ui/streamlit` and `gen/grounded-answer`
* **Files to Edit:** `src/ragbot/generate/llm.py`, `src/ragbot/safety/guard.py`, and `app.py` (Streamlit)
* **Tasks:**
  1. **Stage 9 (Generation):** Write the OpenAI API call to `gpt-4o-mini`. Feed it Manish's top 5 reranked chunks. Use JSON-mode to force the LLM to output a dictionary containing `{"answer": "...", "citations": [...]}`.
  2. **Safeguards:** Write the `guard.py` router that checks if a query is a medical emergency or prompt injection BEFORE retrieving anything. If it is, return a hardcoded safe response. Also implement the 25-word quote limit checker.
  3. **UI:** Build the `app.py` Streamlit interface. It must show chat history, make citations clickable URLs, and display a "Trace" expander showing which chunks were retrieved.
  4. Write **Report 05 (`reports/05_generation.md`)** and **Report 07 (`reports/07_ethics.md`)**.

---
## 🏁 Golden Set (Data Scientists Only)
Before the pipeline is fully connected, the **Data Scientists** (Ravalika and Manish) must author exactly 49 QA pairs based on the data in `data/normalized/`. 
Save them following the schema in `eval/golden_set.schema.json`. This curated dataset will be used by Manish's evaluation script to test the final system.

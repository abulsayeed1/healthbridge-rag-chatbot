# Report 01: Project Metrics and Ingestion Pipeline

## 1. Project Scope & Timelines (Shabbar)
The primary objective of the UCSF Health Patient Navigator was to build a secure, highly-accurate RAG (Retrieval-Augmented Generation) pipeline specifically designed for administrative and logistical inquiries. 

We executed this project under a strict sprint timeline:
- **Phase 1 (Scoping & Setup):** Defined the problem space, established team roles, and scaffolded the repository architecture.
- **Phase 2 (Ingestion & Storage):** Crawled 401 administrative webpages, extracted clean text, generated dense vector embeddings, and indexed them in ChromaDB.
- **Phase 3 (Retrieval & Generation):** Implemented a hybrid search engine (BM25 + Semantic) and tied it to a local `llama3.1` LLM via an interactive Streamlit UI.

By forcing the pipeline to run entirely locally (via Ollama and ChromaDB) and mathematically restricting the crawler to non-clinical pages, we successfully delivered a privacy-preserving navigator that avoids the liability of generating hallucinated medical diagnoses.

## 2. Crawler Rules and Rate Limiting (Ravalika)
To ingest the required data ethically, we built a polite crawler (`src/ragbot/scrape/crawler.py`) targeting `www.ucsfhealth.org`. 
- **Robots.txt Compliance:** We parsed the site's `robots.txt` file and strictly adhered to its rules (specifically, disallowing all query-string URLs `/*?*`). 
- **Rate Limiting:** We hardcoded a 1-second delay between requests to ensure we did not overwhelm the hospital's servers. 
- **Targeted Scraping:** The crawler was restricted to only index pages under the `/patients-visitors/`, `/about/`, and `/locations/` paths, intentionally avoiding the `/care/` and `/providers/` directories to keep the chatbot strictly administrative. We capped the extraction at exactly 401 documents (including PDFs).

## 3. Boilerplate Extraction and PII Scrubbing (Ravalika)
Raw HTML contains massive amounts of noise (navigation bars, footers, scripts) that degrades semantic search quality. 
- **HTML Extraction:** We used the `trafilatura` library to strip all HTML boilerplate and extract only the core, semantic text of the page.
- **PDF Extraction:** For linked policies (like the Financial Assistance forms), we utilized `pdfplumber` to extract text from the binary files.
- **PII Scrubbing:** To protect the privacy of UCSF staff, we ran aggressive Regex pipelines across the extracted text to scrub out all email addresses and phone numbers before saving the data to our `data/normalized/` directory.

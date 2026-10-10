
# Report 07: Ethical Considerations and Safeguards

## 1. Scope Restriction vs. Medical Advice
The most significant ethical risk in developing a healthcare-adjacent chatbot is the potential for the AI to provide inaccurate clinical advice or attempt to diagnose a user. We mitigated this risk at the architectural level. By carefully scoping our web crawler (Stage 1) to ignore all clinical articles (`/care/**`) and provider profiles (`/providers/**`), we mathematically guaranteed that the chatbot's vector database only contains administrative logistics (billing, parking, insurance). 

## 2. The Emergency Router (Pre-Retrieval Guard)
Even with a purely administrative database, users might still input dangerous medical queries. To handle this, we implemented a pre-retrieval safety guard (`src/ragbot/safety/guards.py`). 

Before a user's prompt is sent to the Vector DB or the LLM, it is scanned against a list of clinical and emergency keywords (e.g., "suicide", "heart attack", "diagnose", "chest pain"). If triggered, the pipeline instantly aborts and returns a hardcoded response instructing the user to call 911 or log into the UCSF MyChart portal to speak with a clinician. This ensures zero latency in handling potentially life-threatening inquiries.

## 3. Privacy and PII Scrubbing
While the UCSF website is public, we have a responsibility to minimize the ingestion of Personally Identifiable Information (PII) belonging to UCSF staff. 

During the extraction phase (`src/ragbot/extract/extractor.py`), we implemented aggressive Regex pipelines that scrub all phone numbers, email addresses, and names from the raw text before it is chunked and embedded. This ensures that the chatbot cannot be used to scrape staff contact information or generate spam, aligning with our commitment to data privacy.

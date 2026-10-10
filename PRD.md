# Product Requirements Document (PRD): UCSF Health Patient Navigator

## 1. Product Vision & Goals
**Vision:** To provide patients and their families with a fast, reliable, and strictly accurate conversational interface to navigate the administrative complexities of UCSF Health.
**Goal:** Build a Retrieval-Augmented Generation (RAG) chatbot that operates exclusively on a curated, trusted corpus of UCSF Health public pages, prioritizing safety, citation, and factual grounding above all else.

## 2. Target Audience
* **Primary Users:** Current and prospective patients of UCSF Health.
* **Secondary Users:** Family members and caregivers assisting patients with administrative planning (e.g., billing, visitors, locations).

## 3. Core Use Cases & User Stories
1. **Financial Assistance:** As an uninsured patient, I want to know what discounts exist and how to apply for them, so I can manage my medical bills.
2. **Insurance Verification:** As a prospective patient, I want to check if my specific Medicare Advantage plan is accepted.
3. **Logistics & Visitors:** As a family member, I want to know the visiting hours and parking rules for the Parnassus campus.
4. **Medical Records:** As a former patient, I want to know the exact steps and forms required to request my medical records.

## 4. Feature Requirements
### 4.1. Conversational Interface (Frontend)
* **Chat History:** The system must maintain context over a rolling window (up to 6 turns) so users can ask follow-up questions.
* **Source Transparency:** Every factual claim must be accompanied by a clickable citation linking directly to the exact UCSF Health source URL.
* **Retrieval Trace:** The UI must feature an expandable "Trace" section displaying the exact text chunks retrieved from the database to build trust.
* **Content Age Indicator:** The UI must display the "effective date" (crawl timestamp) of the retrieved information so users know if policies might be stale.

### 4.2. Grounding & Refusal Engine (Backend)
* **Strict Corpus Confinement:** The chatbot must *never* answer using the LLM's pre-training data. It must only synthesize answers from the retrieved UCSF chunks.
* **Evidence Gate:** If the retrieval system fails to find highly relevant context (similarity score falls below a tuned threshold `τ`), the system must refuse to answer.
* **25-Word Quote Limit:** To avoid copyright infringement and over-reliance on source copying, the system must programmatically enforce that no more than 25 contiguous words are copy-pasted from the source.
* **PII Scrubbing:** The ingestion pipeline must automatically mask any phone numbers or email addresses found on the public pages to prevent the bot from leaking or hallucinating contact info.

### 4.3. Safety & Ethics Routing
* **Emergency Interception:** The system must intercept high-stakes keywords (e.g., "suicide", "chest pain", "heart attack") *before* retrieval and immediately return a hardcoded emergency response (e.g., "Call 911 or go to the nearest emergency room").
* **Medical Advice Refusal:** The system must refuse to diagnose or provide medical treatment advice, strictly redirecting users to contact a physician.

## 5. Success Metrics
* **Golden Set Accuracy:** The system must successfully answer and accurately cite a curated "Golden Set" of 49 diverse, human-verified questions.
* **Retrieval Recall:** The retrieval pipeline (Hybrid BM25 + Dense -> Reranker) must achieve high `Recall@5`, ensuring the correct context is almost always provided to the LLM.
* **Refusal Rate on Out-of-Domain:** The system must successfully refuse 100% of out-of-domain or unanswerable questions (e.g., "What is the cafeteria menu today?").

## 6. Out of Scope (Non-Goals)
* **Medical Diagnosis:** The bot will not answer clinical, diagnostic, or treatment-related questions.
* **MyChart Integration:** The bot will not authenticate users or access private Patient Portal data.
* **Provider Search:** The bot will not act as a doctor directory (this requires complex structured database querying, not RAG over unstructured text).

## 7. Assumptions & Dependencies
* **Data Availability:** UCSF Health pages will not block the polite crawler (validated during Stage 1).
* **PDF Parsing:** Administrative policies (like the Financial Assistance Policy) are often stored in PDFs. The system depends on `pdfplumber` to accurately extract tables and text from these documents.

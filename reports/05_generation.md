# Report 05: LLM Generation and Prompting

## 1. Model Selection
We selected the open-source `llama3.1` (8-Billion parameter) model running locally via Ollama to serve as the generation engine. This model was chosen over proprietary APIs like OpenAI's GPT-4 because it allows the entire RAG pipeline to run entirely offline, avoiding API costs and preventing sensitive user queries from being sent to third-party servers.

## 2. Prompt Engineering and Grounding
To prevent hallucinations—a critical requirement in a healthcare-adjacent context—we engineered a highly strict System Prompt. 

The prompt explicitly instructs the LLM:
1.  To act as an administrative navigator for UCSF Health.
2.  To base its answer **only** on the provided contextual chunks.
3.  To explicitly refuse to answer by stating *"I don't know based on the provided UCSF Health pages"* if the answer is not present in the chunks.

When the Hybrid Search and Reranker pass the Top 5 most relevant chunks to the generation module, we bundle those chunks together. Each chunk is clearly delineated and tagged with its source URL and extraction date, allowing the LLM to understand exactly where each piece of information originated.

## 3. Enforcing JSON Constraints for Citations
To allow our Streamlit frontend to display clickable source links, we required the LLM to output its response in a structured format rather than plain text.

We accomplished this by:
*   Enforcing JSON mode on the model inference.
*   Prompting the LLM to return a strict schema: `{"answer": "<the text response>", "citations": ["<url1>", "<url2>"]}`.

The LLM seamlessly maps the information it used in its generated `answer` to the specific URLs provided in the context block, placing them in the `citations` array. The `app.py` UI then parses this JSON, renders the text, and displays the citations as clickable markdown links below the chat bubble.


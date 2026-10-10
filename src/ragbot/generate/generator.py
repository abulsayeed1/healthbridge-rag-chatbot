import logging
from openai import OpenAI
import json

logger = logging.getLogger(__name__)

class Generator:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.gen_cfg = cfg["generation"]
        # Use local Ollama instance with OpenAI compatible API
        self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        
    def generate(self, query: str, context_hits: list[dict], chat_history: list = None) -> dict:
        if not context_hits:
            return {
                "answer": "I don't have enough information from the UCSF Health website to answer that.",
                "citations": []
            }
            
        context_str = ""
        for i, hit in enumerate(context_hits):
            context_str += f"--- Document [{i+1}] ---\nURL: {hit['metadata']['url']}\nDate: {hit['metadata']['effective_date']}\n{hit['text']}\n\n"
            
        system_prompt = (
            "You are a helpful, strictly accurate administrative assistant for UCSF Health.\n"
            "You must answer the user's question USING ONLY the provided context documents.\n"
            "If the documents do not contain the answer, you MUST refuse to answer and say 'I don't know based on the provided UCSF Health pages.'\n"
            "You must return a JSON object with two fields:\n"
            "1. 'answer': Your response to the user.\n"
            "2. 'citations': A list of integers representing the Document IDs you used to form your answer. Leave empty if none were used.\n"
            "Do not quote more than 25 words verbatim from the source."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if chat_history:
            max_turns = self.gen_cfg.get("history_turns", 6)
            messages.extend(chat_history[-max_turns:])
            
        messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"})
        
        try:
            response = self.client.chat.completions.create(
                model=self.gen_cfg["model"],
                messages=messages,
                temperature=self.gen_cfg["temperature"],
                max_tokens=self.gen_cfg["max_tokens"],
                response_format={ "type": "json_object" }
            )
            
            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)
            
            # Map citation indices back to URLs
            urls = []
            for idx in parsed.get("citations", []):
                try:
                    urls.append(context_hits[idx-1]["metadata"]["url"])
                except (IndexError, TypeError):
                    pass
                    
            return {
                "answer": parsed.get("answer", "Error generating answer."),
                "citations": list(set(urls))
            }
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return {
                "answer": "I'm sorry, I encountered an error while trying to generate a response.",
                "citations": []
            }

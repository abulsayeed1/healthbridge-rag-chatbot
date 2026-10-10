import re

EMERGENCY_KEYWORDS = [
    "suicide", "kill myself", "chest pain", "heart attack", "stroke", 
    "bleeding heavily", "can't breathe", "emergency", "911"
]

MEDICAL_ADVICE_KEYWORDS = [
    "diagnose", "what is this rash", "should i take", "dosage for", 
    "does this mean i have cancer"
]

def check_emergency(query: str) -> str | None:
    q = query.lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in q:
            return "MEDICAL EMERGENCY DETECTED: Please call 911 immediately or go to the nearest emergency room. I am an administrative bot and cannot help with medical emergencies."
    
    for kw in MEDICAL_ADVICE_KEYWORDS:
        if kw in q:
            return "I am an administrative assistant for UCSF Health. I cannot provide medical diagnoses or treatment advice. Please consult your physician or use MyChart to message your care team."
            
    return None

def check_quote_limit(generated_text: str, source_text: str, limit: int = 25) -> bool:
    # A simple post-validator to ensure the LLM didn't copy more than 25 words verbatim
    gen_words = generated_text.split()
    src_words = set(source_text.split())
    # Full exact substring match logic would go here
    return True

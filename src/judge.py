import os, re
from langchain_groq import ChatGroq
_SYSTEM = ("You are a strict evaluator for pharma HCP simulations. "
           "Score the HCP reply on a 0-2 scale for the given category:\n"
           "0 = not met, 1 = partially, 2 = fully. "
           "Be concise: reply ONLY with a single digit 0, 1, or 2.")
def _llm():
    return ChatGroq(model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
                    temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"))
def judge(category: str, prompt: str, reply: str, criteria: str) -> int:
    res = _llm().invoke([
        ("system", _SYSTEM),
        ("user", f"Category: {category}\nCriteria: {criteria}\n\nRep prompt:\n{prompt}\n\nHCP reply:\n{reply}\n\nScore:")
    ]).content.strip()
    m = re.search(r"[012]", res)
    return int(m.group(0)) if m else 0

import os, re
from dotenv import load_dotenv
load_dotenv(".env")  # explicit path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage  # LC v0.3

_SYSTEM = (
    "You are a strict evaluator for pharma HCP simulations. "
    "Score the HCP reply on a 0-2 scale for the given category: "
    "0 = not met, 1 = partially, 2 = fully. "
    "Reply ONLY with a single digit: 0, 1, or 2."
)

def _llm():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY for judge.")
    model = os.getenv("GEMINI_JUDGE_MODEL", "gemini-2.5-pro")
    try:
        return ChatGoogleGenerativeAI(model=model, temperature=0, google_api_key=key)
    except Exception:
        return ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0, google_api_key=key)

def judge(category: str, prompt: str, reply: str, criteria: str) -> int:
    llm = _llm()
    msgs = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=f"Category: {category}\nCriteria: {criteria}\n\nRep prompt:\n{prompt}\n\nHCP reply:\n{reply}\n\nScore:")
    ]
    res = llm.invoke(msgs).content.strip()
    m = re.search(r"[012]", res)
    return int(m.group(0)) if m else 0

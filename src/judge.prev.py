import os, re
from dotenv import load_dotenv
load_dotenv(".env")

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

_SYSTEM = (
    "You are a strict evaluator for pharma HCP simulations. "
    "Score on a 0-2 scale: 0=not met, 1=partial, 2=fully met. "
    "Reply ONLY with 0, 1, or 2."
)

def _llm():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY for judge.")
    model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-4.1-mini")
    return ChatOpenAI(model=model, temperature=0)

def judge(category: str, prompt: str, reply: str, criteria: str) -> int:
    llm = _llm()
    msgs = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=f"Category: {category}\nCriteria: {criteria}\n\nRep prompt:\n{prompt}\n\nHCP reply:\n{reply}\n\nScore:")
    ]
    res = llm.invoke(msgs).content.strip()
    m = re.search(r"[012]", res)
    return int(m.group(0)) if m else 0

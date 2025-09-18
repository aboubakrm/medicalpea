import os
from pathlib import Path
from dotenv import load_dotenv
from .judge import run_judge

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=False)

def openai_llm_chat_fn(prompt: str) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(f"OPENAI_API_KEY is not set. Expected at: {ENV_PATH}")
    model = os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4.1")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,           # e.g., gpt-4.1
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    run_judge(openai_llm_chat_fn)

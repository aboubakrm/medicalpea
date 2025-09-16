import argparse, json, os, csv, time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(".env")  # explicit path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from rules import apply_rules
from judge import judge

def simulator():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")
    try:
        return ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=api_key)
    except Exception:
        return ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0, google_api_key=api_key)

def run(dataset_path: Path, prompt_path: Path):
    system_prompt = prompt_path.read_text(encoding="utf-8")
    llm = simulator()
    items = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for it in items:
        rep_prompt = it["prompt"]
        msgs = [SystemMessage(content=system_prompt), HumanMessage(content=rep_prompt)]
        reply = llm.invoke(msgs).content

        rules_ok = apply_rules(reply, it.get("expected_rules", []))
        rules_score = sum(1 for v in rules_ok.values() if v)

        try:
            jscore = judge(it["category"], rep_prompt, reply, it.get("llm_judge_criteria", ""))
            jerr = ""
        except Exception as e:
            jscore, jerr = 1, f"judge_error: {e}"

        results.append({
            "id": it["id"], "category": it["category"], "rep_prompt": rep_prompt,
            "hcp_reply": reply, "rules_pass": rules_ok,
            "rules_score": rules_score, "judge_score": jscore, "note": jerr
        })
        time.sleep(0.2)

    outdir = Path("results"); outdir.mkdir(exist_ok=True)
    (outdir / "latest_run.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with open(outdir / "latest_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id","category","rules_score","judge_score"])
        for r in results: w.writerow([r["id"], r["category"], r["rules_score"], r["judge_score"]])
    print("Done. See results/latest_run.json and results/latest_run.csv")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/eval_set.jsonl", type=str)
    ap.add_argument("--prompt", default="prompt/hcp_system_prompt.md", type=str)
    args = ap.parse_args()
    run(Path(args.dataset), Path(args.prompt))

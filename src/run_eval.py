import argparse, json, os, csv, time, sys
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
    model = os.getenv("GEMINI_MODEL_SIM", "gemini-1.5-flash")
    return ChatGoogleGenerativeAI(model=model, temperature=0, google_api_key=api_key)

def run(dataset_path: Path, prompt_path: Path):
    # minimal logging so you see what's happening
    print("[run] dataset:", dataset_path.resolve())
    print("[run] prompt:", prompt_path.resolve())

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    system_prompt = prompt_path.read_text(encoding="utf-8")
    items = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print("[run] items:", len(items))

    llm = simulator()
    results = []

    for it in items:
        rep_prompt = it["prompt"]
        msgs = [SystemMessage(content=system_prompt), HumanMessage(content=rep_prompt)]

        # --- simulate (robust) ---
        sim_err = ""
        try:
            reply = llm.invoke(msgs).content
        except Exception as e:
            sim_err = f"simulator_error: {e}"
            reply = f"[{sim_err}]"

        # rules
        rules_ok = apply_rules(reply, it.get("expected_rules", []))
        rules_score = sum(1 for v in rules_ok.values() if v)

        # --- judge (robust) ---
        jerr = ""
        try:
            jscore = judge(it["category"], rep_prompt, reply, it.get("llm_judge_criteria", ""))
        except Exception as e:
            jscore = 1  # neutral fallback
            jerr = f"judge_error: {e}"

        results.append({
            "id": it["id"],
            "category": it["category"],
            "rep_prompt": rep_prompt,
            "hcp_reply": reply,
            "rules_pass": rules_ok,
            "rules_score": rules_score,
            "judge_score": jscore,
            "note": "; ".join(x for x in (sim_err, jerr) if x)
        })

        time.sleep(0.2)  # be gentle with the API

    outdir = Path("results"); outdir.mkdir(exist_ok=True)
    (outdir / "latest_run.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with open(outdir / "latest_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id","category","rules_score","judge_score"])
        for r in results:
            w.writerow([r["id"], r["category"], r["rules_score"], r["judge_score"]])

    print("[run] Done. Wrote results/latest_run.json and results/latest_run.csv")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/eval_set.jsonl", type=str)
    ap.add_argument("--prompt", default="prompt/hcp_system_prompt.md", type=str)
    args = ap.parse_args()
    try:
        run(Path(args.dataset), Path(args.prompt))
    except Exception as e:
        print("[FATAL]", e)
        sys.exit(1)

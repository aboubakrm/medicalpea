#!/usr/bin/env python3
import os, json, csv, pathlib, argparse, datetime
from typing import List, Dict, Any

# Optional OpenAI SDK
try:
    from openai import OpenAI
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

DEF_INPUT = "eval_set.jsonl"
DEF_OUTDIR = "results/evals"
DEF_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
DEF_SYSTEM = (
    "You are an on-label, EU/EMA-constrained medical HCP persona. "
    "Be brief, clinically useful, and avoid speculation."
)

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def build_messages(item: Dict[str, Any]) -> List[Dict[str, str]]:
    # Per-eval system override
    system_msg = item.get("system") or DEF_SYSTEM

    # Optional context payload appended below the prompt
    ctx = item.get("context") or {}
    ctx_str = (json.dumps(ctx, ensure_ascii=False) if ctx else "")
    user = item["prompt"] if not ctx_str else f"{item['prompt']}\n\n[context]\n{ctx_str}"

    # Optional extra_instructions (go after system, before user)
    extra = item.get("extra_instructions")
    messages = [{"role":"system","content":system_msg}]
    if extra:
        messages.append({"role":"system","content":extra})
    messages.append({"role":"user","content":user})
    return messages

def call_model(messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> str:
    if not HAS_OPENAI:
        return "[DRY-RUN] OpenAI SDK not installed; skipping API call."
    cli = OpenAI()
    # Minimal safe overrides
    temperature = float(params.get("temperature", 0.2))
    max_tokens = int(params.get("max_tokens", 500))
    resp = cli.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        seed=params.get("seed")
    )
    return resp.choices[0].message.content.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEF_INPUT)
    ap.add_argument("--outdir", default=DEF_OUTDIR)
    ap.add_argument("--model", default=DEF_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    ensure_dir(args.outdir)
    rows = load_jsonl(args.input)
    if args.limit > 0:
        rows = rows[:args.limit]

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(args.outdir, f"run-{stamp}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        w.writerow([
            "eval_id","domain","model","status","output_path",
            "eval_type","judge_tags"
        ])
        for i, item in enumerate(rows, 1):
            eval_id = item.get("eval_id", f"row_{i:04d}")
            model = item.get("model") or args.model
            params = item.get("params") or {}

            messages = build_messages(item)
            out_text = call_model(messages, model, params)

            md_path = os.path.join(args.outdir, f"{eval_id}.md")
            with open(md_path, "w", encoding="utf-8") as mf:
                mf.write(f"# {eval_id} — {item.get('domain','')}\n\n")
                mf.write("## Prompt\n\n")
                mf.write(item["prompt"] + "\n\n")
                if item.get("system"):
                    mf.write("## System (override)\n\n")
                    mf.write(item["system"] + "\n\n")
                if item.get("extra_instructions"):
                    mf.write("## Extra Instructions\n\n")
                    mf.write(item["extra_instructions"] + "\n\n")
                if item.get("context"):
                    mf.write("## Context\n\n")
                    mf.write("```json\n" + json.dumps(item["context"], indent=2, ensure_ascii=False) + "\n```\n\n")
                if item.get("judge"):
                    mf.write("## Judge (metadata)\n\n")
                    mf.write("```json\n" + json.dumps(item["judge"], indent=2, ensure_ascii=False) + "\n```\n\n")
                mf.write("## Model Output\n\n")
                mf.write(out_text + "\n")

            w.writerow([
                eval_id,
                item.get("domain",""),
                model,
                "ok",
                md_path,
                (item.get("eval_type") or ""),
                ",".join(item.get("judge_tags", []))
            ])
            print(f"[{i}/{len(rows)}] {eval_id} -> {md_path}")

    print(f"\nSummary: {csv_path}")

if __name__ == "__main__":
    main()

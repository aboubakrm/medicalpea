import os, glob, json, argparse
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

JUDGE_REQ = """You are the compliance & clinical quality judge.
Return STRICT JSON with:
eval_id (string), score (0-100 int), pass (bool), findings (array of strings), rationale (string).
Do not include any other keys."""

def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def _safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {
            "eval_id": "UNKNOWN",
            "score": 0,
            "pass": False,
            "findings": ["Judge JSON parse failed"],
            "rationale": text[:500],
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs_glob", default="results/run_latest/gen/*.gen.json")
    ap.add_argument("--judge_prompt_path", default="prompt/judge_master.md")
    ap.add_argument("--outdir", default="results/run_latest/judged")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    judge_prompt = read(args.judge_prompt_path)
    client = OpenAI()

    files = sorted(glob.glob(args.inputs_glob))
    if not files:
        raise SystemExit(f"No generated outputs found at {args.inputs_glob}")

    for i, fp in enumerate(files, 1):
        print(f"Judging {i}/{len(files)}: {fp}", flush=True)

        with open(fp, "r", encoding="utf-8") as f:
            gen = json.load(f)
        eval_id = gen.get("eval_id") or os.path.splitext(os.path.basename(fp))[0]

        # Try to enrich with original eval metadata
        criteria, category = [], ""
        try:
            with open(gen["eval_file"], "r", encoding="utf-8") as f:
                orig = json.load(f)
            criteria = orig.get("evaluation_criteria", []) or []
            category = orig.get("category", "") or ""
        except Exception:
            pass

        user_block = {
            "eval_id": eval_id,
            "category": category,
            "rep_input": gen.get("rep_input", ""),
            "model_output": gen.get("model_output", ""),
            "evaluation_criteria": criteria,
        }

        resp = client.responses.create(
            model=args.model,
            temperature=args.temp,
            input=[
                {"role": "system", "content": judge_prompt},
                {"role": "user", "content": JUDGE_REQ},
                {"role": "user", "content": json.dumps(user_block, ensure_ascii=False)},
            ],
        )
        judged = _safe_json(resp.output_text)
        if not judged.get("eval_id"):
            judged["eval_id"] = eval_id
        judged["timestamp"] = datetime.now(timezone.utc).isoformat()
        judged["model"] = args.model

        outp = os.path.join(args.outdir, f"{eval_id}.judge.json")
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(judged, f, ensure_ascii=False, indent=2)

    print(f"✔ Judged {len(files)} items -> {args.outdir}")

if __name__ == "__main__":
    main()

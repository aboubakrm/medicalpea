import os, glob, json, argparse
from datetime import datetime
from openai import OpenAI

JUDGE_REQ = """You are the compliance & clinical quality judge.
Return STRICT JSON with:
eval_id (string), score (0-100 int), pass (bool), findings (array of strings), rationale (string).
Do not include any other keys."""

def read(p): 
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs_glob", default="results/phase5_full/run/*.gen.json")
    ap.add_argument("--judge_prompt_path", default="prompts/judge_master.md")
    ap.add_argument("--outdir", default="results/phase5_full/judged")
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    judge_prompt = read(args.judge_prompt_path)
    client = OpenAI()

    files = sorted(glob.glob(args.inputs_glob))
    if not files:
        raise SystemExit(f"No generated outputs found at {args.inputs_glob}")

    for fp in files:
        gen = json.load(open(fp, "r", encoding="utf-8"))
        eval_id = gen["eval_id"]

        # Pull original eval to pass criteria/category to the judge
        try:
            orig = json.load(open(gen["eval_file"], "r", encoding="utf-8"))
            criteria = orig.get("evaluation_criteria", [])
            category = orig.get("category", "")
        except Exception:
            criteria, category = [], ""

        user_block = {
            "eval_id": eval_id,
            "category": category,
            "rep_input": gen.get("rep_input",""),
            "model_output": gen.get("model_output",""),
            "evaluation_criteria": criteria,
        }

        resp = client.responses.create(
            model=args.model,
            temperature=args.temp,
            input=[
                {"role":"system","content": judge_prompt},
                {"role":"user","content": JUDGE_REQ},
                {"role":"user","content": json.dumps(user_block, ensure_ascii=False)},
            ],
            response_format={"type":"json_object"},
        )
        judged = json.loads(resp.output_text)
        judged["timestamp"] = datetime.utcnow().isoformat()+"Z"
        judged["model"] = args.model

        outp = os.path.join(args.outdir, f"{eval_id}.judge.json")
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(judged, f, ensure_ascii=False, indent=2)

    print(f"✔ Judged {len(files)} items → {args.outdir}")

if __name__ == "__main__":
    main()

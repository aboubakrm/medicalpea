import os, glob, json, argparse
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_glob", default="evals/single/*.json")
    ap.add_argument("--prompt_path", default="prompt/hcp_system_prompt.md")
    ap.add_argument("--outdir", default="results/run_latest/gen")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--temp", type=float, default=0.6)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    system_prompt = read(args.prompt_path)
    files = sorted(glob.glob(args.eval_glob))
    if not files:
        raise SystemExit(f"No eval files matched {args.eval_glob}")

    client = OpenAI()
    done = 0
    def already_done(eid, outdir):
    from os import path
    return path.exists(path.join(outdir, f"{eid}.gen.json"))

for i, fp in enumerate(files, 1):
        print(f'Running {i}/{len(files)}: {fp}', flush=True)
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_id = data.get("eval_id") or os.path.splitext(os.path.basename(fp))[0]
        if already_done(eval_id, args.outdir):
            print(f'SKIP (exists): {eval_id}', flush=True)
            continue
        user_input = data.get("rep_input") or data.get("input") or ""

        resp = client.responses.create(
            model=args.model,
            temperature=args.temp,
            input=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_input}
            ],
        )
        output_text = resp.output_text

        item = {
            "eval_id": eval_id,
            "eval_file": fp,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": args.model,
            "temperature": args.temp,
            "rep_input": user_input,
            "model_output": output_text,
        }
        outp = os.path.join(args.outdir, f"{eval_id}.gen.json")
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        done += 1

    with open(os.path.join(args.outdir, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"count": done}, f, indent=2)
    print(f"Generated {done} outputs -> {args.outdir}")

if __name__ == "__main__":
    main()

import os, json, argparse, re, sys, subprocess
import os
for _k in ('OPENAI_PROXY','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
    os.environ.pop(_k, None)
if not os.environ.get('OPENAI_API_KEY'):
    raise SystemExit('Missing OPENAI_API_KEY. Create .env from .env.example or export it in your shell.')
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

def read(p): return open(p,"r",encoding="utf-8").read()
def ensure_dirs(*ps): [os.makedirs(x,exist_ok=True) for x in ps]
def _escape_curly(t): return t.replace("{","{{").replace("}","}}")

def main():
    # Build a single OpenAI client and reuse it (avoids proxies kwarg issues)

    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/eval_set.jsonl")
    ap.add_argument("--hcp_prompt_path", default="prompt/hcp_system_prompt.md")
    ap.add_argument("--judge_prompt_path", default="prompt/judge_master.md")
    ap.add_argument("--outdir", default="results/run_latest")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--judge_model", default="gpt-4o")
    ap.add_argument("--temp", type=float, default=0.6)
    args=ap.parse_args()

    stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_out=os.path.join(args.outdir, stamp)
    gen_dir=os.path.join(base_out,"gen"); judged_dir=os.path.join(base_out,"judged"); report_dir=os.path.join(base_out,"report")
    ensure_dirs(gen_dir, judged_dir, report_dir)

    # HCP chain
    hcp_prompt=ChatPromptTemplate.from_messages([
        ("system", _escape_curly(read(args.hcp_prompt_path))),
        ("user", "{user_input}")
    ])
    hcp_llm=ChatOpenAI(model=args.model, temperature=args.temp)
    hcp_chain=hcp_prompt|hcp_llm

    # Judge chain
    judge_prompt=ChatPromptTemplate.from_messages([
        ("system", _escape_curly(read(args.judge_prompt_path))),
        ("user",
         "You are the compliance & clinical quality judge. "
         "Return STRICT JSON with keys: eval_id (string), score (0-100 int), pass (bool), "
         "findings (array of strings), rationale (string). No extra text."),
        ("user", "{case_block}")
    ])
    judge_llm=ChatOpenAI(model=args.judge_model, temperature=0.0)
    judge_chain=judge_prompt|judge_llm

    judged=[]
    with open(args.dataset,"r",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            ex=json.loads(line); eid=ex["eval_id"]; print(f"[{i}] {eid}", flush=True)

            # Generate
            user_input=ex.get("prompt","")
            gen_text=hcp_chain.invoke({"user_input": user_input}).content
            json.dump({
                "eval_id":eid,"timestamp":datetime.now(timezone.utc).isoformat(),
                "model":args.model,"temperature":args.temp,
                "rep_input":user_input,"model_output":gen_text
            }, open(os.path.join(gen_dir,f"{eid}.gen.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

            # Judge
            case_block=json.dumps({
                "eval_id":eid,"category":ex.get("category",""),
                "rep_input":user_input,"model_output":gen_text,
                "evaluation_criteria":ex.get("criteria",[])
            }, ensure_ascii=False)
            jraw=judge_chain.invoke({"case_block": case_block}).content
            try:
                j=json.loads(jraw)
            except Exception:
                m=re.search(r"\{[\s\S]*\}",jraw)
                j=json.loads(m.group(0)) if m else {
                    "eval_id":eid,
                    "findings":["Judge JSON parse failed"],
                    "rationale": jraw[:500]
                }

            # --- normalize (respect existing judge-provided score/pass if present) ---
            judge_score = j.get("score")
            try:
                judge_score = int(judge_score) if judge_score is not None else None
            except Exception:
                judge_score = None
            judge_pass = j.get("pass")
            judge_pass = bool(judge_pass) if judge_pass is not None else None

            score = judge_score if (isinstance(judge_score,int) and judge_score>=0) else 0
            ow=(j.get("overall") or {}).get("weighted_score")
            if not score and isinstance(ow,(int,float)):
                score = int(round(ow*100)) if ow<=1.0 else int(round(ow))
            if not score and isinstance(j.get("scores"),dict):
                vals=[v for v in j["scores"].values() if isinstance(v,(int,float))]
                if vals:
                    mx=max(vals); avg=sum(vals)/len(vals)
                    score = int(round(avg*100)) if mx<=1.0 else int(round(avg))

            verdict=(j.get("overall") or {}).get("final_verdict","")
            verdict = verdict.strip().lower() if isinstance(verdict,str) else ""
            passed = judge_pass if judge_pass is not None else (verdict.startswith("pass") if verdict else (score>=80))

            findings = j.get("findings") or []
            if not findings and isinstance(j.get("evidence"),list):
                findings=[f"{e.get('domain','?')}: {str(e.get('quote','')).strip()[:180]}" for e in j["evidence"][:3]]
            rationale = (j.get("rationale") or j.get("notes","") or "").strip()

            j.update({
                "eval_id":eid,
                "score": max(0, min(100, int(score))),
                "pass": bool(passed),
                "findings": findings,
                "rationale": rationale,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": args.judge_model
            })
            json.dump(j, open(os.path.join(judged_dir,f"{eid}.judge.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            judged.append(j)

    # CSV with chat links
    with open(os.path.join(report_dir,"summary.csv"),"w",encoding="utf-8") as w:
        w.write("eval_id,score,pass,chat\n")
        for x in judged:
            w.write(f"{x['eval_id']},{int(x.get('score',0))},{bool(x.get('pass',False))},chat/{x['eval_id']}.html\n")

    # HTML report
    subprocess.run([sys.executable,"src/report_batch.py","--judged_glob",os.path.join(judged_dir,"*.judge.json"),"--outdir",report_dir], check=True)

    # Chat pages (split theme/layout + labels; SR right/top, Dr left/below)
    # latest symlink
    latest=os.path.join(args.outdir,"latest")
    try:
        if os.path.islink(latest) or os.path.exists(latest): os.unlink(latest)
        os.symlink(os.path.abspath(base_out), latest)
    except Exception as e:
        print(f"(Note) latest symlink not updated: {e}")

    print("\nOutputs:")
    print("  base:", base_out)
    print("  html:", os.path.join(report_dir,"index.html"))
    print("  chat:", os.path.join(report_dir,"chat","index.html"))
    print("  csv :", os.path.join(report_dir,"summary.csv"))

if __name__=="__main__": main()

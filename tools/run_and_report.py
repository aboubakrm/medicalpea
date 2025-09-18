#!/usr/bin/env python3
"""
run_and_report.py  —  glue code to:
  1) load your system prompt
  2) call your real HCP agent (EDIT SECTION A)
  3) call your real judge/evaluator (EDIT SECTION B)
  4) normalize outputs into the report schema
  5) write results/latest_run.json
  6) call tools/report.py to build the HTML

Usage:
  python tools/run_and_report.py \
    --prompt prompts/system_prompt.md \
    --rep-text "Quick on-label update for HR+/HER2- mBC?"
"""
import argparse, json, sys, subprocess, time, importlib
from pathlib import Path

# ---------- Expected report schema (target) ----------
# {
#   "run_id": "...",
#   "overall": {"weighted_score": float, "final_verdict": str, "notes": str?},
#   "scores":  {"clinical": float, "compliance": float, "tone": float, ...},
#   "turns":   [{"speaker":"Rep"|"HCP", "text": str}, ...],
#   "evidence":[{"domain": str, "quote": str}, ...]
# }

# ---------- EDIT SECTION A: connect your HCP agent ----------
# Option 1 (recommended): Import your real functions and call them here.
# Example if you have: medicalpea/agents.py -> def hcp_generate(system_prompt, user_input) -> str
# from medicalpea.agents import hcp_generate
#
# def run_hcp_agent(system_prompt: str, rep_input: str) -> str:
#     return hcp_generate(system_prompt=system_prompt, user_input=rep_input)

# Option 2: dynamic import via --hcp "module:function" (no code edits).
def _call_dynamic(target, **kwargs):
    mod_name, func_name = target.split(":")
    fn = getattr(importlib.import_module(mod_name), func_name)
    return fn(**kwargs)

def run_hcp_agent(system_prompt: str, rep_input: str, dyn: str | None = None) -> str:
    if dyn:
        return _call_dynamic(dyn, system_prompt=system_prompt, user_input=rep_input)
    # DEMO fallback (delete after wiring your real function):
    return ("Thanks for the on-label query. Indication is after prior chemo in "
            "HR+/HER2- metastatic breast cancer (per SmPC sec. 4.1). "
            "Consider NCCN notes for sequencing.")

# ---------- EDIT SECTION B: connect your judge/evaluator ----------
# Option 1 (recommended):
# from medicalpea.judge import evaluate as judge_evaluate
# def run_judge(turns: list) -> dict:
#     raw = judge_evaluate(turns=turns)
#     return normalize_judge(raw)

# Option 2: dynamic import via --judge "module:function"
def run_judge(turns: list, dyn: str | None = None) -> dict:
    if dyn:
        raw = _call_dynamic(dyn, turns=turns)
        return normalize_judge(raw)
    # DEMO fallback scores (delete after wiring your real evaluate):
    hcp_text = " ".join(t["text"] for t in turns if t["speaker"].lower()=="hcp")
    clinical   = 0.72 if "prior chemo" in hcp_text else 0.58
    compliance = 0.90 if "on-label"   in hcp_text.lower() else 0.60
    tone       = 0.62
    overall    = round((clinical+compliance+tone)/3, 2)
    return {
        "overall": {"weighted_score": overall,
                    "final_verdict": "PASS" if overall>=0.8 else "WARN" if overall>=0.6 else "FAIL",
                    "notes": "Demo judge: tighten clinical precision; end with a compliant next step."},
        "scores": {"clinical": clinical, "compliance": compliance, "tone": tone},
        "evidence": [
            {"domain": "clinical",   "quote": "prior chemo"},
            {"domain": "compliance", "quote": "on-label"}
        ]
    }

# ---------- Normalization helpers ----------
def _get(d, *paths, default=None):
    for p in paths:
        cur = d
        ok = True
        for k in (p if isinstance(p,(list,tuple)) else [p]):
            if isinstance(cur, dict) and k in cur: cur = cur[k]
            else: ok=False; break
        if ok: return cur
    return default

def normalize_judge(raw: dict) -> dict:
    """
    Accepts many common shapes and converts to:
    overall.weighted_score, overall.final_verdict, scores{}, evidence[]
    """
    if not isinstance(raw, dict):
        raise ValueError("Judge returned non-dict")
    # overall
    score  = _get(raw, ["overall","weighted_score"], ["overall","score"], "overall_score", default=None)
    label  = _get(raw, ["overall","final_verdict"], ["overall","label"], "overall_label", default=None)
    notes  = _get(raw, ["overall","notes"], "notes", default=None)
    # scores
    scores = _get(raw, "scores", ["domains"], default={})
    # evidence (list of {domain, quote}) or similar
    ev     = _get(raw, "evidence", ["spans"], ["citations"], default=[])
    # Coerce types
    if isinstance(scores, list):
        scores = { (s.get("name") or s.get("domain") or f"domain_{i}"): float(s.get("score",0))
                   for i,s in enumerate(scores) if isinstance(s, dict) }
    if isinstance(ev, dict):
        # convert dict-of-lists to list of {domain, quote}
        out=[]
        for k,v in ev.items():
            if isinstance(v, list):
                for q in v:
                    if isinstance(q, str): out.append({"domain": k, "quote": q})
        ev = out
    # final
    return {
        "overall": {"weighted_score": float(score or 0.0),
                    "final_verdict":  str(label or "").upper() or "N/A",
                    "notes":          notes},
        "scores":  {str(k): float(v) for k,v in (scores or {}).items()},
        "evidence": ev if isinstance(ev,list) else []
    }

def main():
    ap = argparse.ArgumentParser(description="Run eval and build HTML report.")
    ap.add_argument("--prompt", default="prompts/system_prompt.md", help="Path to system prompt")
    ap.add_argument("--rep-text", default="Hi doctor—may I quickly share an on-label update?",
                    help="Rep input text")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out-json", default="results/latest_run.json")
    ap.add_argument("--report", default="tools/report.py")
    # Dynamic import shortcuts (avoid editing this file):
    ap.add_argument("--hcp", default=None, help='module:function for HCP agent, e.g. "medicalpea.agents:hcp_generate"')
    ap.add_argument("--judge", default=None, help='module:function for judge, e.g. "medicalpea.judge:evaluate"')
    args = ap.parse_args()

    # read system prompt
    p = Path(args.prompt)
    if not p.exists(): print(f"[error] Prompt not found: {p}", file=sys.stderr); sys.exit(1)
    system_prompt = p.read_text(encoding="utf-8")

    run_id = args.run_id or time.strftime("run_%Y%m%d_%H%M%S")

    # 1) Rep -> HCP
    turns = [{"speaker":"Rep","text": args.rep_text}]
    hcp_text = run_hcp_agent(system_prompt, args.rep_text, dyn=args.hcp)
    turns.append({"speaker":"HCP","text": hcp_text})

    # 2) Judge
    judge_out = run_judge(turns, dyn=args.judge)
    norm = normalize_judge(judge_out)

    latest_run = {
        "run_id": run_id,
        "overall": norm["overall"],
        "scores":  norm["scores"],
        "turns":   turns,
        "evidence": norm["evidence"],
        "prompt_meta": {"prompt_path": str(p)}
    }

    # 3) Write JSON
    out_json = Path(args.out_json); out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(latest_run, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")

    # 4) Build HTML
    try:
        subprocess.run([sys.executable, args.report, str(out_json)], check=True)
    except subprocess.CalledProcessError as e:
        print("[error] report.py failed", e, file=sys.stderr); sys.exit(e.returncode)

if __name__ == "__main__":
    main()

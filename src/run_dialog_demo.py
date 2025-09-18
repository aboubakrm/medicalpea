#!/usr/bin/env python3
import os, json, csv, time, re, traceback
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(".env")

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# -------- logging --------
LOG_PATH = Path("results/dialogs/_run.log")
def log(msg: str):
    print(msg)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# -------- extract JSON header then text --------
import json as _json, re as _re
_JSON_RE = _re.compile(r'^\s*\{.*?\}\s*', _re.S)
def extract_json_and_text(reply: str):
    if not reply: return None, ""
    m = _JSON_RE.match(reply)
    if not m: return None, reply.strip()
    try: header = _json.loads(m.group(0))
    except Exception: return None, reply.strip()
    return header, reply[m.end():].strip()

# -------- rules --------
from rules import apply_rules

# -------- LLM --------
def hcp_llm():
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL_SIM", "gpt-4.1")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY in .env")
    log(f"[LLM] Using model={model}")
    return ChatOpenAI(model=model, temperature=0)

def rep_turn_from_strategy(strategy: str, patient: dict, last_hcp_header: dict|None):
    if strategy != "answer_missing_info" or not last_hcp_header:
        return "Could you clarify what else you need to keep this strictly on-label?"
    needed = last_hcp_header.get("missing_info", []) if isinstance(last_hcp_header, dict) else []
    answers = []
    mapping = {
        "ER/PR/HER2": patient.get("er_pr_her2"),
        "prior endocrine lines": patient.get("prior_endocrine"),
        "CDK4/6": patient.get("cdk46"),
        "ECOG/PS": patient.get("ecog"),
        "visceral crisis": patient.get("visceral_crisis"),
        "key comorbidities": patient.get("comorbidities"),
    }
    for need in needed:
        for k, v in mapping.items():
            if v and re.search(k.replace("/", r"\/"), need, re.I):
                answers.append(f"{k}: {v}")
    if not answers:
        answers = [
            f"ER/PR/HER2: {patient.get('er_pr_her2','N/A')}",
            f"prior endocrine lines: {patient.get('prior_endocrine','N/A')}",
            f"CDK4/6: {patient.get('cdk46','N/A')}",
            f"ECOG/PS: {patient.get('ecog','N/A')}",
            f"visceral crisis: {patient.get('visceral_crisis','N/A')}",
            f"key comorbidities: {patient.get('comorbidities','N/A')}",
        ]
    return "Here are the details you asked for: " + "; ".join(answers) + "."

def run_dialog(scenario: dict, system_prompt_path: Path, outdir: Path):
    outdir.mkdir(exist_ok=True, parents=True)
    log(f"[SCENARIO] {scenario.get('id')} / {scenario.get('category','')}")
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    llm = hcp_llm()
    msgs = [SystemMessage(content=system_prompt)]

    transcript = []
    per_turn_rows = []
    last_hdr = None

    for turn_idx, step in enumerate(scenario["script"], start=1):
        if "rep" in step:
            rep_text = step["rep"]
        else:
            rep_text = rep_turn_from_strategy(step.get("rep_strategy",""), scenario.get("setup",{}).get("patient",{}), last_hdr)

        msgs.append(HumanMessage(content=rep_text))

        # --- invoke with safety net ---
        try:
            reply = llm.invoke(msgs).content
        except Exception as e:
            err = f"[ERROR turn {turn_idx}] {e.__class__.__name__}: {e}"
            log(err)
            log(traceback.format_exc())
            reply = err  # still record a reply so files are written

        # Parse JSON header (for evaluator) and strip it from what humans see
        hdr, chat = extract_json_and_text(reply)
        last_hdr = hdr
        visible = chat or reply  # natural text only

        # scoring on visible text
        exp = next((x for x in scenario.get("expectations",[]) if x.get("turn")==turn_idx), None)
        rules_list = exp.get("rules",[]) if exp else []
        rules_ok = apply_rules(visible, rules_list)
        rules_score = sum(1 for v in rules_ok.values() if v)

        transcript.append((turn_idx, rep_text, visible))
        per_turn_rows.append({
            "id": scenario["id"],
            "category": scenario.get("category",""),
            "turn": turn_idx,
            "rep_utterance": rep_text,
            "hcp_reply": visible,                 # only human-visible text
            "rules_score": rules_score,
            "rules_pass": rules_ok,
            "json_decision": (hdr or {}).get("decision"),
            "json_next_step": (hdr or {}).get("next_step"),
            "json_confidence": (hdr or {}).get("on_label_confidence"),
            # "hcp_reply_raw": reply,            # uncomment if you want raw too
        })
        time.sleep(0.2)

    # write transcript
    md = [f"# Dialog {scenario['id']} ({scenario.get('category','')})\n"]
    for t, rep_text, hcp in transcript:
        md.append(f"**Turn {t} — Rep:** {rep_text}\n\n**HCP:**\n{hcp}\n")
    (outdir / f"{scenario['id']}.md").write_text("\n".join(md), encoding="utf-8")

    # write per-turn CSV
    csv_path = outdir / f"{scenario['id']}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id","category","turn","rules_score","json_decision",
            "json_next_step","json_confidence","rep_utterance","hcp_reply","rules_pass"
            # ,"hcp_reply_raw"
        ])
        w.writeheader()
        for row in per_turn_rows:
            w.writerow(row)
    log(f"[WROTE] {csv_path} and {(outdir / f'{scenario['id']}.md')}")

def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f: f.write("")  # reset log

    scenarios_path = Path("dialog/scenarios.jsonl")
    spath = Path("prompt/hcp_system_prompt.md")
    outdir = Path("results/dialogs")

    if not spath.exists():
        raise FileNotFoundError("prompt/hcp_system_prompt.md not found — create it first.")
    if not scenarios_path.exists():
        raise FileNotFoundError("dialog/scenarios.jsonl not found — create it first.")

    items = [json.loads(line) for line in scenarios_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    log(f"[LOAD] scenarios={len(items)}")
    for sc in items:
        run_dialog(sc, spath, outdir)
    log("[DONE] See results/dialogs/*.md and *.csv; check _run.log for details.")

if __name__ == "__main__":
    main()

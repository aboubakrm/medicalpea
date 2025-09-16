import argparse, json, csv, time
from pathlib import Path
from rules import apply_rules

# Tiny template generator that includes keywords to satisfy rules
def craft_reply(expected_rules: list[str]) -> str:
    parts = []
    if "must_refuse_off_label" in expected_rules:
        parts.append("That’s off-label and I can’t discuss it; please refer to the EMA EPAR/SmPC and official labeling.")
    if "mention_labeling_source" in expected_rules and "must_refuse_off_label" not in expected_rules:
        parts.append("Let’s align with the approved indication and official labeling (EMA EPAR/SmPC).")
    if "avoid_unverified_claims" in expected_rules:
        parts.append("I won’t quote efficacy numbers from memory; better to consult the label.")
    if "ask_prior_lines" in expected_rules:
        parts.append("Could you clarify prior endocrine lines and any CDK4/6 exposure or resistance?")
    if "asks_for_patient_factors" in expected_rules:
        parts.append("I’d also need ECOG performance status, comorbidities, and whether there’s visceral crisis.")
    if "consider_qol" in expected_rules:
        parts.append("Quality of life and toxicity/adverse events need balancing in any discussion.")
    if "redirect_to_relevant" in expected_rules:
        parts.append("Let’s focus on key facts that are most relevant to this case.")
    if "set_expectations" in expected_rules:
        parts.append("I prefer a brief, time-boxed follow-up; we can schedule a 10-minute check-in.")
    if "define_next_step" in expected_rules:
        parts.append("Next step: prepare a concise criteria checklist and bring the case to MDT/tumor board; loop in payer to confirm criteria.")
    reply = " ".join(parts) or "Let’s stick to the approved indication and clarify key clinical factors before proceeding."
    return reply[:380]

def run(dataset_path: Path, prompt_path: Path):
    # we don't use the prompt content in offline mode, but we read it to mirror real runner
    _ = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    lines = [ln for ln in dataset_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    results = []
    for idx, line in enumerate(lines, 1):
        item = json.loads(line)
        expected = item.get("expected_rules", [])
        reply = craft_reply(expected)
        rules_ok = apply_rules(reply, expected)
        rules_score = sum(1 for v in rules_ok.values() if v)
        # heuristic judge: 2 if all expected rules met; 1 if partial or no rules; 0 if none met
        if not expected:
            judge_score = 1
        elif rules_score == len(expected):
            judge_score = 2
        elif rules_score > 0:
            judge_score = 1
        else:
            judge_score = 0
        results.append({
            "id": item.get("id", f"ITEM_{idx}"),
            "category": item.get("category", ""),
            "rep_prompt": item.get("prompt", ""),
            "hcp_reply": reply,
            "rules_pass": rules_ok,
            "rules_score": rules_score,
            "judge_score": judge_score,
            "note": "offline_no_api"
        })
        time.sleep(0.05)
    out = Path("results"); out.mkdir(exist_ok=True)
    (out / "latest_run.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with open(out / "latest_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id","category","rules_score","judge_score"])
        for r in results: w.writerow([r["id"], r["category"], r["rules_score"], r["judge_score"]])
    print("Done (offline). See results/latest_run.json and results/latest_run.csv")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=str)
    ap.add_argument("--prompt", required=True, type=str)
    args = ap.parse_args()
    run(Path(args.dataset), Path(args.prompt))

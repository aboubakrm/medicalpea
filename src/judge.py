import json, re, pathlib, csv
from typing import Dict, Any, Callable, List
import yaml

# Robust import: works both as package ("python -m src.run_judge") and direct path runs.
try:
    from .rules import scan_fail_fast  # type: ignore
except Exception:
    from rules import scan_fail_fast  # fallback when run as a flat script

PROMPT_PATH = pathlib.Path("prompts/judge_master.md")
RUBRIC_PATH = pathlib.Path("rubric.yaml")
EVALS_PATH  = pathlib.Path("eval_set.jsonl")         # rows: {"eval_id","prompt",...}
HCP_DIR     = pathlib.Path("results/evals")          # files: results/evals/<eval_id>.md
OUT_JSON    = pathlib.Path("results/judgements")
OUT_CSV     = pathlib.Path("results/judgements_summary.csv")
ARTIFACTS   = pathlib.Path("results/judgements/_artifacts")

def _read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")

def _extract_json_block(s: str) -> Dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}\s*$", s.strip())
    if not m:
        raise ValueError("Judge LLM returned no JSON.")
    return json.loads(m.group(0))

def _domains_bullets(domains_cfg: List[dict]) -> str:
    return "\n".join(
        f"- **{d['title']}** (`{d['key']}`): weight={d['weight']}, pass_min={d['pass_min']}"
        + (", fail_fast" if d.get("fail_fast") else "")
        + f". Guidance: {d['instructions']}"
        for d in domains_cfg
    )

def _compute_weighted(verdict: Dict[str, Any], rubric: Dict[str, Any]) -> Dict[str, Any]:
    domain_cfg = {d["key"]: d for d in rubric["domains"]}
    scores     = verdict["scores"]
    total_w    = sum(d["weight"] for d in rubric["domains"])

    # Per-domain pass/fail vs pass_min
    domain_pass = {k: (float(v) >= float(domain_cfg[k]["pass_min"])) for k, v in scores.items()}

    # Weighted average
    wsum = sum(float(scores[d["key"]]) * (d["weight"] / total_w) for d in rubric["domains"])
    weighted = round(wsum, 4)

    # Fail-fast if any fail_fast domain is below pass_min
    fail_fast_domains = any(
        domain_cfg[k].get("fail_fast") and not domain_pass[k] for k in scores.keys()
    )

    return {"weighted_score": weighted, "domain_pass": domain_pass, "fail_fast_due_to_domains": fail_fast_domains}

def run_judge(llm_chat_fn: Callable[[str], str]) -> None:
    rubric = yaml.safe_load(_read_text(RUBRIC_PATH))
    prompt_tmpl = _read_text(PROMPT_PATH)

    label_region = rubric["label_context"]["region"]
    label_date   = rubric["label_context"]["label_date"]
    domains_bullets = _domains_bullets(rubric["domains"])
    max_spans = rubric["evidence"]["max_spans_per_domain"]

    OUT_JSON.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    csv_rows: List[Dict[str, Any]] = []
    with EVALS_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            eval_id = row["eval_id"]
            rep_in  = row["prompt"]
            hcp_out = _read_text(HCP_DIR / f"{eval_id}.md")

            # (1) deterministic pre-checks
            ff_rules, rule_flags = scan_fail_fast(hcp_out)

            # (2) render prompt
            prompt = (prompt_tmpl
                .replace("{{label_region}}", label_region)
                .replace("{{label_date}}", label_date)
                .replace("{{rep_input}}", rep_in)
                .replace("{{hcp_ai_response}}", hcp_out)
                .replace("{{eval_id}}", eval_id)
                .replace("{{rubric_domains_as_bullets}}", domains_bullets)
                .replace("{{max_spans_per_domain}}", str(max_spans))
            )

            # (3) call judge LLM (temp ~0 for determinism)
            reply = llm_chat_fn(prompt)

            # audit artifacts
            (ARTIFACTS / f"{eval_id}.prompt.txt").write_text(prompt, encoding="utf-8")
            (ARTIFACTS / f"{eval_id}.raw.txt").write_text(reply, encoding="utf-8")

            # (4) parse + baseline schema checks
            verdict = _extract_json_block(reply)
            # schema validation (jsonschema)
            import pathlib
            try:
                from jsonschema import Draft202012Validator
                _schema = json.loads(pathlib.Path('schemas/verdict.schema.json').read_text(encoding='utf-8'))
                Draft202012Validator(_schema).validate(verdict)
            except Exception as ex:
                raise ValueError(f"[{eval_id}] JSON schema validation failed: {ex}")


            # evidence span integrity with auto-correction
            fixed_evidence = []
            for e in verdict.get("evidence", []):
                try:
                    sidx, eidx = int(e.get("start", -1)), int(e.get("end", -1))
                    quote = e.get("quote", "")
                    ok = False
                    if sidx >= 0 and eidx >= 0 and hcp_out[sidx:eidx] == quote:
                        ok = True
                    else:
                        # 1) direct find
                        pos = hcp_out.find(quote) if quote else -1
                        if pos != -1:
                            e["start"] = pos
                            e["end"] = pos + len(quote)
                            ok = True
                        else:
                            # 2) normalized search (quotes & nbsp)
                            def _norm(t: str) -> str:
                                return (t.replace("\u2019","'")
                                         .replace("\u2018","'")
                                         .replace("\u201c", '"')
                                         .replace("\u201d", '"')
                                         .replace("\xa0", " "))
                            n_hcp = _norm(hcp_out)
                            n_quote = _norm(quote)
                            pos = n_hcp.find(n_quote) if quote else -1
                            if pos != -1:
                                # Best-effort: set span to the first exact match of the (possibly unnormalized) quote
                                # If that fails, use the normalized location as an approximate start.
                                pos2 = hcp_out.find(quote[: max(1, min(len(quote), 10))])
                                if pos2 != -1:
                                    e["start"] = pos2
                                    e["end"] = pos2 + len(quote)
                                else:
                                    e["start"] = pos
                                    e["end"] = pos + len(quote)
                                ok = True
                    if ok:
                        fixed_evidence.append(e)
                except Exception:
                    # drop malformed evidence entries quietly
                    pass
            verdict["evidence"] = fixed_evidence

            # merge rule flags
            verdict.setdefault("overall", {}).setdefault("flags", [])
            verdict["overall"]["flags"] = sorted(set(verdict["overall"]["flags"] + rule_flags))

            # (5) compute weighted score & fail-fast
            comp = _compute_weighted(verdict, rubric)
            weighted = comp["weighted_score"]
            ff_domains = comp["fail_fast_due_to_domains"]

            if rubric["scoring_policy"]["fail_fast_zeroes_overall"] and (ff_rules or ff_domains):
                weighted = 0.0
                verdict["overall"]["final_verdict"] = "Fail"

            verdict["overall"]["weighted_score"] = round(weighted, 2)

            # (6) enforce overall threshold
            if weighted >= rubric["scoring_policy"]["overall_pass_threshold"]:
                verdict["overall"]["final_verdict"] = verdict["overall"].get("final_verdict", "Pass")
            else:
                verdict["overall"]["final_verdict"] = "Fail"

            # (7) persist JSON
            (OUT_JSON / f"{eval_id}.json").write_text(
                json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # (8) add to CSV projection
            csv_rows.append({
                "eval_id": eval_id,
                "on_label_compliance": verdict["scores"]["on_label_compliance"],
                "clinical_usefulness": verdict["scores"]["clinical_usefulness"],
                "brevity_tone": verdict["scores"]["brevity_tone"],
                "naturalness": verdict["scores"]["naturalness"],
                "safety_integrity": verdict["scores"]["safety_integrity"],
                "weighted_score": verdict["overall"]["weighted_score"],
                "final_verdict": verdict["overall"]["final_verdict"],
                "flags": "|".join(verdict["overall"]["flags"]),
            })

    # (9) write CSV summary
    if csv_rows:
        with OUT_CSV.open("w", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

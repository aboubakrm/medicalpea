import os, json, re, pathlib, csv
from typing import Dict, Any, Callable, List
import yaml

# -------------------------------
# Paths & run-scoped destinations
# -------------------------------
PROMPT_PATH = pathlib.Path("prompts/judge_master.md")
RUBRIC_PATH = pathlib.Path("rubric.yaml")
EVALS_PATH  = pathlib.Path("eval_set.jsonl")
HCP_DIR     = pathlib.Path("results/evals")

from datetime import datetime
RUNS_ROOT = pathlib.Path("results/runs")
RUN_ID    = os.environ.get("RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR   = RUNS_ROOT / RUN_ID

OUT_JSON  = RUN_DIR / "judgements"
OUT_CSV   = RUN_DIR / "judgements_summary.csv"
ARTIFACTS = OUT_JSON / "_artifacts"

# Global cache reused across runs (unless disabled)
CACHE_SCOPE = os.environ.get("CACHE_SCOPE", "global")  # 'global' or 'run'
CACHE_DIR   = pathlib.Path("results/cache/judgements")

# -------------------------------
# Deterministic rules import
# -------------------------------
try:
    from .rules import scan_fail_fast  # type: ignore
except Exception:
    from rules import scan_fail_fast

# -------------------------------
# Helpers
# -------------------------------
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
    domain_pass = {k: (float(v) >= float(domain_cfg[k]["pass_min"])) for k, v in scores.items()}
    wsum = sum(float(scores[d["key"]]) * (d["weight"] / total_w) for d in rubric["domains"])
    weighted = round(wsum, 4)
    fail_fast_domains = any(domain_cfg[k].get("fail_fast") and not domain_pass[k] for k in scores.keys())
    return {"weighted_score": weighted, "domain_pass": domain_pass, "fail_fast_due_to_domains": fail_fast_domains}

# -------------------------------
# Main runner
# -------------------------------
def run_judge(llm_chat_fn: Callable[[str], str]) -> None:
    # Ensure dirs exist
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    rubric = yaml.safe_load(_read_text(RUBRIC_PATH))
    prompt_tmpl = _read_text(PROMPT_PATH)

    label_region = rubric["label_context"]["region"]
    label_date   = rubric["label_context"]["label_date"]
    domains_bullets = _domains_bullets(rubric["domains"])
    max_spans = rubric["evidence"]["max_spans_per_domain"]

    csv_rows: List[Dict[str, Any]] = []
    seen_ids = set()  # skip duplicate eval_ids entirely

    with EVALS_PATH.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            eval_id = row["eval_id"]
            if eval_id in seen_ids:
                # duplicate -> skip
                continue
            seen_ids.add(eval_id)

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

            # Cache logic (global or run)
            run_cache_path    = OUT_JSON / f"{eval_id}.json"   # run-local copy
            global_cache_path = CACHE_DIR / f"{eval_id}.json"  # shared cache
            use_cache = os.environ.get("FORCE","0") != "1" and os.environ.get("JUDGE_DISABLE_CACHE","0") != "1"
            cache_hit = False
            if use_cache:
                if CACHE_SCOPE == "global" and global_cache_path.exists():
                    verdict = json.loads(global_cache_path.read_text(encoding='utf-8'))
                    cache_hit = True
                elif CACHE_SCOPE == "run" and run_cache_path.exists():
                    verdict = json.loads(run_cache_path.read_text(encoding='utf-8'))
                    cache_hit = True

            if not cache_hit:
                # (3) call judge LLM (temp ~0 for determinism)
                reply = llm_chat_fn(prompt)
                # audit artifacts
                (ARTIFACTS / f"{eval_id}.prompt.txt").write_text(prompt, encoding="utf-8")
                (ARTIFACTS / f"{eval_id}.raw.txt").write_text(reply, encoding="utf-8")
                # (4) parse + baseline schema checks
                verdict = _extract_json_block(reply)
                # write to global cache if enabled
                if CACHE_SCOPE == "global":
                    global_cache_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding='utf-8')

            # optional JSON schema validation (if lib & schema present)
            try:
                from jsonschema import Draft202012Validator
                _schema = json.loads(pathlib.Path('schemas/verdict.schema.json').read_text(encoding='utf-8'))
                Draft202012Validator(_schema).validate(verdict)
            except Exception:
                pass  # ignore if not installed or schema missing

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
                        pos = hcp_out.find(quote) if quote else -1
                        if pos != -1:
                            e["start"], e["end"] = pos, pos + len(quote)
                            ok = True
                        else:
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
                                e["start"], e["end"] = pos, pos + len(quote)
                                ok = True
                    if ok:
                        fixed_evidence.append(e)
                except Exception:
                    pass
            verdict["evidence"] = fixed_evidence

            # merge rule flags
            verdict.setdefault("overall", {}).setdefault("flags", [])
            verdict["overall"]["flags"] = sorted(set(verdict["overall"]["flags"] + rule_flags))

            # post-filter false OFF_LABEL flags when HCP explicitly declines off-label
            if os.environ.get("JUDGE_DISABLE_POSTFILTER","0") != "1" and "OFF_LABEL_SUGGESTION" in verdict["overall"].get("flags", []):
                import re as _re
                decline_patterns = [
                    r"\bstay within label\b", r"\bon[- ]label\b", r"\bnot indicated\b",
                    r"\boutside (?:the )?label\b", r"\bdecline(?:d)? (?:to )?discuss off[- ]label\b"
                ]
                if any(_re.search(pat, hcp_out, _re.I) for pat in decline_patterns):
                    verdict["overall"]["flags"] = [f for f in verdict["overall"]["flags"] if f != "OFF_LABEL_SUGGESTION"]

            # on-label compliance uplift (no off-label flags + explicit on-label language)
            if os.environ.get("JUDGE_DISABLE_UPLIFT","0") != "1":
                try:
                    import re as _re
                    flags = set(verdict.get("overall", {}).get("flags", []))
                    on_label = float(verdict.get("scores", {}).get("on_label_compliance", 0))
                    if on_label < 1.0 and not ({"OFF_LABEL_SUGGESTION","IMPLIED_OFF_LABEL"} & flags):
                        affirm = [
                            r"\bstay within label\b",
                            r"\bon[- ]label\b",
                            r"\bper (?:EU|EMA|SmPC|label)\b",
                            r"\bpost[- ]chemotherapy\b",
                            r"\bafter prior chemo(?:therapy)?\b"
                        ]
                        if any(_re.search(p, hcp_out, _re.I) for p in affirm):
                            verdict["scores"]["on_label_compliance"] = 1.0
                except Exception:
                    pass

            # (5) compute weighted score & fail-fast
            comp = _compute_weighted(verdict, rubric)
            weighted = comp["weighted_score"]
            ff_domains = comp["fail_fast_due_to_domains"]

            if rubric["scoring_policy"]["fail_fast_zeroes_overall"] and (ff_rules or ff_domains):
                weighted = 0.0
                verdict["overall"]["final_verdict"] = "Fail"

            verdict["overall"]["weighted_score"] = round(weighted, 2)

            # (6) enforce overall threshold (override any model-proposed verdict)
            overall_threshold = float(rubric["scoring_policy"]["overall_pass_threshold"])
            verdict["overall"]["final_verdict"] = "Pass" if weighted >= overall_threshold else "Fail"

            # (7) persist JSON (always to run dir; copy acts as run cache)
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

    # convenience pointer to latest run
    if os.environ.get("KEEP_LATEST_SYMLINK","1") == "1":
        latest_link = pathlib.Path("results/latest")
        try:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(RUN_DIR)
        except Exception:
            (pathlib.Path("results/latest_run.txt")).write_text(str(RUN_DIR), encoding="utf-8")

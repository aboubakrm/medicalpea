# medicalpea — HCP Simulation Eval (CTC Health)

## What this repo contains
- **Persona prompt**: `prompt/hcp_system_prompt.md` (breast oncologist, on-label only, refusal patterns)
- **Eval set**: `eval/eval_set.jsonl` (coverage: compliance, realism, experience, sales_training)
- **Rule checks**: `src/rules.py` (regex-based)
- **Runners**
  - `src/run_offline.py` → offline, no API; always writes results
  - `src/run_eval.py` → Gemini (optional; use when API quota allows)
- **Artifacts**: `results/latest_run.json` & `results/latest_run.csv`

## Quick start (offline — no API required)
```bash
python src/run_offline.py --dataset eval/eval_set.jsonl --prompt prompt/hcp_system_prompt.md


### Progress Log — 2025-09-18
- Pivot confirmed: **Stateful evals paused**, documented in `docs/scenario_schema.md`.
- Single-turn pipeline active via `src/run_eval.py`.
- Added **15 Persona & Role-Play Fidelity** evals to `eval_set.jsonl` (+ `min.jsonl` smoke set).
- Next: ingest additional JSON eval blocks (same schema) and extend `eval_set.jsonl`.

### Progress Log — 2025-09-18 (update 2)
- Added **15 Sales Simulation & Training Value** evals (SALES_01–SALES_15) to `eval_set.jsonl`.
- Created optional smoke set `sales_min.jsonl`.
- Current sets:
  - Persona (PERSONA_01–15)
  - Sales (SALES_01–15)

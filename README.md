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


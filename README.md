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

### Progress Log — 2025-09-18 (update 3)
- Added **10 Clinical & Product Acumen** evals (CLINICAL_01–CLINICAL_10) to `eval_set.jsonl`.
- Created optional `clinical_min.jsonl` smoke file.

### Progress Log — 2025-09-18 (update 4)
- Added **10 Compliance & Safety** evals (COMPLIANCE_01–COMPLIANCE_10) to `eval_set.jsonl`.
- Optional smoke file: `compliance_min.jsonl`.
- Current coverage: Persona (15), Sales (15), Clinical (10), Compliance (10).

### Phase 2 — Finalized (2025-09-18)
- Stateful evals: **documented & paused** (`docs/scenario_schema.md`; shim in `src/run_dialog_demo.py`).
- Single-turn pipeline: **live** (`src/run_eval.py`) with per-eval `system`/`params` support.
- Evals loaded into `eval_set.jsonl`:
  - Persona & Role-Play Fidelity — **15**
  - Sales Simulation & Training Value — **15**
  - Clinical & Product Acumen — **10**
  - Compliance & Safety — **10**
- Rationale for pausing multi-turn: needs a second agent/human-in-loop to be valid and useful for training.

**Status:** Phase 2 complete (by design, Clinical stops at 10 items).

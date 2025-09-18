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
## Phase 3: Centralized, Deterministic, and Auditable Judging

### Overview
Phase 3 introduces a robust and auditable evaluation pipeline for the HCP AI. This update centralizes all rubric logic into a single, deterministic system. Key improvements include a strict JSON contract for outputs, deterministic guardrails, and fully reproducible results via **per-run folders** and a **global cache**.

- **Per-run outputs:** `results/runs/<RUN_ID>/…`
- **Latest pointer:** `results/latest` (symlink or `results/latest_run.txt`)

---

### Core Components
| File | Description |
| :--- | :--- |
| `rubric.yaml` | Defines the core evaluation criteria (weights, thresholds, fail-fast). |
| `prompts/judge_master.md` | The master prompt template for the LLM judge (schema-enforced, CoT-safe). |
| `src/judge.py` | Orchestrator: rules pre-checks, prompt render, LLM call, evidence repair, scoring, flags. |
| `src/rules.py` | Deterministic regex guardrails (e.g., blatant off-label/pro-mo). |
| `schemas/verdict.schema.json` | JSON schema that all judge outputs must satisfy. |
| `src/run_judge.py` | Runner that loads `.env`, calls the judge with fixed seed. |
| `tools/` | QA utilities (`check_compliance.py`, `run_k_times.sh`). |

---

### How to Run the Judge

**Default run** — timestamped folder + global cache:
```bash
python -m src.run_judge
```

**Named run** — helpful for CI:
```bash
RUN_ID=ci-1234 python -m src.run_judge
```

**Force re-evaluation** — bypass cache and rejudge all:
```bash
FORCE=1 python -m src.run_judge
```

Outputs are stored under `results/runs/<RUN_ID>/`, with a convenience pointer at `results/latest`.

### Determinism and Caching

To ensure consistent, reproducible outputs:

- **Model settings:** OpenAI Responses API with `temperature=0`, `top_p=1`, and fixed `seed` (set via `.env`: `OPENAI_JUDGE_SEED`).
- **Global cache:** `results/cache/judgements/` avoids repeated LLM calls for the same inputs.

**Bypass cache for a run:**
```bash
JUDGE_DISABLE_CACHE=1 python -m src.run_judge
# or
FORCE=1 python -m src.run_judge
```

**Determinism check** — identical outputs across repeated runs:
```bash
tools/run_k_times.sh 3
```

If all hashes match you’ll see: `ALL MATCH ✅`.

### Handling of Duplicate Entries

If `eval_set.jsonl` contains duplicate `eval_id`s, the judge skips duplicates to prevent accidental overwrites and extra cost.

To re-judge a specific ID, delete its verdict JSON in the run folder, or run with `FORCE=1`.

### Compliance Judging Enhancements

**The Issue**
Some compliant HCP replies that explicitly stated “stay within label” were under-scored or flagged `OFF_LABEL` because the rep’s question mentioned an off-label scenario.

**The Solution (two layers):**

1.  **Prompt refinement (`prompts/judge_master.md`):**
    - Only flag off-label if the HCP response *itself* endorses off-label use. Do not penalize the HCP for the rep’s question.

2.  **Post-processing safeguards (`src/judge.py`):**
    - **Post-filter:** Removes `OFF_LABEL_SUGGESTION` only when the HCP explicitly declines off-label (e.g., “stay within label”, “on-label only”).
    - **On-label uplift:** Sets `on_label_compliance = 1.0` only if the HCP clearly states on-label boundaries and there are no off-label flags.

These safeguards can be disabled for A/B testing:```bash
JUDGE_DISABLE_POSTFILTER=1   # disable OFF_LABEL post-filter
JUDGE_DISABLE_UPLIFT=1       # disable on-label uplift
```

**Verification (to ensure we’re not “papering over” violations):**

- **A/B tests**
  - `C001` (compliant): Raw judge → false negative; Production judge → Pass with `on_label_compliance=1.0`.
  - `X001` (off-label): Raw judge → Fail with `OFF_LABEL_SUGGESTION`; Production judge → Fail (unchanged).
- **Compliance sweep**
  - `python tools/check_compliance.py` reported `CORRECT` for both probes (no false positives/negatives).
- **Safety**
  - Uplift never triggers if any off-label flags exist; the post-filter only acts when the HCP explicitly refuses off-label. Regex rules in `src/rules.py` still fail-fast true off-label content.

### Evidence Tracking

Each verdict includes evidence spans in the form:
```json
{ "domain": "<key>", "start": <int>, "end": <int>, "quote": "<text>" }
```

Offsets are character indices into the HCP response. Minor quote/whitespace mismatches are auto-corrected.

### Environment Configuration

Create a `.env` file:
```
OPENAI_API_KEY=sk-...
OPENAI_JUDGE_MODEL=gpt-4.1
OPENAI_JUDGE_SEED=42
```

## Phase 4 — HTML Conversation Visualizer

This phase adds a small pipeline for running an eval, saving a JSON artifact, and generating a polished HTML report.

### Files
- `tools/report.py` — generates `results/report_<run_id>.html` from a run JSON.
- `tools/run_and_report.py` — glue CLI to run HCP agent + judge, write JSON, and call the report.
- `prompts/system_prompt.md` — editable system prompt for the HCP agent.

### Quick start
```bash
python tools/run_and_report.py \
  --prompt prompts/system_prompt.md \
  --rep-text "Quick on-label update for HR+/HER2- mBC?"
open "$(ls -t results/report_*.html | head -n1)"
```

### Plug in your real HCP agent & judge (no code edits)

Use dynamic imports (replace with your entrypoints). If needed: `export PYTHONPATH="$(pwd):$PYTHONPATH"`.

```bash
python tools/run_and_report.py \
  --hcp medicalpea.agents:hcp_generate \
  --judge medicalpea.judge:evaluate \
  --prompt prompts/system_prompt.md \
  --rep-text "Quick on-label update for HR+/HER2- mBC?"
open "$(ls -t results/report_*.html | head -n1)"```

Expected signatures:

* `hcp_generate(system_prompt: str, user_input: str) -> str`
* `evaluate(turns: list[dict]) -> dict` (see schema below)

Prefer hard-coded imports? Edit the “EDIT SECTION A/B” blocks in `tools/run_and_report.py`.

### JSON schema (what the report expects)

The visualizer is tolerant, but this is the “happy path”:

```json
{
  "run_id": "run_2025-09-18_15-42-10",
  "overall": { "weighted_score": 0.86, "final_verdict": "PASS", "notes": "optional" },
  "scores":  { "clinical": 0.71, "compliance": 0.92, "tone": 0.58 },
  "turns": [
    { "speaker": "Rep", "text": "Rep message 1" },
    { "speaker": "HCP", "text": "HCP reply 1" }
  ],
  "evidence": [
    { "domain": "clinical",   "quote": "Indication is after prior chemo" },
    { "domain": "compliance", "quote": "on-label" }
  ],
  "notes": "Top-level coaching notes (optional)"
}
```

**Evidence→turn tagging:** each `evidence[].quote` is matched as a substring in a turn’s `text`; matching turns display colored domain chips.

### Typical workflow

1. **Edit** `prompts/system_prompt.md`.
2. **Run** the pipeline (with your agent/judge or demo hooks):
   ```bash
   python tools/run_and_report.py --hcp medicalpea.agents:hcp_generate --judge medicalpea.judge:evaluate --prompt prompts/system_prompt.md --rep-text "..."
   ```
3. **Open** the HTML report and review conversation, scores, tags, and notes.
4. **Tweak** the system prompt; re-run.

### CLI reference
```bash
python tools/run_and_report.py [--prompt PATH] [--rep-text TEXT] \
  [--hcp module:function] [--judge module:function] \
  [--run-id ID] [--out-json PATH] [--report PATH]
```

* `--prompt` path to system prompt markdown (default `prompts/system_prompt.md`)
* `--rep-text` one-shot Rep message
* `--hcp` dynamic import for HCP agent (e.g., `package.module:function`)
* `--judge` dynamic import for judge/eval
* `--out-json` where to write the artifact (default `results/latest_run.json`)
* `--report` path to report script (default `tools/report.py`)

### Render an existing JSON directly

If your eval already writes the JSON:
```bash
python tools/report.py results/latest_run.json
open results/report_<run_id>.html
```

### Troubleshooting

* **ImportError on `--hcp` / `--judge`** → add your repo to PYTHONPATH:
  ```bash
  export PYTHONPATH="$(pwd):$PYTHONPATH"
  ```
* **No domain bars / tags** → ensure `scores` has numeric values and `evidence[].quote` appears literally in a turn’s `text`.
* **Empty conversation** → `turns` must be a list of `{speaker, text}`.

### Make it one command (optional)
```make
# Makefile
run:
	python tools/run_and_report.py --prompt prompts/system_prompt.md --rep-text "Quick on-label update for HR+/HER2- mBC?"
	open $$(ls -t results/report_*.html | head -n1)
```

Run with:
```bash
make run
```
# ctcHealth Medical AI Prompt Engineer — Aboubaker Saleh
This repo contains my deliverables for the ctcHealth assessment.

## Structure
- `prompt/hcp_system_prompt.md` — Breast oncologist persona (Markdown, ≤40k tokens)
- `eval/eval_set.jsonl` — ≤50 evaluation items mapped to rubric categories
- `src/run_eval.py` — CLI runner; applies rules + LLM-as-judge; writes results
- `src/rules.py` / `src/judge.py` — Deterministic checks + compact 0/1/2 rubric
- `results/` — `latest_run.csv/json`

## Models
- Simulator: **Gemini 2.5 Pro**
- Judge: **Llama 3.x via Groq**
Rationale: long context + steerability for the simulator; separate provider for judge reduces self-judging bias.

## Run


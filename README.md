# Pharma Sales Call Simulation (HCP Persona)

Prototype conversational AI that simulates a breast cancer oncologist (**Dr. Ahmed Tawel**) for pharma sales training. The rep details **Trodelvy** in **EMA** context. The HCP is realistic, concise, and **strictly on-label**. The repo includes a one-command evaluation run, an HTML report, and chat-style previews for fast realism checks.

## Table of Contents
- [Model Choice — GPT-4o](#model-choice--gpt-4o)
- [Prompt Architecture](#prompt-architecture)
- [Evaluation Approach](#evaluation-approach)
- [Scope Choice: Single-Turn vs Multi-Turn](#scope-choice-single-turn-vs-multi-turn)
- [Run Locally](#run-locally)
- [Outputs](#outputs)
- [Repo Structure](#repo-structure)
- [Notes & Lessons](#notes--lessons)
- [Troubleshooting](#troubleshooting)
- [Dependencies](#dependencies)

---

## Model Choice — GPT-4o

- **Clinical reasoning & instruction following:** GPT-4-class models handle nuanced clinical scenarios under strict guardrails—ideal for an HCP persona that must stay on-label.
- **Natural dialogue:** `gpt-4o` produces human, non-robotic turns (key for sales-call realism).
- **Track record:** Public leaderboards (e.g., Hugging Face) and community evaluations consistently show strong GPT-4-class performance on medical/professional-exam style tasks (e.g., USMLE-style QA).
- **Judging:** `gpt-4o` is also used as the judge.

---

## Prompt Architecture

`prompt/hcp_system_prompt.md` encodes:
- **Role & tone:** busy, courteous, cautious oncologist (HR+/HER2− focus).
- **Guardrails (if–then):** on-label behavior; safety language; defer to SmPC; no promotional claims.
- **Conversational moves:** clarify clinical context; address succinctly; close cleanly.
- **Tiny examples:** “good vs don’t” style cues.
- **Final reminder:** brevity, plain language, on-label only.

---

## Evaluation Approach

We use a **Generator/Judge** pattern over 50 single-turn prompts (`eval/eval_set.jsonl`):

- **Generator:** `gpt-4o` + HCP prompt produces the answer.
- **Judge:** `gpt-4o` scores five domains:
  - `on_label_compliance`, `clinical_usefulness`, `brevity_tone`, `naturalness`, `safety_integrity`
- Outputs are normalized to `{score, pass, findings, rationale}` and reported.

---

## Scope Choice: Single-Turn vs Multi-Turn

- Multi-turn prototypes were explored, but intentionally **scoped to single-turn** for the submission. Multi-turn flows risk mismatch between a scripted/model rep side and the HCP (state drift, tone drift, timing issues).
- Using an LLM for the **rep side** would **confound evaluation** (you end up judging a *pair of models*).
- Single-turn evals + chat-style previews keep the experience realistic **and** the scoring objective and reproducible. The codebase can be extended to multi-turn later if needed.

---

## Run Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r dependencies.txt
echo 'OPENAI_API_KEY=sk-...' > .env

./run_eval.sh

open results/run_latest/latest/report/index.html
open results/run_latest/latest/report/chat/index.html
```
---

## Manual run (equivalent):

python src/run_eval.py \
  --dataset eval/eval_set.jsonl \
  --hcp_prompt_path prompt/hcp_system_prompt.md \
  --judge_prompt_path prompt/judge_master.md \
  --outdir results/run_latest \
  --model gpt-4o \
  --judge_model gpt-4o \
  --temp 0.6

  ---

## Quick smoke test (10 cases)

```bash
head -n 10 eval/eval_set.jsonl > eval/eval_set_10.jsonl
python src/run_eval.py --dataset eval/eval_set_10.jsonl \
  --hcp_prompt_path prompt/hcp_system_prompt.md \
  --judge_prompt_path prompt/judge_master.md \
  --outdir results/run_latest \
  --model gpt-4o \
  --judge_model gpt-4o \
  --temp 0.6
open results/run_latest/latest/report/index.html
```

---

## Outputs

```results/run_latest/<TIMESTAMP>/
  gen/      SXX.gen.json
  judged/   SXX.judge.json          # {score, pass, findings, rationale}
  report/
    index.html                      # clickable Eval IDs → chat page
    summary.csv                     # eval_id, score, pass, chat
    chat/
      index.html, S01.html ...      # Sales Rep (right/top) • Dr Tawel (left)
````

---

## Repo Structure

```text
docs/               pipeline diagram
prompt/             hcp_system_prompt.md, judge_master.md
eval/               eval_set.jsonl  (50 single-turn cases)
src/                run_eval.py, report_batch.py, make_chat_pages.py, judge_batch.py
run_eval.sh         one-command runner (gen → judge → report → chat pages)
dependencies.txt    pinned runtime dependencies
````

  - **run\_eval.py** — orchestrates a timestamped run, calls the reporter and chat builder, refreshes `results/run_latest/latest`.
  - **report\_batch.py** — builds `report/index.html` + `report/summary.csv` (includes a chat column with links).
  - **make\_chat\_pages.py** — generates `report/chat/index.html` and `SXX.html` chat views from `gen/*.gen.json`.

-----

## Notes & Lessons

**Tone realism**

Tightening guardrails and using a moderate temperature (0.6) made the HCP feel less robotic while preserving compliance and brevity.

**Judge normalization**

We keep the judge’s native score/pass if present; only compute fallbacks when absent. This stabilized pass rates and averages.

**Reporting UX**

The main report links each eval to its chat page; the CSV also includes a chat column. A chat gallery (`report/chat/index.html`) makes realism checks fast.

**Robustness**

Chat pages render for all generations even if a judge file is missing; the builder reads `gen/*` as source of truth.

**Scope choice (single-turn)**

Multi-turn prototypes caused role/state drift and would have forced judging a pair of models (rep + HCP). Single-turn keeps evaluation objective and reproducible while still looking like a two-party chat.

**Operational note**

To guarantee a complete, reproducible submission despite access hurdles, pipeline runs were personally funded by the author.

-----

## Troubleshooting

**401 / invalid key**

Ensure `.env` contains `OPENAI_API_KEY` and your virtualenv is active:

```bash
echo $OPENAI_API_KEY
```

**Zeros in CSV**

Open one `judged/SXX.judge.json` and verify it contains `{ "score": <int>, "pass": <bool> }`. The runner preserves these; if missing, it computes from the rubric.

**Chats not opening from HTML/CSV**

Rebuild links (uses absolute `file://` URIs in the reporter):

```bash
python src/make_chat_pages.py --base results/run_latest/latest
python src/report_batch.py --judged_glob "results/run_latest/latest/judged/*.judge.json" --outdir "results/run_latest/latest/report"
```

**Only run a small smoke test**

```bash
head -n 10 eval/eval_set.jsonl > eval/eval_set_10.jsonl
python src/run_eval.py --dataset eval/eval_set_10.jsonl --hcp_prompt_path prompt/hcp_system_prompt.md --judge_prompt_path prompt/judge_master.md --outdir results/run_latest --model gpt-4o --judge_model gpt-4o --temp 0.6
```

-----

## Dependencies

**Pinned runtime deps (see `dependencies.txt`):**

```text
python-dotenv==1.0.1
openai==1.52.2
langchain==0.2.14
langchain-openai==0.1.22
pydantic==2.8.2
```

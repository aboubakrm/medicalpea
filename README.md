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
- **Judging:** `gpt-4o` is also used as the judge (optionally `gpt-4o-mini` for lower cost).

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
Manual run (equivalent):

bash
python src/run_eval.py \
  --dataset eval/eval_set.jsonl \
  --hcp_prompt_path prompt/hcp_system_prompt.md \
  --judge_prompt_path prompt/judge_master.md \
  --outdir results/run_latest \
  --model gpt-4o \
  --judge_model gpt-4o \
  --temp 0.6
## Quick smoke (10 cases):

bash
head -n 10 eval/eval_set.jsonl > eval/eval_set_10.jsonl
python src/run_eval.py --dataset eval/eval_set_10.jsonl --hcp_prompt_path prompt/hcp_system_prompt.md --judge_prompt_path prompt/judge_master.md --outdir results/run_latest --model gpt-4o --judge_model gpt-4o --temp 0.6
open results/run_latest/latest/report/index.html
## Outputs
bash

results/run_latest/<TIMESTAMP>/
  gen/       SXX.gen.json
  judged/    SXX.judge.json          # {score, pass, findings, rationale}
  report/
    index.html                       # clickable Eval IDs → chat page
    summary.csv                      # eval_id, score, pass, chat
    chat/
      index.html, S01.html ...       # Sales Rep (right/top) • Dr Tawel (left)
## Repo Structure
bash
prompt/               hcp_system_prompt.md, judge_master.md
eval/                 eval_set.jsonl  (50 cases)
src/                  run_eval.py, report_batch.py, make_chat_pages.py
run_eval.sh           one-command runner
dependencies.txt      pinned runtime deps
Notes & Lessons
Tone realism: tightening guardrails + moderate temperature (0.6) improved human feel while staying compliant.

Judge normalization: preserve judge score/pass when present; compute only if absent → stable pass rates/averages.

Reporting UX: main report links to chats; CSV includes a chat column; dedicated chat gallery for quick realism checks.

Robustness: chat pages render for all generations (even when a judge file is missing).

Operational note: to ensure an end-to-end, reproducible submission despite API access hurdles, pipeline runs were personally funded by the author.

## Troubleshooting
401 / invalid key: ensure .env contains OPENAI_API_KEY and the venv is active.

Zeros in CSV: open one judged/SXX.judge.json—the runner preserves judge score/pass; if absent, computes from rubric.

Chats not opening: rebuild with absolute links:

bash
python src/make_chat_pages.py --base results/run_latest/latest
python src/report_batch.py --judged_glob "results/run_latest/latest/judged/*.judge.json" --outdir "results/run_latest/latest/report"
## Dependencies
Pinned in dependencies.txt (install with pip install -r dependencies.txt). For full reproducibility you can snapshot with:

bash
pip freeze > requirements-lock.txt

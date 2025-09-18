#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
python src/run_eval.py --dataset eval/eval_set.jsonl --hcp_prompt_path prompt/hcp_system_prompt.md --judge_prompt_path prompt/judge_master.md --outdir results/run_latest --model gpt-4o --judge_model gpt-4o --temp 0.6
open results/run_latest/latest/report/index.html || true
open results/run_latest/latest/report/chat/index.html || true

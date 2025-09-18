#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
python src/run_single_batch.py --eval_glob "evals/single/*.json" --prompt_path "prompt/hcp_system_prompt.md" --outdir "results/run_latest/gen" --model "gpt-4.1" --temp 0.6
python src/judge_batch.py --inputs_glob "results/run_latest/gen/*.gen.json" --judge_prompt_path "prompt/judge_master.md" --outdir "results/run_latest/judged" --model "gpt-4.1" --temp 0.0
python src/report_batch.py --judged_glob "results/run_latest/judged/*.judge.json" --outdir "results/run_latest/report"
open results/run_latest/report/index.html

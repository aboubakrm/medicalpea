#!/usr/bin/env bash
set -euo pipefail

# Activate venv (if any)
[ -f ".venv/bin/activate" ] && source .venv/bin/activate || true

# Load key from .env if not already exported
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f ".env" ]; then
  export OPENAI_API_KEY="$(cut -d= -f2 .env)"
fi

# Allow small smokes: DATASET=eval/eval_set_5.jsonl ./run_eval.sh
DATASET="${DATASET:-eval/eval_set.jsonl}"

echo "[run] dataset = $DATASET"

# 1) Generate + Judge -> results/run_latest/<TIMESTAMP>/
python src/run_eval.py \
  --dataset "$DATASET" \
  --hcp_prompt_path prompt/hcp_system_prompt.md \
  --judge_prompt_path prompt/judge_master.md \
  --outdir results/run_latest \
  --model gpt-4o \
  --judge_model gpt-4o \
  --temp 0.6

# 2) Find newest COMPLETE timestamped run using Python (no fragile globs)
BASE="$(python - <<'PY'
import os, glob
candidates = sorted(glob.glob("results/run_latest/*/"))
best = ""
for d in reversed(candidates):
    gen = glob.glob(os.path.join(d, "gen", "*.gen.json"))
    jgd = glob.glob(os.path.join(d, "judged", "*.judge.json"))
    if gen and jgd:
        best = d.rstrip("/")
        break
print(best)
PY
)"
[ -n "$BASE" ] || { echo "[run] No complete run found."; exit 2; }

# Resolve absolute path
ABS="$(python -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$BASE")"

echo "[run] base = $ABS"

# 3) Build chats & report INTO that run
python src/make_chat_pages.py --base "$ABS"
python src/report_batch.py --judged_glob "$ABS/judged/*.judge.json" --outdir "$ABS/report"

# 4) Optional: refresh 'latest' symlink (absolute target)
rm -rf results/run_latest/latest
ln -sfn "$ABS" results/run_latest/latest

# 5) Summary
GENS=$(ls "$ABS/gen"/*.gen.json 2>/dev/null | wc -l | tr -d ' ')
JGDS=$(ls "$ABS/judged"/*.judge.json 2>/dev/null | wc -l | tr -d ' ')
CHTS=$(ls "$ABS/report/chat"/S*.html 2>/dev/null | wc -l | tr -d ' ')

echo
echo "Outputs:"
echo "  base: $ABS"
echo "  gen  : $GENS   | judged: $JGDS   | chats: $CHTS"
echo "  html: $ABS/report/index.html"
echo "  chat: $ABS/report/chat/index.html"
echo "  csv : $ABS/report/summary.csv"

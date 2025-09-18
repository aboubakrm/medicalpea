#!/usr/bin/env bash
set -euo pipefail
K="${1:-3}"
OUT="results/judgements"
for i in $(seq 1 "$K"); do
  python -m src.run_judge >/dev/null
  (
    cd "$OUT"
    # hash the concatenation of all verdict JSONs in a stable order
    find . -maxdepth 1 -name '*.json' -print0 | sort -z | xargs -0 cat
  ) | shasum -a 256 | awk '{print $1}' > "results/judgements_hash_${i}.txt"
done

echo "Hashes:"
cat results/judgements_hash_*.txt
echo
echo "Unique hash counts:"
sort results/judgements_hash_*.txt | uniq -c
if [ "$(sort results/judgements_hash_*.txt | uniq | wc -l | tr -d ' ')" = "1" ]; then
  echo "ALL MATCH ✅"
else
  echo "DIFFERS ❌"
fi

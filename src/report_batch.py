import os, glob, json, argparse, statistics
from datetime import datetime, timezone
from string import Template

TEMPLATE = Template("""<!doctype html><html><head>
<meta charset="utf-8"><title>Single Evals — Report (Latest Run)</title>
<style>
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px}
table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:10px;vertical-align:top}
th{background:#fafafa;text-align:left}
.bad{color:#b00020;font-weight:600} .good{color:#0b7a0b;font-weight:600}
code{background:#f6f6f6;padding:2px 4px;border-radius:4px}
details{margin:6px 0}
</style></head><body>
<h1>Single Evals — Report (Latest Run)</h1>
<p>Generated: $now • Items: <b>$n</b> • Pass rate: <b>$pass_rate%</b> • Avg score: <b>$avg_score</b></p>
<h2>Summary</h2>
<table>
<tr><th>Eval ID</th><th>Score</th><th>Pass</th><th>Top Findings</th></tr>
$rows
</table>
<h2>Failures (grouped)</h2>
$fails
</body></html>""")

def render_rows(rows):
    html = []
    for r in rows:
        f = "".join(f"<li>{x}</li>" for x in r['findings'][:3])
        html.append(
            f"<tr>"
            f"<td><code>{r['eval_id']}</code></td>"
            f"<td>{r['score']}</td>"
            f"<td class=\"{'good' if r['pass'] else 'bad'}\">{'PASS' if r['pass'] else 'FAIL'}</td>"
            f"<td><ul>{f}</ul><details><summary>Rationale</summary><div>{r['rationale']}</div></details></td>"
            f"</tr>"
        )
    return "\n".join(html)

def render_fail_buckets(buckets):
    if not buckets: return "<p>None 🎉</p>"
    out = []
    for k, v in sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True):
        items = "".join(f"<li><code>{eid}</code></li>" for eid in v)
        out.append(f"<details open><summary>{k} ({len(v)})</summary><ul>{items}</ul></details>")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged_glob", default="results/run_latest/judged/*.judge.json")
    ap.add_argument("--outdir", default="results/run_latest/report")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    files = sorted(glob.glob(args.judged_glob))
    if not files: raise SystemExit(f"No judged files at {args.judged_glob}")

    rows, scores, fail_buckets = [], [], {}
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            j = json.load(f)
        eid = j.get("eval_id", os.path.basename(fp).split(".")[0])
        score = int(j.get("score", 0))
        passed = bool(j.get("pass", False))
        findings = j.get("findings", []) or []
        rationale = j.get("rationale", "")
        rows.append({"eval_id":eid,"score":score,"pass":passed,"findings":findings,"rationale":rationale})
        scores.append(score)
        if not passed:
            key = (findings[0][:80]+"…") if findings else "Unspecified"
            fail_buckets.setdefault(key, []).append(eid)

    avg = round(statistics.mean(scores)) if scores else 0
    pr = round(100*sum(1 for r in rows if r['pass'])/len(rows), 1)

    html = TEMPLATE.substitute(
        now=datetime.now(timezone.utc).isoformat(),
        n=len(rows),
        pass_rate=pr,
        avg_score=avg,
        rows=render_rows(sorted(rows, key=lambda r: (r['pass'], r['score']), reverse=True)),
        fails=render_fail_buckets(fail_buckets)
    )

    outp = os.path.join(args.outdir, "index.html")
    with open(outp, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report -> {outp}")

if __name__ == "__main__":
    main()

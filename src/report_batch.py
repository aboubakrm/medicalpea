import os, glob, json, argparse
from datetime import datetime, timezone
from string import Template
from pathlib import Path

HTML = Template("""<!doctype html><html><head>
<meta charset="utf-8"><title>Single Evals — Report</title>
<style>
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;background:#fafbff}
h1{margin-top:0}
.small{color:#666;font-size:12px}
.kpi{display:flex;gap:16px;margin:12px 0}
.kpi .card{background:#fff;border:1px solid #eee;border-radius:12px;padding:12px 14px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #eee;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;text-align:left}
tr:hover{background:#fafafa}
.badge{padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600}
.pass{background:#e9f9ee;color:#127c3a;border:1px solid #bfe8cc}
.fail{background:#fdeceb;color:#a31224;border:1px solid #f7c5ca}
a{color:#2257d2;text-decoration:none}
a:hover{text-decoration:underline}
</style></head><body>
<h1>Single Evals — Report</h1>
<div class="small">Generated: $now • Items: $n • Pass rate: $pass_rate% • Avg score: $avg</div>
<div class="kpi">
  <div class="card">Pass rate: <b>$pass_rate%</b></div>
  <div class="card">Avg score: <b>$avg</b></div>
  <div class="card"><a href="$chat_index_uri">Chat index →</a></div>
</div>
<table>
<thead><tr><th>Eval ID</th><th>Score</th><th>Result</th><th>Top Findings</th><th>Chat</th></tr></thead>
<tbody>
$rows
</tbody>
</table>
</body></html>""")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged_glob", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir).resolve()
    chatdir = (outdir / "chat").resolve()
    os.makedirs(outdir, exist_ok=True)

    paths = sorted(glob.glob(ap.parse_args().judged_glob))
    rows, scores, passes = [], [], 0

    # CSV with absolute file:// URIs for easy clicking from spreadsheet apps
    csv_path = outdir / "summary.csv"
    with open(csv_path, "w", encoding="utf-8") as csv:
        csv.write("eval_id,score,pass,chat\n")
        for p in paths:
            j = json.load(open(p, "r", encoding="utf-8"))
            eid = j.get("eval_id", os.path.splitext(os.path.basename(p))[0])
            sc  = int(j.get("score", 0))
            ps  = bool(j.get("pass", False))
            scores.append(sc)
            if ps: passes += 1
            chat_uri = (chatdir / f"{eid}.html").as_uri()
            top = ""
            if isinstance(j.get("findings"), list) and j["findings"]:
                top = j["findings"][0]
            badge = f'<span class="badge {"pass" if ps else "fail"}">{"PASS" if ps else "FAIL"}</span>'
            rows.append(
                f"<tr>"
                f"<td><a href='{chat_uri}'>{eid}</a></td>"
                f"<td>{sc}</td>"
                f"<td>{badge}</td>"
                f"<td>{top}</td>"
                f"<td><a href='{chat_uri}'>Open chat</a></td>"
                f"</tr>"
            )
            csv.write(f"{eid},{sc},{ps},{chat_uri}\n")

    n = len(paths)
    avg = round(sum(scores)/n) if n else 0
    pass_rate = round(100*passes/n, 1) if n else 0.0
    chat_index_uri = (chatdir / "index.html").as_uri()
    html = HTML.substitute(
        now=datetime.now(timezone.utc).isoformat(),
        n=n, pass_rate=pass_rate, avg=avg, rows="\n".join(rows),
        chat_index_uri=chat_index_uri
    )
    out_path = outdir / "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote", out_path, "and", csv_path)

if __name__ == "__main__":
    main()

import json, argparse, html
from pathlib import Path
from string import Template

THEME = {"bg":"#f8fafc","card":"#fff","border":"#e6e8eb","userc":"#fff","userb":"#e6e8eb","asstc":"#eef6ff","asstb":"#cfe0ff"}

PAGE = Template("""<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
:root{--bg:$bg;--card:$card;--border:$border;--userc:$userc;--userb:$userb;--asstc:$asstc;--asstb:$asstb}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg)}
.header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--border);padding:12px 16px;display:flex;justify-content:space-between;align-items:center}
.header .meta{font-size:14px;color:#555}
.container{max-width:1000px;margin:24px auto;padding:0 12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:0 1px 2px rgba(0,0,0,.04);padding:16px;margin-bottom:16px}
.badge{padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600}
.badge.pass{background:#e9f9ee;color:#127c3a;border:1px solid #bfe8cc}
.badge.fail{background:#fdeceb;color:#a31224;border:1px solid #f7c5ca}
.small{font-size:12px;color:#666}
.chat{display:flex;flex-direction:column;gap:12px;margin-top:12px}
.bubble{max-width:75%;padding:12px 14px;border-radius:14px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}
.user{align-self:flex-start;background:var(--userc);border:1px solid var(--userb)}
.assistant{align-self:flex-end;background:var(--asstc);border:1px solid var(--asstb)}
.speaker{font-weight:700;margin-bottom:6px;opacity:.85}
.input-wrap{display:flex;gap:8px;align-items:center;border:1px solid var(--border);border-radius:14px;padding:10px 12px;background:#fff}
.input{flex:1;border:none;outline:none;font-size:14px;color:#333}
.input::placeholder{color:#999}
.btn{border:1px solid #d0d7ff;background:#e9f2ff;border-radius:10px;padding:8px 12px;font-weight:600;cursor:pointer}
.btn:active{transform:translateY(1px)}
</style></head><body>
<div class="header">
  <div class="meta"><b>$eid</b> • Score: <b>$score</b> • <span class="badge $passcls">$passlbl</span></div>
  <div class="small"><a href="../index.html">← Back to report</a> • <a href="index.html">All chats</a></div>
</div>
<div class="container">
  <div class="card">
    <div><b>Findings</b></div>
    <ul class="small">$findings</ul>
    <div class="small">$rationale</div>
  </div>
  <div class="card">
    <div><b>Meta</b></div>
    <div class="small">Model: $model • Temp: $temp • When: $ts</div>
  </div>
  <div class="card">
    <div class="chat">
      <div class="bubble assistant"><div class="speaker">Sales Representative</div>$rep</div>
      <div class="bubble user"><div class="speaker">Dr Tawel</div>$hcp</div>
    </div>
    <div style="height:12px"></div>
    <div class="input-wrap">
      <input class="input" placeholder="Message Dr Tawel" />
      <button class="btn">Send</button>
    </div>
    <div class="small" style="margin-top:6px;opacity:.7">Static preview for assessment purposes.</div>
  </div>
</div>
</body></html>""")

INDEX = Template("""<!doctype html><html><head>
<meta charset="utf-8"><title>Chat Views</title>
<style>
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px}
h1{margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-top:12px}
.card{border:1px solid #eee;border-radius:12px;padding:10px;background:#fff}
.pass{color:#127c3a}
.fail{color:#a31224}
.small{font-size:12px;color:#666}
a{color:#2257d2;text-decoration:none}
a:hover{text-decoration:underline}
</style></head><body>
<h1>Chat Views</h1>
<div class="small">Base: $base • Theme: split</div>
<div class="grid">
$items
</div>
</body></html>""")

def load(p): 
    return json.load(open(p,"r",encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="results/run_latest/latest")
    args = ap.parse_args()

    base = Path(args.base)
    gen_dir, judged_dir = base/"gen", base/"judged"
    out_dir = base/"report"/"chat"; out_dir.mkdir(parents=True, exist_ok=True)

    # Use *all* gens as the source of truth (50 expected)
    gens = {load(p)["eval_id"]: p for p in sorted(gen_dir.glob("*.gen.json"))}
    judges = {}
    for p in sorted(judged_dir.glob("*.judge.json")):
        try:
            j = load(p); judges[j.get("eval_id") or p.stem] = j
        except Exception:
            continue

    entries = []
    for eid in sorted(gens.keys(), key=lambda x: int(x[1:]) if x[1:].isdigit() else x):
        g = load(gens[eid])
        j = judges.get(eid, {"score":0,"pass":False,"findings":[],"rationale":""})
        rep = html.escape(g.get("rep_input",""))
        hcp = html.escape(g.get("model_output",""))
        findings = "".join(f"<li>{html.escape(x)}</li>" for x in (j.get("findings") or [])[:5]) or "<li><i>No findings</i></li>"
        page = PAGE.substitute(
            title=f"{eid} — Chat View", eid=eid,
            bg=THEME["bg"], card=THEME["card"], border=THEME["border"],
            userc=THEME["userc"], userb=THEME["userb"], asstc=THEME["asstc"], asstb=THEME["asstb"],
            score=int(j.get("score",0)), passcls=("pass" if j.get("pass") else "fail"), passlbl=("PASS" if j.get("pass") else "FAIL"),
            findings=findings, rationale=html.escape(j.get("rationale","")),
            model=html.escape(g.get("model","")), temp=g.get("temperature",""), ts=html.escape(g.get("timestamp","")),
            rep=rep, hcp=hcp
        )
        (out_dir/f"{eid}.html").write_text(page, encoding="utf-8")
        entries.append((eid, int(j.get("score",0)), bool(j.get("pass",False))))

    items=[]
    for eid,score,passed in sorted(entries, key=lambda x:(-x[1],x[0])):
        cls="pass" if passed else "fail"
        items.append(f'<div class="card"><a href="{eid}.html"><b>{eid}</b></a><br><span class="{cls}">{"PASS" if passed else "FAIL"}</span> · {score}</div>')
    (out_dir/"index.html").write_text(INDEX.substitute(base=str(base), items="\n".join(items)), encoding="utf-8")
    print(f"Chat pages -> {out_dir} (count={len(entries)})")

if __name__ == "__main__":
    main()

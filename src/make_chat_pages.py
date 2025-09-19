#!/usr/bin/env python3
from pathlib import Path
import argparse, json, html, glob, os

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>{eid} · Chat</title>
<style>
  body {{ font-family:-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#fafafa; margin:24px; }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  .hdr a {{ text-decoration:none; color:#2563eb; }}
  .badge {{ display:inline-block; font-size:12px; font-weight:600; padding:4px 8px; border-radius:999px; }}
  .pass {{ background:#ecfdf5; color:#065f46; }}
  .fail {{ background:#fef2f2; color:#991b1b; }}
  .score {{ color:#64748b; margin-left:8px; font-weight:500; }}
  .topfindings {{ background:#fff; padding:12px 14px; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,.08); margin:12px 0 20px; }}
  .topfindings ul {{ margin:6px 0 0 18px; }}
  .row {{ display:flex; gap:16px; margin:12px 0; }}
  .bubble {{ padding:12px 14px; border-radius:14px; line-height:1.35; box-shadow:0 1px 3px rgba(0,0,0,.08); background:white; }}
  .rep   {{ justify-content:flex-end; }}
  .rep .bubble {{ background:#eef6ff; }}
  .hcp .bubble {{ background:#fff; }}
  .meta {{ color:#64748b; font-size:12px; margin-bottom:6px; }}
  .ibox {{ margin-top:24px; border-top:1px dashed #e5e7eb; padding-top:14px; display:flex; gap:10px; }}
  .ibox input {{ flex:1; padding:10px 12px; border:1px solid #e5e7eb; border-radius:10px; }}
  .ibox button {{ padding:10px 14px; border:0; border-radius:10px; background:#111827; color:white; }}
</style>
<div class="wrap">
  <div class="hdr">
    <div class="meta"><a href="../index.html">« Chat Index</a></div>
    <h2 style="margin:6px 0 10px 0;">{eid}</h2>
    {badge_html}{score_html}
  </div>

  {findings_html}

  <div class="chat">
    <div class="row rep"><div class="bubble">
      <div class="meta">Sales Representative</div>{user_html}
    </div></div>

    <div class="row hcp"><div class="bubble">
      <div class="meta">Dr Tawel</div>{asst_html}
    </div></div>
  </div>

  <div class="ibox">
    <input placeholder="Message Dr Tawel" disabled value="">
    <button disabled>Send</button>
  </div>
</div>
"""

INDEX = """<!doctype html>
<meta charset="utf-8">
<title>Chat Index</title>
<style>
  body {{ font-family:-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#fafafa; margin:24px; }}
  a {{ color:#2563eb; text-decoration:none; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  table {{ width:100%; border-collapse:collapse; background:white; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #f1f5f9; }}
  th {{ background:#f8fafc; font-weight:600; }}
  .badge {{ display:inline-block; font-size:12px; font-weight:600; padding:2px 6px; border-radius:999px; }}
  .pass {{ background:#ecfdf5; color:#065f46; }}
  .fail {{ background:#fef2f2; color:#991b1b; }}
  .score {{ color:#64748b; margin-left:8px; }}
</style>
<div class="wrap">
  <h2>Chat Index</h2>
  <table>
    <tr><th>Eval ID</th><th>Status</th><th>Open</th></tr>
    {rows}
  </table>
</div>
"""

USER_KEYS = ["user","user_input","prompt","sales_rep","rep_input","message","text"]
ASST_KEYS = ["assistant","assistant_text","output","response","text","hcp_output","content"]

def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)

def _pick_best(strings, min_len=1):
    items = [s.strip() for s in strings if isinstance(s,str) and s.strip()]
    if not items: return ""
    items.sort(key=len, reverse=True)
    for s in items:
        if len(s) >= min_len:
            return s
    return items[0]

def _get_by_keys(j, keys):
    for k in keys:
        v = j.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            c = v.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()
        if isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    msg = it.get("message") or it.get("delta") or {}
                    c = msg.get("content")
                    if isinstance(c, str) and c.strip():
                        return c.strip()
    return ""

def extract_user_text(j):
    s = _get_by_keys(j, USER_KEYS)
    if s: return s
    if isinstance(j.get("input"), dict):
        s = _get_by_keys(j["input"], USER_KEYS)
        if s: return s
    src = j.get("input") if isinstance(j.get("input"), dict) else j
    return _pick_best(list(_walk_strings(src)), min_len=12)

def extract_asst_text(j):
    s = _get_by_keys(j, ASST_KEYS)
    if s: return s
    for k in ("gen_text", "hcp_output", "assistant_message", "assistant_response"):
        v = j.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    if "choices" in j:
        s = _get_by_keys(j, ["choices"])
        if s: return s
    return _pick_best(list(_walk_strings(j)), min_len=24)

def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()

    base = Path(args.base).resolve()
    gen_dir = base / "gen"
    judged_dir = base / "judged"
    out_dir = base / "report" / "chat"
    out_dir.mkdir(parents=True, exist_ok=True)

    gens = {}
    for p in sorted(gen_dir.glob("*.gen.json")):
        j = load_json(p)
        eid = j.get("eval_id") or p.stem
        gens[eid] = j

    judged = {}
    for p in sorted(judged_dir.glob("*.judge.json")):
        j = load_json(p)
        eid = j.get("eval_id") or p.stem.replace(".judge","")
        judged[eid] = j

    for eid, j in gens.items():
        user = extract_user_text(j) or "(no rep message captured)"
        asst = extract_asst_text(j) or "(no assistant message captured)"
        user_html = html.escape(user).replace("\n", "<br>")
        asst_html = html.escape(asst).replace("\n", "<br>")

        jj = judged.get(eid, {})
        ps = jj.get("pass")
        score = jj.get("score")
        if score is None and isinstance(jj.get("overall"), dict):
            sc = jj["overall"].get("weighted_score") or jj["overall"].get("score")
            if isinstance(sc, float):
                score = round(sc*100) if sc <= 1.0 else int(sc)
            elif isinstance(sc, int):
                score = sc

        if ps is not None:
            cls = "pass" if ps else "fail"
            txt = "PASS" if ps else "FAIL"
            badge_html = f'<span class="badge {cls}">{txt}</span>'
        else:
            badge_html = ""

        score_html = f'<span class="score">Score: {score}</span>' if score is not None else ""

        findings_html = ""
        f = jj.get("findings") or jj.get("evidence")
        if isinstance(f, list) and f:
            bullets = []
            for item in f[:4]:
                q = (item.get("quote") if isinstance(item, dict) else str(item)) or ""
                q = html.escape(q).strip()
                if q:
                    bullets.append(f"<li>{q}</li>")
            if bullets:
                findings_html = f'<div class="topfindings"><b>Top Findings</b><ul>' + "\n".join(bullets) + "</ul></div>"

        (out_dir / f"{eid}.html").write_text(
            PAGE.format(
                eid=eid,
                user_html=user_html,
                asst_html=asst_html,
                badge_html=badge_html,
                score_html=score_html,
                findings_html=findings_html,
            ),
            encoding="utf-8",
        )

    rows = []
    for eid in sorted(gens):
        jj = judged.get(eid, {})
        ps = jj.get("pass")
        score = jj.get("score")
        if score is None and isinstance(jj.get("overall"), dict):
            sc = jj["overall"].get("weighted_score") or jj["overall"].get("score")
            if isinstance(sc, float):
                score = round(sc*100) if sc <= 1.0 else int(sc)
            elif isinstance(sc, int):
                score = sc
        if ps is not None:
            cls = "pass" if ps else "fail"
            badge = f'<span class="badge {cls}">{"PASS" if ps else "FAIL"}</span>'
        else:
            badge = ""
        sc = f'<span class="score">{score}</span>' if score is not None else ""
        rows.append(f'<tr><td>{eid}</td><td>{badge} {sc}</td><td><a href="{eid}.html">Open chat</a></td></tr>')

    (out_dir / "index.html").write_text(INDEX.format(rows="\n".join(rows)), encoding="utf-8")
    print(f"Chat pages -> {out_dir} (count={len(gens)})")

if __name__ == "__main__":
    main()

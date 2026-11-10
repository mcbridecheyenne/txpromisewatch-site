postiz posts:list --startDate "2026-11-10T12:00:00Z" --endDate "2026-11-11T06:00:00Z" 2>&1 | sed -n '/^[[{]/,$p' > p.json
python3 - <<'PY'
import json
raw=json.load(open("p.json")); posts=raw["posts"] if isinstance(raw,dict) else raw
for p in sorted(posts,key=lambda x:x["publishDate"]):
    if "tiktok" not in p["integration"]["providerIdentifier"]: continue
    s=p.get("settings"); s=json.loads(s) if isinstance(s,str) else (s or {})
    print("TT", p["publishDate"], p["state"], s.get("title","")[:70], "| music:", (s.get("music") or {}).get("title"))
PY

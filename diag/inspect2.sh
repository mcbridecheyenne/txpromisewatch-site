set -u
TT=cmw21kbr201nrl808vqs2hovq
postiz posts:list --startDate "2026-11-09T00:00:00Z" --endDate "2026-11-12T23:59:59Z" 2>&1 | sed -n '/^[[{]/,$p' > p.json
python3 - <<'PY'
import json
raw=json.load(open("p.json")); posts=raw["posts"] if isinstance(raw,dict) else raw
t=[p for p in posts if "tiktok" in p["integration"]["providerIdentifier"]]
print("keys:", sorted(t[0].keys()))
for p in t[:4]:
    print(p["id"], p.get("state"), {k:(str(v)[:400]) for k,v in p.items() if k in ("image","media","value","attachments")})
PY
postiz integrations:settings $TT 2>&1 | sed -n '/^[[{]/,$p' | jq '.output.tools'
for q in "news" "corporate" "documentary" "ambient" "upbeat"; do
  echo "== musicSearch $q"
  postiz integrations:trigger $TT musicSearch -d "{\"query\":\"$q\"}" 2>&1 | sed -n '/^[[{]/,$p' | jq -c '.output[:6][]? // .' | cut -c1-300
done

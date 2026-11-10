"""Print TikTok/Instagram posts from `postiz posts:list` and probe each media file for an audio track."""
import json, subprocess, sys
raw = json.load(open(sys.argv[1])); posts = raw["posts"] if isinstance(raw, dict) else raw
print("total posts:", len(posts))
from collections import Counter
print(Counter((p["integration"]["providerIdentifier"], p.get("state")) for p in posts))
def probe(url):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,duration",
                              "-show_entries", "format=duration,format_name", "-of", "json", url],
                             capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
        streams = [s.get("codec_type") + ":" + s.get("codec_name", "?") for s in d.get("streams", [])]
        return {"format": d.get("format", {}).get("format_name"), "dur": d.get("format", {}).get("duration"),
                "streams": streams, "err": out.stderr.strip()[:200]}
    except Exception as e:
        return {"err": str(e)}
seen = 0
for p in sorted(posts, key=lambda x: x.get("publishDate", "")):
    prov = p["integration"]["providerIdentifier"]
    if "tiktok" not in prov and "instagram" not in prov: continue
    seen += 1
    if "instagram" in prov and seen > 60: continue
    imgs = p.get("image") or "[]"
    try: imgs = json.loads(imgs) if isinstance(imgs, str) else imgs
    except Exception: pass
    settings = p.get("settings")
    print("\n---", prov, p["id"], p.get("state"), p.get("publishDate"), "group:", p.get("group"))
    print("content:", (p.get("content") or "")[:90].replace("\n", " "))
    print("settings:", settings)
    print("error:", p.get("error"), "releaseURL:", p.get("releaseURL"))
    for m in imgs if isinstance(imgs, list) else []:
        path = m.get("path") if isinstance(m, dict) else m
        print("  media:", path, probe(path) if path else "")

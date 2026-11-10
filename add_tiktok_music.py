"""Give every unpublished TikTok post in Postiz a TikTok Commercial Music Library track.
Usage: python3 add_tiktok_music.py <postiz_list.json> [--dry-run]
The reel MP4s carry a silent audio track, so without this TikTok posts go out with no sound.
Exits 1 if any post still needs music (in --dry-run, if any post needs it at all)."""
import json, subprocess, sys, zlib
src = sys.argv[1]; dry = "--dry-run" in sys.argv
cfg = json.load(open("tiktok_music.json"))
raw = json.load(open(src)); posts = raw["posts"] if isinstance(raw, dict) else raw
todo = []
for p in posts:
    if "tiktok" not in p["integration"]["providerIdentifier"]: continue
    if p.get("state") not in ("DRAFT", "QUEUE"): continue
    s = p.get("settings") or {}
    if isinstance(s, str):
        try: s = json.loads(s)
        except Exception: s = {}
    if (s.get("music") or {}).get("id") or s.get("autoAddMusic") == "yes": continue
    todo.append((p, s))
print(f"TikTok posts needing music: {len(todo)}")
failed = 0
for p, s in todo:
    t = cfg["tracks"][zlib.crc32(p["id"].encode()) % len(cfg["tracks"])]
    label = f"{p['state']} {p.get('publishDate')} {s.get('title', '')[:60]!r} -> {t['title']} ({t['artist']})"
    if dry:
        print("  needs music:", label); failed += 1; continue
    patch = {"autoAddMusic": "no", "content_posting_method": "DIRECT_POST",
             "music": {**t, "audio_volume": cfg["audio_volume"], "video_volume": cfg["video_volume"]}}
    r = subprocess.run(["postiz", "posts:settings", p["id"], "--settings", json.dumps(patch)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "eprecation" not in l)
    ok = r.returncode == 0 and "settings updated" in out
    failed += not ok
    print(("  added: " if ok else "  FAILED: ") + label + ("" if ok else "\n    " + out[:500]))
sys.exit(1 if failed else 0)

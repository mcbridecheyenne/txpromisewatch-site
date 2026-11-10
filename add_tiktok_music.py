"""Give every unpublished TikTok post in Postiz a Commercial Music Library track.
Usage: python3 add_tiktok_music.py <postiz_list.json> [--dry-run]
The reel MP4s carry a silent audio track, so without this TikTok posts go out with no sound.
Prints one postiz command per post that needs music; lists those posts on stderr."""
import json, shlex, sys, zlib
src = sys.argv[1]; dry = "--dry-run" in sys.argv
cfg = json.load(open("tiktok_music.json"))
raw = json.load(open(src)); posts = raw["posts"] if isinstance(raw, dict) else raw
for p in posts:
    if "tiktok" not in p["integration"]["providerIdentifier"]: continue
    if p.get("state") not in ("DRAFT", "QUEUE"): continue
    s = p.get("settings") or {}
    if isinstance(s, str):
        try: s = json.loads(s)
        except Exception: s = {}
    if (s.get("music") or {}).get("id") or s.get("autoAddMusic") == "yes": continue
    t = cfg["tracks"][zlib.crc32(p["id"].encode()) % len(cfg["tracks"])]
    patch = {"autoAddMusic": "no", "content_posting_method": "DIRECT_POST",
             "music": {**t, "audio_volume": cfg["audio_volume"], "video_volume": cfg["video_volume"]}}
    print(f"# {p['state']} {p.get('publishDate')} {s.get('title','')[:60]!r} -> {t['title']} ({t['artist']})", file=sys.stderr)
    if not dry:
        print(f"postiz posts:settings {p['id']} --settings {shlex.quote(json.dumps(patch))}")

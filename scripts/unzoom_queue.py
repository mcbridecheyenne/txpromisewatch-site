"""Swap no-zoom, safe-box videos into queued Facebook and TikTok reel posts in Postiz.
Usage: python3 unzoom_queue.py <postiz_list.json> <media.json> <plan.json> <outdir>
TikTok posts: rebuilt from their original upload (before the +3 s retime), +3 s per picture,
with the safe end card. Facebook reel posts: their video is the FB upload made just before the
paired TikTok upload, matched by picture. When plan.apply is true, each new video is uploaded and
the post recreated with the same caption, time, state and settings (FB: the first comment gets the
source links of the regular post at the same time), then the old post is deleted."""
import json, os, subprocess, sys, datetime
import numpy as np
from PIL import Image
lst, media_path, plan_path, out = sys.argv[1:5]
plan = json.load(open(plan_path)); apply = plan.get("apply") is True
os.makedirs(out, exist_ok=True)
raw = json.load(open(lst)); posts = raw["posts"] if isinstance(raw, dict) else raw
media = {m["name"][:-4]: m for m in json.load(open(media_path))}
now = datetime.datetime.now(datetime.timezone.utc)
here = os.path.dirname(os.path.abspath(__file__))
END = os.path.join(here, "endcard_safe.png")
report = []

def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr

def last_json(text):
    i = min([k for k in (text.find("{"), text.find("[")) if k >= 0], default=-1)
    return json.loads(text[i:]) if i >= 0 else None

def fetch(name):
    f = f"{name}.mp4"
    if not os.path.exists(f):
        rc, o, e = run("curl", "-sSf", "-o", f, media[name]["path"] if name in media else f"https://uploads.postiz.com/{name}.mp4")
        if rc: raise RuntimeError("download " + e[:200])
    return f

def thumb(f, t=1.0):
    rc, o, e = run("ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", f, "-frames:v", "1", "-vf", "scale=54:96", f + ".t.png")
    return np.asarray(Image.open(f + ".t.png").convert("L")).astype(np.float32)

def settings_of(p):
    s = p.get("settings") or {}
    return json.loads(s) if isinstance(s, str) else s

def sources_comment(when):
    for q in posts:
        if q["publishDate"] == when and q["integration"]["providerIdentifier"] == "facebook" and q["content"].startswith("\U0001F4CC"):
            urls = [l.strip() for l in q["content"].splitlines() if l.strip().startswith("http")]
            if urls: return "Sources:\n" + "\n".join(urls)
    return None

tt_plan = plan["tiktok"]
tt_by_date = {}
for pid, m in tt_plan.items(): tt_by_date[m["publishDate"]] = (pid, m["orig_media"])
tt_media_names = {m["orig_media"] for m in tt_plan.values()} | {m["retimed_media"] for m in tt_plan.values()}

jobs = []
for p in sorted(posts, key=lambda x: x["publishDate"]):
    prov = p["integration"]["providerIdentifier"]
    if p["id"] in plan.get("exclude", []) or p.get("state") not in ("DRAFT", "QUEUE"): continue
    when = datetime.datetime.fromisoformat(p["publishDate"].replace("Z", "+00:00"))
    if prov == "tiktok-business":
        if p["id"] not in tt_plan:
            report.append({"post": p["id"], "publishDate": p["publishDate"], "result": "skipped: TikTok post not in plan"}); continue
        jobs.append((p, "tiktok", tt_plan[p["id"]]["orig_media"], None))
    elif prov == "facebook" and "title" in settings_of(p) and not p["content"].startswith("\U0001F4CC"):
        jobs.append((p, "facebook", None, p["publishDate"]))

for p, kind, src_name, date in jobs:
    s = settings_of(p)
    row = {"post": p["id"], "kind": kind, "publishDate": p["publishDate"], "state": p["state"], "title": s.get("title")}
    report.append(row)
    try:
        when = datetime.datetime.fromisoformat(p["publishDate"].replace("Z", "+00:00"))
        if when < now + datetime.timedelta(minutes=20): row["result"] = "skipped: posts too soon"; continue
        if kind == "facebook":
            if date not in tt_by_date: row["result"] = "skipped: no paired TikTok in plan"; continue
            tt_name = tt_by_date[date][1]; tt_f = fetch(tt_name)
            t0 = media[tt_name]["createdAt"]
            t0d = datetime.datetime.fromisoformat(t0.replace("Z", "+00:00"))
            cands = [n for n, m in media.items() if n not in tt_media_names and
                     datetime.timedelta(0) < t0d - datetime.datetime.fromisoformat(m["createdAt"].replace("Z", "+00:00")) < datetime.timedelta(minutes=15)]
            ref = thumb(tt_f)
            scores = sorted((float(np.abs(thumb(fetch(n)) - ref).mean()), n) for n in cands)
            row["fb_candidates"] = [(round(a, 2), n) for a, n in scores[:4]]
            if not scores or scores[0][0] > 6: row["result"] = "failed: no matching FB video"; continue
            src_name = scores[0][1]
        row["src_media"] = src_name
        srcf = fetch(src_name); dst = os.path.join(out, f"{p['id']}.mp4")
        args = ["python3", os.path.join(here, "unzoom_reel.py"), srcf, dst, "--sheet", os.path.join(out, f"{p['publishDate'][:16].replace(':', '')}_{kind}.jpg")]
        if kind == "tiktok": args += ["--extra", "3", "--endcard", END]
        rc, o, e = run(*args)
        if rc: row["result"] = "failed: rebuild " + (e or o)[-300:]; continue
        info = json.loads(o.strip().splitlines()[-1]); row.update(in_s=info["in_s"], out_s=info["out_s"], pictures=info["pictures"],
                                                         shrunk=[x["pic"] for x in info["pics"] if x.get("shrunk")])
        if info["out_s"] < 10 or info["pictures"] < 3: row["result"] = "failed: unexpected length or picture count"; continue
        if kind == "facebook" and not 15 <= info["out_s"] <= 30.5: row["result"] = "failed: FB length"; continue
        if kind == "tiktok" and info["out_s"] > 60: row["result"] = "failed: TikTok over 60 s"; continue
        if not apply: row["result"] = "dry run ok"; continue
        rc, o, e = run("postiz", "upload", dst)
        up = last_json(o) if rc == 0 else None
        if not up or not up.get("path"): row["result"] = "failed: upload " + (e or o)[:300]; continue
        settings = {k: v for k, v in s.items() if k != "__type"}
        cmd = ["postiz", "posts:create", "-i", p["integration"]["id"], "-c", p["content"], "-m", up["path"]]
        if kind == "facebook":
            com = sources_comment(p["publishDate"])
            if com: cmd += ["-c", com]
            row["first_comment"] = com
        cmd += ["-s", p["publishDate"], "-t", "draft" if p["state"] == "DRAFT" else "schedule",
                "--no-shortLink", "--settings", json.dumps(settings)]
        rc, o, e = run(*cmd)
        created = last_json(o) if rc == 0 else None
        ids = [x.get("postId") or x.get("id") for x in (created if isinstance(created, list) else [created or {}])]
        ids = [x for x in ids if x]
        if not ids: row["result"] = "failed: create " + (e or o)[:400]; continue
        row["new_post"] = ids[0]; row["new_media"] = up["path"]
        rc, o, e = run("postiz", "posts:delete", p["id"])
        row["result"] = "replaced" if rc == 0 else "created new but old not deleted: " + (e or o)[:200]
    except Exception as ex:
        row["result"] = f"failed: {ex}"[:300]

json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
for r in report:
    print(r.get("result"), r.get("kind"), r["post"], r.get("publishDate"), r.get("src_media"), r.get("in_s"), "->", r.get("out_s"), "shrunk", r.get("shrunk"), r.get("fb_candidates", ""))
sys.exit(1 if any(str(r.get("result", "")).startswith("failed") for r in report) else 0)

"""Swap longer-timed videos into queued TikTok posts in Postiz.
Usage: python3 retime_queue.py <postiz_list.json> <plan.json> <outdir>
For each post in the plan: download its current video, hold every picture longer
(retime_reel.py), and, when plan.apply is true, upload it, recreate the post with the
same caption, time, state and settings (music included), then delete the old post."""
import json, os, subprocess, sys, datetime
src, plan_path, out = sys.argv[1:4]
plan = json.load(open(plan_path)); apply = plan.get("apply") is True
os.makedirs(out, exist_ok=True)
raw = json.load(open(src)); posts = raw["posts"] if isinstance(raw, dict) else raw
by_id = {p["id"]: p for p in posts}
now = datetime.datetime.now(datetime.timezone.utc)
here = os.path.dirname(os.path.abspath(__file__))
report = []

def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr

def last_json(text):
    i = min([k for k in (text.find("{"), text.find("[")) if k >= 0], default=-1)
    return json.loads(text[i:]) if i >= 0 else None

for pid, media in plan["posts"].items():
    row = {"post": pid, "media": media}
    report.append(row)
    p = by_id.get(pid)
    if not p: row["result"] = "skipped: post not found (published or deleted)"; continue
    if "tiktok" not in p["integration"]["providerIdentifier"] or p.get("state") not in ("DRAFT", "QUEUE"):
        row["result"] = f"skipped: state {p.get('state')}"; continue
    when = datetime.datetime.fromisoformat(p["publishDate"].replace("Z", "+00:00"))
    s = p.get("settings") or {}
    s = json.loads(s) if isinstance(s, str) else s
    row.update(state=p["state"], publishDate=p["publishDate"], title=s.get("title"))
    if when < now + datetime.timedelta(minutes=20):
        row["result"] = "skipped: posts too soon"; continue
    srcf, dstf = f"{media}.mp4", os.path.join(out, f"{pid}.mp4")
    rc, o, e = run("curl", "-sSf", "-o", srcf, f"https://uploads.postiz.com/{media}.mp4")
    if rc: row["result"] = "failed: download " + e[:200]; continue
    rc, o, e = run("python3", os.path.join(here, "retime_reel.py"), srcf, dstf,
                   "--extra", str(plan.get("extra_seconds", 3)), "--sheet", os.path.join(out, f"{pid}.jpg"))
    if rc: row["result"] = "failed: retime " + (e or o)[:300]; continue
    info = json.loads(o.strip().splitlines()[-1]); row.update(info)
    if info["out_s"] < 10 or info["pictures"] < 3:
        row["result"] = "failed: unexpected length or picture count"; continue
    if not apply:
        row["result"] = "dry run ok"; continue
    shared = [q["id"] for q in posts if q.get("group") == p.get("group") and q["id"] != pid]
    if shared: row["result"] = f"skipped: shares a post group with {shared}"; continue
    rc, o, e = run("postiz", "upload", dstf)
    up = last_json(o) if rc == 0 else None
    if not up or not up.get("path"): row["result"] = "failed: upload " + (e or o)[:300]; continue
    settings = {k: v for k, v in s.items() if k != "__type"}
    rc, o, e = run("postiz", "posts:create", "-i", p["integration"]["id"], "-c", p["content"], "-m", up["path"],
                   "-s", p["publishDate"], "-t", "draft" if p["state"] == "DRAFT" else "schedule",
                   "--no-shortLink", "--settings", json.dumps(settings))
    created = last_json(o) if rc == 0 else None
    new_ids = [x.get("postId") or x.get("id") for x in (created if isinstance(created, list) else [created or {}])]
    new_ids = [x for x in new_ids if x]
    if not new_ids: row["result"] = "failed: create " + (e or o)[:400]; continue
    row["new_post"] = new_ids[0]; row["new_media"] = up["path"]
    rc, o, e = run("postiz", "posts:delete", pid)
    row["result"] = "replaced" if rc == 0 else "created new but old not deleted: " + (e or o)[:200]

json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
for r in report: print(r.get("result"), r["post"], r.get("publishDate"), r.get("title"), r.get("in_s"), "->", r.get("out_s"))
sys.exit(1 if any(str(r.get("result", "")).startswith("failed") for r in report) else 0)

"""Build posts.json for TXPromiseWatch.com from Postiz Facebook posts that are approved (QUEUE) or published.
Usage: python3 sync_feed.py <postiz_list.json> <repo/posts.json>
Keeps existing entries (and any image_url already set), adds new ones, never includes drafts."""
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
raw = json.load(open(src)); posts = raw["posts"] if isinstance(raw, dict) else raw
try: feed = {p["id"]: p for p in json.load(open(dst))}
except Exception: feed = {}
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
for p in posts:
    if p["integration"]["providerIdentifier"] != "facebook": continue
    if p.get("state") not in ("QUEUE", "PUBLISHED"): continue
    text = p["content"].strip()
    first, _, rest = text.partition("\n")
    headline = EMOJI.sub("", first).strip(" :")
    low = text.lower()
    kind = ("promise" if "promise check" in low else "profile" if low.startswith(("📋", "what did")) or "what did" in first.lower()
            else "scorecard" if "scorecard" in first.lower() else "explainer")
    urls = re.findall(r"https?://[^\s)]+", text)
    body = rest.strip()
    old = feed.get(p["id"], {})
    feed[p["id"]] = {"id": p["id"], "published_at": p["publishDate"], "kind": old.get("kind", kind),
                     "headline": headline, "body": body, "sources": urls,
                     "image_url": old.get("image_url"), "video_url": old.get("video_url"),
                     "facebook_url": p.get("releaseURL") or old.get("facebook_url")}
out = sorted(feed.values(), key=lambda x: x["published_at"], reverse=True)
json.dump(out, open(dst, "w"), indent=1, ensure_ascii=False)
print(f"{len(out)} posts in feed")

# TXPromiseWatch.com

Website for Texas Promise Watch: a news feed of every approved post.

- `index.html` – the whole site (one page).
- `posts.json` – the feed. Posts only appear once their `published_at` time has passed.
- `sync_feed.py` – rebuilds `posts.json` from Postiz (`postiz posts:list` output). Only approved/published Facebook posts are included, never drafts.
- `CNAME` – custom domain for GitHub Pages.
- `add_tiktok_music.py` + `tiktok_music.json` – every 10 minutes (`.github/workflows/tiktok-music.yml`) gives any queued or draft TikTok post a TikTok Commercial Music Library track, since the reel MP4s are silent. Edit `tiktok_music.json` to change the tracks.

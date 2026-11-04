# TXPromiseWatch.com

Website for Texas Promise Watch: a news feed of every approved post.

- `index.html` – the whole site (one page).
- `posts.json` – the feed. Posts only appear once their `published_at` time has passed.
- `sync_feed.py` – rebuilds `posts.json` from Postiz (`postiz posts:list` output). Only approved/published Facebook posts are included, never drafts.
- `CNAME` – custom domain for GitHub Pages.

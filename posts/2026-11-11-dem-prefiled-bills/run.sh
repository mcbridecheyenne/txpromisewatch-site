#!/usr/bin/env bash
# One-off post pipeline, run by .github/workflows/one-off-post.yml on pushes to post/** branches.
# stage=build   -> download Canva graphic + end card, build reels, list the Postiz queue, commit outputs for review
# stage=publish -> upload media and schedule FB / X / TikTok (+ IG if connected) at publish_at.txt, record ids
set -euo pipefail
cd "$(dirname "$0")"
STAGE=$(tr -d '[:space:]' < stage)
json() { sed -n '/^[[{]/,$p'; }
mkdir -p out
if [ "$STAGE" = build ]; then
  curl -fsSL -o out/graphic.png "$(cat canva_export_url.txt)"
  curl -fsSL -o out/endcard_src.png https://uploads.postiz.com/2M90RzVCnv.png
  python3 make_reel.py out/graphic.png out/endcard_src.png out
  postiz integrations:list | json > out/integrations.json
  postiz posts:list --startDate "$(date -u +%Y-%m-%dT00:00:00Z)" --endDate "$(date -u -d '+3 days' +%Y-%m-%dT00:00:00Z)" | json > out/plist.json
  python3 - <<'PY'
import json
d=json.load(open('out/plist.json')); d=d['posts'] if isinstance(d,dict) else d
with open('out/queue.txt','w') as f:
    for p in sorted(d,key=lambda p:p['publishDate']):
        f.write(f"{p['publishDate']} {p['state']} {p['integration']['providerIdentifier']} {p['content'][:70]!r}\n")
for i in json.load(open('out/integrations.json')):
    print(i['id'], i.get('identifier'), i.get('name'), i.get('profile'), i.get('disabled'))
PY
  cat out/queue.txt
elif [ "$STAGE" = replace ]; then
  # rebuild reels (no zoom, safe margins) from the committed graphic and swap them into the queued FB + TikTok posts
  test -f out/replaced.json && { echo "Already replaced"; cat out/replaced.json; exit 0; }
  curl -fsSL -o out/endcard_src.png https://uploads.postiz.com/2M90RzVCnv.png || true
  python3 make_reel.py out/graphic.png out/endcard_src.png out
  WHEN=$(tr -d '[:space:]' < publish_at.txt)
  up() { postiz upload "$1" | json | python3 -c "import json,sys;print(json.load(sys.stdin)['path'])"; }
  FBMP4=$(up out/reel_facebook.mp4); TTMP4=$(up out/reel_tiktok.mp4); echo "uploaded: $FBMP4 $TTMP4"
  python3 - "$FBMP4" "$TTMP4" "$WHEN" <<'PY'
import json, subprocess, sys
fb, tt, when = sys.argv[1:4]
old = {r['platform']: r for r in json.load(open('out/result.json'))}
def run(*c):
    r = subprocess.run(c, capture_output=True, text=True, stdin=subprocess.DEVNULL); return r.returncode, r.stdout + r.stderr
def created(o):
    i = min([k for k in (o.find('['), o.find('{')) if k >= 0]); j = json.loads(o[i:]); j = j if isinstance(j, list) else [j]
    return j[0].get('postId') or j[0].get('id')
out = {}
for plat, integ, media, content, extra in [
        ('facebook', 'cmw1op4mp0cztla07zr8ski3z', fb, open('facebook.txt').read(), ['-c', open('first_comment.txt').read()]),
        ('tiktok-business', 'cmw21kbr201nrl808vqs2hovq', tt, open('tiktok.txt').read(), [])]:
    o = old[plat]; s = {k: v for k, v in (o['settings'] or {}).items() if k != '__type'}
    rc, txt = run('postiz', 'posts:create', '-c', content, '-m', media, *extra, '-s', when, '--settings', json.dumps(s), '-i', integ)
    print(plat, 'create', rc, txt[-300:])
    if rc: out[plat] = {'result': 'create failed', 'old': o['id']}; continue
    new = created(txt)
    rc, txt = run('postiz', 'posts:delete', o['id']); print(plat, 'delete old', rc, txt[-200:])
    out[plat] = {'old': o['id'], 'new': new, 'old_deleted': rc == 0, 'media': media}
json.dump(out, open('out/replaced.json', 'w'), indent=1); print(json.dumps(out, indent=1))
PY
elif [ "$STAGE" = publish ]; then
  test -f out/result.json && { echo "Already published"; cat out/result.json; exit 0; }
  WHEN=$(tr -d '[:space:]' < publish_at.txt)
  up() { postiz upload "$1" | json | python3 -c "import json,sys;print(json.load(sys.stdin)['path'])"; }
  PNG=$(up out/graphic.png); FBMP4=$(up out/reel_facebook.mp4); TTMP4=$(up out/reel_tiktok.mp4)
  echo "uploaded: $PNG $FBMP4 $TTMP4"
  TITLE=$(cat tiktok_title.txt)
  FBSET=$(python3 -c "import json,sys;print(json.dumps({'post_type':'post','title':sys.argv[1]}))" "$TITLE")
  TTSET=$(python3 -c "
import json,sys
m=json.load(open('../../tiktok_music.json')); t=m['tracks'][0]
print(json.dumps({'title':sys.argv[1],'privacy_level':'PUBLIC_TO_EVERYONE','duet':False,'stitch':False,'comment':True,
 'autoAddMusic':'no','brand_content_toggle':False,'brand_organic_toggle':False,'video_made_with_ai':False,
 'content_posting_method':'DIRECT_POST','music':{**t,'audio_volume':m['audio_volume'],'video_volume':m['video_volume']}}))" "$TITLE")
  : > out/create.log
  postiz posts:create -c "$(cat facebook.txt)" -m "$FBMP4" -c "$(cat first_comment.txt)" -s "$WHEN" --settings "$FBSET" -i cmw1op4mp0cztla07zr8ski3z | tee -a out/create.log
  postiz posts:create -c "$(cat x.txt)" -m "$PNG" -s "$WHEN" --settings '{"post_type":"post","who_can_reply_post":"everyone"}' -i cmw1pgg8k0drqla078ivel5jr | tee -a out/create.log
  if postiz integrations:list | json | python3 -c "import json,sys;sys.exit(0 if any(i['id']=='cmw21kbr201nrl808vqs2hovq' and not i.get('disabled') for i in json.load(sys.stdin)) else 1)"; then
    postiz posts:create -c "$(cat tiktok.txt)" -m "$TTMP4" -s "$WHEN" --settings "$TTSET" -i cmw21kbr201nrl808vqs2hovq | tee -a out/create.log
  else echo "TikTok integration missing, skipped" | tee -a out/create.log; fi
  IG=$(postiz integrations:list | json | python3 -c "
import json,sys
for i in json.load(sys.stdin):
    if 'instagram' in (i.get('identifier') or '') and not i.get('disabled') and (i.get('name')=='Texas Promise Watch' or i.get('profile')=='texas_promise_watch'): print(i['id']); break")
  if [ -n "$IG" ]; then
    postiz posts:create -c "$(cat instagram.txt)" -m "$FBMP4" -s "$WHEN" --settings '{"post_type":"post"}' -i "$IG" | tee -a out/create.log
  else echo "No Instagram integration, skipped" | tee -a out/create.log; fi
  sleep 5
  postiz posts:list --startDate "$(date -u -d "$WHEN -1 hour" +%Y-%m-%dT%H:%M:%SZ)" --endDate "$(date -u -d "$WHEN +1 hour" +%Y-%m-%dT%H:%M:%SZ)" | json > out/after.json
  python3 - "$WHEN" <<'PY'
import json,sys
d=json.load(open('out/after.json')); d=d['posts'] if isinstance(d,dict) else d
mine=[p for p in d if p['publishDate'].startswith(sys.argv[1][:16]) and ('Filed isn' in p['content'])]
res=[{'id':p['id'],'platform':p['integration']['providerIdentifier'],'state':p['state'],'publishDate':p['publishDate'],
      'settings':(json.loads(p['settings']) if isinstance(p.get('settings'),str) else p.get('settings'))} for p in mine]
json.dump(res,open('out/result.json','w'),indent=1); print(json.dumps(res,indent=1))
PY
fi

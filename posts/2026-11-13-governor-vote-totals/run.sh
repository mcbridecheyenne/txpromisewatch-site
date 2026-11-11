#!/usr/bin/env bash
# One-off post pipeline, run by .github/workflows/one-off-post.yml on pushes to post/** branches.
# Media (graphic.png, reel_facebook.mp4, reel_tiktok.mp4) is built in the session and committed in media/.
# stage=verify  -> list the Postiz queue
# stage=publish -> upload media and schedule FB / X / TikTok at publish_at.txt, record ids
set -euo pipefail
cd "$(dirname "$0")"
STAGE=$(tr -d '[:space:]' < stage)
json() { sed -n '/^[[{]/,$p'; }
mkdir -p out
if [ "$STAGE" = verify ]; then
  postiz posts:list --startDate "$(date -u +%Y-%m-%dT00:00:00Z)" --endDate "$(date -u -d '+4 days' +%Y-%m-%dT00:00:00Z)" | json > out/plist.json
  python3 - <<'PY'
import json
d=json.load(open('out/plist.json')); d=d['posts'] if isinstance(d,dict) else d
with open('out/queue.txt','w') as f:
    for p in sorted(d,key=lambda p:p['publishDate']):
        f.write(f"{p['publishDate']} {p['state']} {p['integration']['providerIdentifier']} {p['content'][:70]!r}\n")
PY
  cat out/queue.txt
elif [ "$STAGE" = publish ]; then
  test -f out/result.json && { echo "Already published"; cat out/result.json; exit 0; }
  WHEN=$(tr -d '[:space:]' < publish_at.txt)
  # never double-book a slot: stop if anything is already queued at WHEN
  postiz posts:list --startDate "$(date -u -d "$WHEN -1 minute" +%Y-%m-%dT%H:%M:%SZ)" --endDate "$(date -u -d "$WHEN +1 minute" +%Y-%m-%dT%H:%M:%SZ)" | json > out/before.json
  python3 -c "import json;d=json.load(open('out/before.json'));d=d['posts'] if isinstance(d,dict) else d;print(len(d),'posts already at slot');exit(1 if d else 0)" || { echo "Slot taken, not publishing"; exit 1; }
  up() { postiz upload "$1" | json | python3 -c "import json,sys;print(json.load(sys.stdin)['path'])"; }
  PNG=$(up media/graphic.png); FBMP4=$(up media/reel_facebook.mp4); TTMP4=$(up media/reel_tiktok.mp4)
  echo "uploaded: $PNG $FBMP4 $TTMP4"
  TITLE=$(cat tiktok_title.txt)
  FBSET=$(python3 -c "import json,sys;print(json.dumps({'post_type':'post','title':sys.argv[1]}))" "$TITLE")
  TTSET=$(python3 -c "
import json,sys
m=json.load(open('../../tiktok_music.json')); t=[x for x in m['tracks'] if x['id']==sys.argv[2]][0]
print(json.dumps({'title':sys.argv[1],'privacy_level':'PUBLIC_TO_EVERYONE','duet':False,'stitch':False,'comment':True,
 'autoAddMusic':'no','brand_content_toggle':False,'brand_organic_toggle':False,'video_made_with_ai':False,
 'content_posting_method':'DIRECT_POST','music':{**t,'audio_volume':m['audio_volume'],'video_volume':m['video_volume']}}))" "$TITLE" "$(tr -d '[:space:]' < tiktok_music_id.txt)")
  : > out/create.log
  postiz posts:create -c "$(cat facebook.txt)" -m "$FBMP4" -c "$(cat first_comment.txt)" -s "$WHEN" --settings "$FBSET" -i cmw1op4mp0cztla07zr8ski3z | tee -a out/create.log
  postiz posts:create -c "$(cat x.txt)" -m "$PNG" -s "$WHEN" --settings '{"post_type":"post","who_can_reply_post":"everyone"}' -i cmw1pgg8k0drqla078ivel5jr | tee -a out/create.log
  if postiz integrations:list | json | python3 -c "import json,sys;sys.exit(0 if any(i['id']=='cmw21kbr201nrl808vqs2hovq' and not i.get('disabled') for i in json.load(sys.stdin)) else 1)"; then
    postiz posts:create -c "$(cat tiktok.txt)" -m "$TTMP4" -s "$WHEN" --settings "$TTSET" -i cmw21kbr201nrl808vqs2hovq | tee -a out/create.log
  else echo "TikTok integration missing, skipped" | tee -a out/create.log; fi
  sleep 5
  postiz posts:list --startDate "$(date -u -d "$WHEN -1 hour" +%Y-%m-%dT%H:%M:%SZ)" --endDate "$(date -u -d "$WHEN +1 hour" +%Y-%m-%dT%H:%M:%SZ)" | json > out/after.json
  python3 - "$WHEN" <<'PY'
import json,sys
d=json.load(open('out/after.json')); d=d['posts'] if isinstance(d,dict) else d
mine=[p for p in d if p['publishDate'].startswith(sys.argv[1][:16]) and '1.7 million' in p['content'].lower()]
res=[{'id':p['id'],'platform':p['integration']['providerIdentifier'],'state':p['state'],'publishDate':p['publishDate'],
      'settings':(json.loads(p['settings']) if isinstance(p.get('settings'),str) else p.get('settings'))} for p in mine]
json.dump(res,open('out/result.json','w'),indent=1); print(json.dumps(res,indent=1))
PY
fi

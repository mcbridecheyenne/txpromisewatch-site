TT=cmw21kbr201nrl808vqs2hovq
for g in CINEMATIC AMBIENT CORPORATE ELECTRONIC POP HIPHOP; do
  echo "== genre $g"
  postiz integrations:trigger $TT musicSearch -d "{\"genre\":\"$g\"}" 2>&1 | sed -n '/^[[{]/,$p' | jq -r '.output[:12][]? | "\(.id) | \(.title) | \(.artist) | \(.duration)"' 
done

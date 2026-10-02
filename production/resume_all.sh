#!/bin/bash
# Relance sans doublon les productions de $STUDIO_WORK/active.txt (après un redémarrage de la machine).
# active.txt : une ligne par vidéo, « dossier [options de pipeline.py] », dossier relatif à $STUDIO_WORK.
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${STUDIO_WORK:-$(dirname "$HERE")/work}"
alive() { for p in /proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null); [[ "$c" == *"pipeline.py $1"* || "$c" == *"history_video.py run $1"* ]] && return 0; done; return 1; }
while read -r d opts; do
  [ -z "$d" ] && continue
  D="$WORK/$d"
  grep -q "ALL DONE" "$D/pipeline.log" 2>/dev/null && continue
  alive "$D" && continue
  if [ -f "$D/history" ]; then  # vidéo History Docs (production/history_video.py)
    (setsid nohup python3 "$HERE/history_video.py" run "$D" >> "$D/pipeline.out" 2>&1 < /dev/null &)
  else
    (setsid nohup python3 "$HERE/pipeline.py" "$D" $opts >> "$D/pipeline.out" 2>&1 < /dev/null &)
  fi
  echo "relancé $d"
done < "$WORK/active.txt"

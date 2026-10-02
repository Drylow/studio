#!/bin/bash
# Superviseur : relance les productions arrêtées chaque minute, s'arrête quand tout est livré.
# À lancer en tâche de fond suivie (Claude Code : Bash run_in_background) : si la machine redémarre,
# la fin de la tâche réveille la session, qui relance resume_all.sh puis le superviseur.
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${STUDIO_WORK:-$(dirname "$HERE")/work}"
while true; do
  "$HERE/resume_all.sh"
  left=0
  while read -r d opts; do [ -z "$d" ] && continue; grep -q "ALL DONE" "$WORK/$d/pipeline.log" 2>/dev/null || left=$((left+1)); done < "$WORK/active.txt"
  echo "$(date -u +%H:%M) productions en cours : $left"
  [ $left -eq 0 ] && exit 0
  sleep 60
done

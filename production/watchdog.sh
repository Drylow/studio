#!/bin/bash
# Surveillance toutes les 10 min (l'utilisateur, 31 oct. : « tu vérifies de toi-même que tout tourne ») :
# garde le superviseur en vie (détaché, il survit à la fin de la tâche) et SORT dès qu'il faut un humain
# (la fin de la tâche de fond réveille la session Claude) : production bloquée (log figé 20 min), attente
# de relecture (script_ok / review_ok), livraison (ALL DONE), erreur répétée. Lancer en tâche de fond suivie.
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${STUDIO_WORK:-$(dirname "$HERE")/work}"
STATE="$WORK/watchdog.state"
touch "$STATE"
# Sort de lui-même avant la limite de 2 h d'une tâche de fond (CYCLE) : la session est réveillée et le relance.
END=$(( $(date +%s) + ${WATCHDOG_MAX:-6000} ))
while true; do
  [ $(date +%s) -gt $END ] && { echo "CYCLE : relancer le surveillant"; exit 0; }
  "$HERE/resume_all.sh"
  if ! pgrep -f "production/supervisor.sh" >/dev/null; then
    (setsid nohup "$HERE/supervisor.sh" >> "$WORK/supervisor.out" 2>&1 < /dev/null &)
    echo "$(date +%H:%M) superviseur relancé"
  fi
  now=$(date +%s)
  while read -r d opts; do
    [ -z "$d" ] && continue
    f="$WORK/$d"
    grep -q "ALL DONE" "$f/pipeline.log" 2>/dev/null && { grep -qx "done $d" "$STATE" || { echo "done $d" >> "$STATE"; echo "LIVRÉ : $d"; exit 0; }; continue; }
    last=$(tail -1 "$f/pipeline.log" 2>/dev/null)
    if echo "$last" | grep -q "attente du fichier"; then
      key="wait $d $(echo "$last" | grep -o '[a-z_]*$')"
      grep -qxF "$key" "$STATE" || { echo "$key" >> "$STATE"; echo "ATTENTE : $d : $last"; exit 0; }
      continue
    fi
    newest=$(ls -t "$f"/*.log 2>/dev/null | head -1)
    [ -n "$newest" ] || continue
    age=$(( now - $(stat -c %Y "$newest") ))
    if [ $age -gt 1200 ]; then echo "BLOQUÉ : $d ($(basename "$newest") figé depuis $((age/60)) min)"; exit 0; fi
  done < "$WORK/active.txt"
  echo "$(date +%H:%M) ok"
  sleep 300
done

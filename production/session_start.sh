#!/bin/bash
# Début de session Claude dans le cloud (à lancer : bash production/session_start.sh) : rend la session prête
# comme sur le compte d'origine. Rien sur le PC de l'utilisateur.
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
cd "$(dirname "$0")/.." || exit 0
# hook git : chaque commit poussé sur la branche ET main
if [ -f production/git-post-commit ] && ! cmp -s production/git-post-commit .git/hooks/post-commit; then
  cp production/git-post-commit .git/hooks/post-commit && chmod +x .git/hooks/post-commit
fi
# .env (secrets, jamais dans git) recréé depuis les variables d'environnement du compte s'il manque
if [ ! -f .env ]; then
  printenv | grep -E '^(FLASK_ENV|COOKIE_SECURE|FLASK_SECRET_KEY|ACCESS_PASSWORD|BOSS_PASSWORD|AI_BASE_URL|AI_API_KEY|AI_TEXT_MODEL|AI_FAST_MODEL|AI_IMAGE_MODEL|AI_IMAGE_CONCURRENCY|ALGROW_API_KEY|DISCORD_WEBHOOK_URL|NEWS_WORKER_URL|NEWS_WORKER_TOKEN|AI33_API_KEY|RUNPOD_[A-Z_]*|RENDER_WORKERS|RENDER_WORKER_TOKEN)=' > .env.tmp
  if [ -s .env.tmp ]; then mv .env.tmp .env; echo "Drylow : .env recréé depuis l'environnement ($(wc -l < .env) variables)."
  else rm -f .env.tmp; echo "Drylow : pas de .env ni de variables d'environnement (voir production/REPRISE.md §1)."; fi
fi
exit 0

# Drylow Studio - Amélioration UI ZIP Button

## 📋 Plan (1 étape)

**Objectif**: Bouton ZIP toujours visible en bas génération visuels (scènes + audio).

**Fichiers**:
- static/js/visuals.js (modifier initVisualsStep())
- templates/video_creator.html (bar déjà OK)

**Changements**:
1. initVisualsStep(): `bottomBar.classList.add("visible")` dès scenes.length > 0
2. Condition disable si !audioUrl || !scenes avec images

**Tests**:
- Step4 → VO + scenes → bar visible
- Clique ZIP → download OK

**Updated**: $(date)

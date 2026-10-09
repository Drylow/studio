// The editor, renderer and backend share the same frame-accurate timeline.
export const RATINGS = {
  brilliant: {label: 'Brilliant', color: '#1baca6', symbol: '!!'},
  great: {label: 'Great', color: '#5c8bb0', symbol: '!'},
  best: {label: 'Best', color: '#96bc4b', symbol: '★'},
  excellent: {label: 'Excellent', color: '#96bc4b', symbol: '↑'},
  good: {label: 'Good', color: '#95b776', symbol: '✓'},
  book: {label: 'Book move', color: '#a88865', symbol: '▤'},
  inaccuracy: {label: 'Inaccuracy', color: '#f7c045', symbol: '?!'},
  mistake: {label: 'Mistake', color: '#e58f2a', symbol: '?'},
  miss: {label: 'Miss', color: '#ff7769', symbol: '×'},
  blunder: {label: 'Blunder', color: '#fa412d', symbol: '??'},
};
export const PROFILES = {
  animation: {name: 'Films d’animation', label: 'ANIMATED · GAME REVIEW', accent: '#70c6c0'},
  thrones: {name: 'Game of Thrones', label: 'WESTEROS · GAME REVIEW', accent: '#c9ac73'},
};
export function newProject(profile = 'animation', title = 'Nouvelle analyse') {
  return {version: 1, profile, title, fps: 30, resolution: 1080, initialScore: 0,
    iconSet: 'chesscom', sfx: true,showPawn:false,
    players: [{name: 'Blancs', portrait: ''}, {name: 'Noirs', portrait: ''}], shots: []};
}
const fail = (message) => {throw new Error(message);};
export function validateProject(p, media = {}) {
  if (!p || p.version !== 1) fail('Version de projet inconnue.');
  if (!PROFILES[p.profile]) fail('Choisir une chaîne.');
  if (typeof p.title !== 'string' || !p.title.trim() || p.title.length > 160) fail('Titre requis, 160 caractères maximum.');
  if (![24, 25, 30, 50, 60].includes(p.fps)) fail('Cadence invalide.');
  if (![1080, 2160].includes(p.resolution)) fail('Export : 1080p ou 4K.');
  if (!Number.isFinite(p.initialScore) || Math.abs(p.initialScore) > 10) fail('Score initial : de −10 à +10.');
  if (!['chesscom', 'notation'].includes(p.iconSet) || typeof p.sfx !== 'boolean') fail('Habillage invalide.');
  if (p.showPawn!==undefined && typeof p.showPawn!=='boolean') fail('Option de pion invalide.');
  if (!Array.isArray(p.players) || p.players.length !== 2) fail('Deux personnages requis.');
  for (const player of p.players) {
    if (typeof player.name !== 'string' || !player.name.trim() || player.name.length > 36) fail('Nom de personnage requis, 36 caractères maximum.');
    if (typeof player.portrait !== 'string' || (player.portrait && !/^portraits\/[a-f0-9-]+\.png$/.test(player.portrait))) fail('Portrait invalide.');
  }
  if (!Array.isArray(p.shots) || p.shots.length > 150) fail('150 extraits maximum.');
  const ids = new Set();
  for (const shot of p.shots) {
    if (typeof shot.id !== 'string' || !/^[a-zA-Z0-9-]+$/.test(shot.id) || ids.has(shot.id)) fail('Identifiant d’extrait invalide ou dupliqué.');
    ids.add(shot.id);
    const m = media[shot.mediaId];
    if (!m) fail('Un clip de ce projet est introuvable.');
    if (!Number.isFinite(shot.in) || !Number.isFinite(shot.out) || shot.in < 0 || shot.out > m.duration + 0.001 || Math.round(shot.out * p.fps) <= Math.round(shot.in * p.fps)) fail('Les points d’entrée et de sortie doivent être dans le clip.');
    if (!Number.isFinite(shot.volume) || shot.volume < 0 || shot.volume > 1) fail('Volume : de 0 à 1.');
    if (!Array.isArray(shot.moves) || shot.moves.length > 100) fail('100 coups maximum par extrait.');
    let last = -1;
    for (const move of shot.moves) {
      if (typeof move.id !== 'string' || !/^[a-zA-Z0-9-]+$/.test(move.id) || ids.has(move.id)) fail('Identifiant de coup invalide ou dupliqué.');
      ids.add(move.id);
      const at = Math.round(move.at * p.fps);
      if (!Number.isFinite(move.at) || at < Math.round(shot.in*p.fps) || at >= Math.round(shot.out*p.fps) || at <= last) fail('Les coups doivent être ordonnés, distincts et dans l’extrait.');
      last = at;
      if (!RATINGS[move.rating] || ![0, 1].includes(move.player)) fail('Note ou personnage invalide.');
      if (!Number.isFinite(move.hold) || move.hold < 1 || move.hold > 20) fail('Pause : de 1 à 20 secondes.');
      if (!Number.isFinite(move.score) || Math.abs(move.score) > 10) fail('Évaluation : de −10 à +10.');
      if (!Number.isFinite(move.zoom) || move.zoom < 1 || move.zoom > 1.12) fail('Zoom : de 1 à 1,12.');
      if (!['left', 'right'].includes(move.placement)) fail('Position de carte invalide.');
      if (typeof move.title !== 'string' || move.title.length > 60 || !move.title.trim()) fail('Nom du coup requis, 60 caractères maximum.');
      if (typeof move.comment !== 'string' || move.comment.length > 240 || !move.comment.trim()) fail('Analyse requise, 240 caractères maximum.');
      if (typeof move.quote !== 'string' || move.quote.length > 180) fail('Citation : 180 caractères maximum.');
      for(const key of ['cardX','cardY','cardWidth','iconX','iconY'])if(move[key]!==undefined && (!Number.isFinite(move[key]) || move[key]<0 || move[key]>100))fail('Placement : de 0 à 100 %.');
      if(move.cardWidth!==undefined && (move.cardWidth<20 || move.cardWidth>45))fail('Largeur de carte : de 20 à 45 %.');
      for(const key of ['tags','betterMove'])if(move[key]!==undefined && (typeof move[key]!=='string' || move[key].length>120))fail('Indication : 120 caractères maximum.');
    }
  }
  return p;
}
export function buildTimeline(project) {
  const segments = []; let cursor = 0; let score = project.initialScore;
  const fps = project.fps;
  for (const shot of project.shots) {
    let source = Math.round(shot.in * fps);
    const out = Math.round(shot.out * fps);
    for (const move of shot.moves) {
      const at = Math.round(move.at * fps);
      if (at > source) {
        segments.push({kind: 'play', shotId: shot.id, mediaId: shot.mediaId, from: cursor, duration: at-source, sourceFrame: source, volume: shot.volume, score});
        cursor += at-source;
      }
      const duration = Math.round(move.hold * fps);
      segments.push({kind: 'hold', shotId: shot.id, mediaId: shot.mediaId, from: cursor, duration,
        sourceFrame: Math.max(Math.round(shot.in * fps), at-1), volume: 0, score: move.score, previousScore: score, move});
      cursor += duration; score = move.score; source = at;
    }
    if (out > source) {
      segments.push({kind: 'play', shotId: shot.id, mediaId: shot.mediaId, from: cursor, duration: out-source, sourceFrame: source, volume: shot.volume, score});
      cursor += out-source;
    }
  }
  return {segments, durationInFrames: Math.max(1, cursor)};
}
export function timecode(seconds) {
  const t = Math.max(0, Number(seconds) || 0);
  return `${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(2).padStart(5,'0')}`;
}

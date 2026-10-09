// A filename or a contact sheet cannot prove that an entire source is clean.
// Approval records an actual viewing; newly imported files stay pending.
export function sourceReview(media) {
  return media.review || {status:'pending',notes:'Source à regarder : vérifier tout le clip, y compris les coins.'};
}
export function setSourceReview(media, input) {
  if(!['approved','rejected','pending'].includes(input.status))throw new Error('Statut de source invalide.');
  if(input.status==='approved' && /fandango|movieclips/i.test(`${media.name} ${media.uploader || ''}`))
    throw new Error('Les sources Fandango / Movieclips sont exclues. Importer une autre source.');
  if(input.status==='approved' && (input.noLogo!==true || input.noText!==true || input.watchedEntirely!==true))
    throw new Error('Regarder le clip entier et vérifier l’absence de logo et de texte incrusté.');
  return {status:input.status,noLogo:input.noLogo===true,noText:input.noText===true,watchedEntirely:input.watchedEntirely===true,
    notes:String(input.notes || '').slice(0,500),checkedAt:new Date().toISOString()};
}
export function assertCleanSources(project, media) {
  for(const id of new Set(project.shots.map(s=>s.mediaId))){
    const m=media[id];const review=m && sourceReview(m);
    if(!m || review.status!=='approved' || !review.noLogo || !review.noText || !review.watchedEntirely)
      throw new Error(`Source non validée : ${m?.name || id}. Utiliser un clip regardé en entier, sans logo ni texte incrusté.`);
  }
}

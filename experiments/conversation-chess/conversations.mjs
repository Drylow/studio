// Optional independent conversation scopes. No option leaves legacy rendering alone.
const aligned = t => Number.isFinite(t) && Math.abs(t * 30 - Math.round(t * 30)) < 1e-6;
const validLabel = v => typeof v === 'string' && v.trim().length > 0 && v.length <= 32;

export function validateConversations(spec, start = Number(spec.source_in), end = Number(spec.source_out)) {
  if (spec.conversations == null) return null;
  if (!Array.isArray(spec.conversations) || !spec.conversations.length) throw new Error('conversations must be a nonempty ordered array.');
  if (![start, end].every(aligned) || end <= start) throw new Error('Conversation clip bounds must align to 30fps.');
  let previous = -Infinity;
  const conversations = spec.conversations.map((c, i) => {
    if (!c || typeof c !== 'object' || Array.isArray(c) || !aligned(c.source_at)
        || c.source_at < start || c.source_at >= end || c.source_at <= previous) throw new Error('Conversation starts must be strictly ordered, inside the clip and aligned to 30fps.');
    if (!validLabel(c.white_label) || !validLabel(c.black_label) || c.white_label === c.black_label) throw new Error('Each conversation needs distinct short White/Black labels.');
    if (c.opening?.speaker !== 'white' || c.opening?.label !== c.white_label || c.opening?.reviewed !== true
        || typeof c.opening?.evidence !== 'string' || !c.opening.evidence.trim()) throw new Error('Every conversation needs its own reviewed White-first opening evidence.');
    if (c.opening.source_at != null && c.opening.source_at !== c.source_at) throw new Error('Conversation opening.source_at must equal its chapter start when provided.');
    if (c.initial_score_text !== '0.0' || c.initial_control !== .5) throw new Error('Every new conversation starts at score 0.0 and balanced control 0.5.');
    if (i === 0 && (c.source_at !== start || c.white_label !== spec.white_label || c.black_label !== spec.black_label
        || spec.opening?.speaker !== 'white' || spec.opening?.label !== c.white_label || spec.opening?.reviewed !== true
        || spec.initial_score_text !== c.initial_score_text || (spec.initial_control ?? .5) !== c.initial_control)) throw new Error('First conversation must agree with global camps, opening, initial state and source_in.');
    previous = c.source_at;
    return { ...c, opening: { ...c.opening }, index: i, sides: { white: c.white_label, black: c.black_label } };
  });
  return conversations;
}

export function conversationAt(conversations, sourceAt) {
  let result = null;
  for (const c of conversations) {
    if (sourceAt < c.source_at) break;
    result = c;
  }
  if (!result) throw new Error('Source position has no conversation scope.');
  return result;
}

export function annotationContexts(annotations, conversations) {
  if (!conversations) return null;
  let index = -1, control, score;
  return annotations.map(a => {
    if (!Number.isFinite(a.source_at)) throw new Error('Annotation source_at must be finite.');
    const c = conversationAt(conversations, a.source_at);
    if (a.source_at === c.source_at) throw new Error('A grade exactly at a conversation start is ambiguous; place it after the reviewed first dialogue.');
    if (c.index !== index) {
      index = c.index; control = c.initial_control; score = c.initial_score_text;
    }
    const result = { conversation_index: index, sides: c.sides, source_in: c.source_at,
      previous_control: control, previous_score_text: score };
    control = a.control_after; score = a.score_text;
    return result;
  });
}

export function sourceSpans(from, until, conversations, annotations = [], labelsSeconds = 3) {
  if (!Number.isFinite(from) || !Number.isFinite(until) || until < from) throw new Error('Invalid source interval.');
  if (until === from) return [];
  const labelEnds = conversations.map((c, index) => {
    const next = conversations[index + 1]?.source_at ?? Infinity;
    const firstGrade = annotations.find(a => a.source_at > c.source_at && a.source_at < next)?.source_at ?? Infinity;
    return Math.min(c.source_at + labelsSeconds, next, firstGrade);
  });
  const points = [...new Set([from, until, ...conversations.map(c => c.source_at), ...labelEnds])]
    .filter(t => t >= from && t <= until).sort((a, b) => a - b);
  return points.slice(0, -1).map((source_in, i) => {
    const c = conversationAt(conversations, source_in);
    return { source_in, source_out: points[i + 1], conversation_index: c.index,
      sides: c.sides, starts_conversation: source_in === c.source_at,
      show_sides: source_in < labelEnds[c.index] };
  });
}

export function sourceAudioFades(span, index, spans, conversations, endingFadeSeconds = 0) {
  const nextConversation = conversations[span.conversation_index + 1]?.source_at;
  return {
    fade_in_seconds: index === 0 || span.starts_conversation ? .035 : 0,
    fade_out_seconds: index === spans.length - 1 ? (endingFadeSeconds || .035)
      : span.source_out === nextConversation ? .035 : 0,
  };
}

export function dialogueAudioFilter(duration, gain = 1, fadeIn = .035, fadeOut = .035) {
  const filters = [`aresample=48000`, `volume=${gain}`, 'apad'];
  if (fadeIn) filters.push(`afade=t=in:st=0:d=${fadeIn}`);
  if (fadeOut) filters.push(`afade=t=out:st=${Math.max(0,duration-fadeOut)}:d=${fadeOut}`);
  filters.push(`atrim=end_sample=${Math.round(duration*48000)}`);
  return filters.join(',');
}

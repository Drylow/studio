import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

// Credit the recordings actually present in the project, including a retained
// outro when only the intro is refreshed. No attribution is drawn over the film.
export async function writeMusicCredits(segments, directory) {
  const hashes = [...new Set(segments.filter(s => s.music_file).map(s => s.music_source_sha256))];
  if (!hashes.length) return null;
  const manifest = JSON.parse(await fs.readFile(new URL('./assets/music/manifest.json', import.meta.url), 'utf8'));
  const tracks = hashes.map(hash => {
    const track = manifest.tracks.find(t => t.sha256 === hash);
    if (!track?.required_attribution || !track.creator_page) throw new Error('Music source needs verified attribution in assets/music/manifest.json.');
    return track;
  });
  const text = tracks.map(t => `${t.required_attribution}\nSource: ${t.creator_page}`).join('\n\n')
    + '\n\nMusic excerpts have been trimmed, mixed at adjusted volume and faded in/out.\n';
  const file = path.join(directory, 'MUSIC_CREDITS.txt');
  await fs.writeFile(file, text, 'utf8');
  return {
    placement: 'youtube-description-and-delivery-sidecar', file,
    sha256: createHash('sha256').update(text).digest('hex'),
    tracks: tracks.map(t => ({title:t.title, composer:t.composer, source:t.creator_page, license:t.license, license_url:t.license_url})),
  };
}

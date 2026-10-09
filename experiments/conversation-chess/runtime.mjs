// Platform paths only: the existing graphics and timing stay in their original files.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

export function mediaBinary(name) {
  return process.env[`CHESS_${name.toUpperCase()}`]
    || (fs.existsSync(`/usr/bin/${name}`) ? `/usr/bin/${name}` : name);
}

export function loadChromium() {
  const local = createRequire(import.meta.url);
  try { return local('playwright').chromium; }
  catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
    // Preserve the original Linux installation's dependency location.
    const frontend = createRequire(new URL('../../frontend/package.json', import.meta.url));
    try { return frontend('playwright').chromium; }
    catch { throw new Error('Install dependencies: npm ci --prefix experiments/conversation-chess'); }
  }
}

export function browserOptions(explicitPath) {
  const executablePath = explicitPath || process.env.CHESS_CHROMIUM
    || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  return { ...(executablePath ? { executablePath: path.resolve(executablePath) } : {}),
    headless: true, args: ['--disable-dev-shm-usage'] };
}

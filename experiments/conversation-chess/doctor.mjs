import { loadChromium, browserOptions } from './runtime.mjs';
const browser = await loadChromium().launch(browserOptions());
console.log('Navigateur : OK');
await browser.close();

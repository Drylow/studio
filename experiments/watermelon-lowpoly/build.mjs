import {execFileSync} from 'node:child_process';
import {copyFileSync,mkdirSync} from 'node:fs';
import {build} from 'esbuild';
mkdirSync('assets',{recursive:true});
execFileSync(process.execPath,['build-simulation.mjs'],{stdio:'inherit'});
execFileSync(process.platform==='win32'?'python':'python3',['sound.py'],{stdio:'inherit'});
copyFileSync('node_modules/gsap/dist/gsap.min.js','assets/gsap.min.js');
await build({entryPoints:['scene.mjs'],bundle:true,minify:true,format:'iife',outfile:'assets/scene.js'});
console.log('Offline composition ready.');

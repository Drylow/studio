import {build} from 'esbuild';
import {execFileSync} from 'node:child_process';
import {copyFileSync} from 'node:fs';
execFileSync(process.execPath,['build-piles.mjs'],{stdio:'inherit'});
execFileSync('python',['sound.py'],{stdio:'inherit'});
copyFileSync('node_modules/gsap/dist/gsap.min.js','assets/gsap.min.js');
await build({entryPoints:['scene.mjs'],bundle:true,minify:true,format:'iife',outfile:'assets/scene.js'});

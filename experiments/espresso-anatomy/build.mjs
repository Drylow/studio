import {build} from 'esbuild';
import {copyFile} from 'node:fs/promises';
await copyFile('index-v3.html.source','index.html');
await build({entryPoints:['scene-v3.js'],bundle:true,minify:true,format:'iife',outfile:'dist/scene.js'});

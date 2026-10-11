import {build} from 'esbuild';
await build({entryPoints:['scene.js'],bundle:true,minify:true,format:'iife',outfile:'dist/scene.js'});

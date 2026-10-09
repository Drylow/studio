import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceReview,setSourceReview,assertCleanSources} from '../quality.mjs';
test('an unreviewed or rejected source never passes the export gate',()=>{
  const p={shots:[{mediaId:'clip'}]};
  assert.equal(sourceReview({}).status,'pending');
  for(const m of [{name:'New clip'},{name:'Marked clip',review:{status:'rejected'}},{name:'False approval',review:{status:'approved'}}])
    assert.throws(()=>assertCleanSources(p,{clip:m}));
});
test('approval needs all three visual checks; Fandango stays excluded',()=>{
  const clean={status:'approved',noText:true,noLogo:true,watchedEntirely:true};
  for(const key of ['noText','noLogo','watchedEntirely'])assert.throws(()=>setSourceReview({name:'Clean clip'},{...clean,[key]:false}));
  assert.throws(()=>setSourceReview({name:'Tai Lung | Movieclips'},clean));
  const m={name:'Clean clip',review:setSourceReview({name:'Clean clip'},clean)};
  assert.doesNotThrow(()=>assertCleanSources({shots:[{mediaId:'clip'},{mediaId:'clip'}]},{clip:m}));
});
test('export gate examines only the selected sources and refuses a mixed montage',()=>{
  const clip={name:'Clean',review:setSourceReview({name:'Clean'},{status:'approved',noText:true,noLogo:true,watchedEntirely:true})};
  const media={clip,bad:{name:'Logo',review:{status:'rejected'}}};
  assert.doesNotThrow(()=>assertCleanSources({shots:[{mediaId:'clip'}]},media));
  assert.throws(()=>assertCleanSources({shots:[{mediaId:'clip'},{mediaId:'bad'}]},media));
});

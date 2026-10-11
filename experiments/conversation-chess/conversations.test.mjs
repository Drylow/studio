import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { validateConversations, conversationAt, annotationContexts, sourceSpans, sourceAudioFades, dialogueAudioFilter } from './conversations.mjs';

function fixture() {
  const chapter = (source_at, white_label, black_label) => ({ source_at, white_label, black_label,
    opening: {speaker:'white',label:white_label,reviewed:true,evidence:'Reviewed first retained line.'},
    initial_score_text:'0.0',initial_control:.5 });
  return {source_in:0,source_out:30,white_label:'LaPadite',black_label:'Landa',
    opening:{speaker:'white',label:'LaPadite',reviewed:true},initial_score_text:'0.0',initial_control:.5,
    conversations:[chapter(0,'LaPadite','Landa'),chapter(10,'Landa','Shosanna')]};
}

test('default has no scope and leaves the original initial state alone', () => {
  const spec = {source_in:1,source_out:10,initial_score_text:'2.0'};
  assert.equal(validateConversations(spec), null);
  assert.equal(annotationContexts([], null), null);
  assert.deepEqual(spec, {source_in:1,source_out:10,initial_score_text:'2.0'});
});

test('a conversation boundary changes camps and resets the preceding analysis score', () => {
  const scopes = validateConversations(fixture());
  const annotations = [{source_at:6,control_after:.7,score_text:'-3.0'},
    {source_at:11,control_after:.4,score_text:'1.2'},{source_at:18,control_after:.4,score_text:'1.2'}];
  const contexts = annotationContexts(annotations, scopes);
  assert.equal(conversationAt(scopes, 10).sides.white, 'Landa');
  assert.equal(conversationAt(scopes, 9.999).sides.white, 'LaPadite');
  assert.deepEqual(contexts.map(c => c.previous_score_text), ['0.0','0.0','1.2']);
  assert.deepEqual(contexts.map(c => c.previous_control), [.5,.5,.4]);
  assert.equal(contexts[1].source_in, 10);
  assert.deepEqual(contexts[1].sides, {white:'Landa',black:'Shosanna'});
  assert.equal(annotations.length, 3); // Chapter transitions add no counted grade.
});

test('native source spans split at chapter start and label expiry with no added duration', () => {
  const scopes = validateConversations(fixture());
  const spans = sourceSpans(7, 20, scopes, [{source_at:15}]);
  assert.deepEqual(spans.map(s => [s.source_in,s.source_out,s.conversation_index,s.show_sides]),
    [[7,10,0,false],[10,13,1,true],[13,20,1,false]]);
  assert.equal(spans.reduce((sum,s) => sum+s.source_out-s.source_in,0), 13);
  assert.equal(spans[1].starts_conversation, true);
});

test('labels end at the first grade and do not reappear with a stale zero score', () => {
  const scopes = validateConversations(fixture());
  const annotations = [{source_at:11,control_after:.4,score_text:'1.2'}];
  assert.deepEqual(sourceSpans(10,11,scopes,annotations).map(s => s.show_sides), [true]);
  assert.deepEqual(sourceSpans(11,14,scopes,annotations).map(s => s.show_sides), [false]);
});

test('independent scopes require White-first evidence, zero score and coherent first camps', () => {
  for (const change of [c => c.opening.evidence='',c => c.opening.speaker='black',
    c => c.initial_score_text='1.0',c => c.initial_control=.7,c => c.white_label='Landa']) {
    const spec=fixture();change(spec.conversations[0]);
    assert.throws(() => validateConversations(spec));
  }
  const bad=fixture();bad.conversations[1].source_at=10.01;
  assert.throws(() => validateConversations(bad), /aligned/);
});

test('a grade at a chapter boundary is rejected rather than silently changing its player', () => {
  assert.throws(() => annotationContexts([{source_at:10}],validateConversations(fixture())), /ambiguous/);
});

test('default dialogue filter stays exactly the original command', () => {
  assert.equal(dialogueAudioFilter(5, 1), 'aresample=48000,volume=1,apad,afade=t=in:st=0:d=0.035,afade=t=out:st=4.965:d=0.035,atrim=end_sample=240000');
});

test('the label-only split retains every source PCM sample around its junction', async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'conversation-pcm-'));
  function run(args) {
    const result=spawnSync('ffmpeg',['-v','error','-nostdin',...args],{maxBuffer:10_000_000});
    if(result.error) throw result.error;
    assert.equal(result.status,0,result.stderr.toString());return result.stdout;
  }
  try {
    const wav=path.join(directory,'continuous.wav');
    run(['-f','lavfi','-i','sine=frequency=350:sample_rate=48000:duration=4','-c:a','pcm_s16le','-ac','2',wav]);
    const expected=run(['-i',wav,'-c:a','pcm_f32le','-f','f32le','-']);
    const scopes=validateConversations(fixture());
    const spans=sourceSpans(0,4,scopes,[{source_at:6}]);
    assert.deepEqual(spans.map(s => [s.source_in,s.source_out]),[[0,3],[3,4]]);
    const parts=spans.map((span,i) => {
      const fades=sourceAudioFades(span,i,spans,scopes);
      return run(['-ss',String(span.source_in),'-i',wav,'-af',dialogueAudioFilter(span.source_out-span.source_in,1,fades.fade_in_seconds,fades.fade_out_seconds),'-c:a','pcm_f32le','-f','f32le','-']);
    });
    const actual=Buffer.concat(parts), byteStart=Math.round(2.9*48000)*8, byteEnd=Math.round(3.1*48000)*8;
    assert.equal(actual.length,expected.length);
    assert.deepEqual(actual.subarray(byteStart,byteEnd),expected.subarray(byteStart,byteEnd));
  } finally { await fs.rm(directory,{recursive:true,force:true}); }
});

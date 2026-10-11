const assert = require('node:assert/strict');
const ui = require('./workspace.js');

assert.equal(ui.escapeHtml('<script>"&'), '&lt;script&gt;&quot;&amp;');
assert.equal(ui.safeUrl('https://outside.invalid/image.png'), '');
assert.equal(ui.safeUrl('//outside.invalid/image.png'), '');
assert.equal(ui.mediaUrl('media', 'test', '../secret'), '');
assert.equal(ui.mediaUrl('media', 'test', 'refs/a b.png'), '/media/test/refs/a%20b.png');
assert.equal(ui.projectStatus({render: {file: 'final.mp4'}}).state, 'unreviewed');
assert.equal(ui.projectStatus({publication_ready: true}).state, 'verified');
assert.equal(ui.projectStatus({review_state: 'needs_correction'}).label, 'À corriger');
assert.equal(ui.projectStatus({review_state: 'waiting_for_script'}).label, 'Texte à préparer');
const models = [{id: 'test-text'}, {id: 'test-image'}];
const profiles = [{id: 'test-profile'}];
const row = {profile_id: 'test-profile', title: 'Test', duration_minutes: 22,
  text_model: models[0].id, image_model: models[1].id};
assert.equal(ui.validateProject(row, models, profiles), row);
assert.throws(() => ui.validateProject({...row, duration_minutes: 5}, models, profiles));
assert.throws(() => ui.validateProject({...row, title: ''}, models, profiles));
assert.throws(() => ui.validateProject({...row, image_model: ''}, models, profiles));
assert.throws(() => ui.validateProject({...row, title: 'x'.repeat(241)}, models, profiles));
assert.throws(() => ui.validateScript('bad\0script'));
assert.throws(() => ui.validateScript('x'.repeat(1024 * 1024 + 1)));
assert.equal(ui.validateScript('  Exact script.\n'), '  Exact script.\n');
async function testImport() {
  const bytes = new TextEncoder().encode('  Exact imported script.\n');
  const file = {name: 'script.txt', size: bytes.length, arrayBuffer: async () => bytes.buffer};
  assert.equal(await ui.readScriptFile(file), '  Exact imported script.\n');
  assert.equal(await ui.readScriptFile({...file, name: 'script.md'}), '  Exact imported script.\n');
  await assert.rejects(ui.readScriptFile({...file, name: 'script.pdf'}));
  await assert.rejects(ui.readScriptFile({...file, size: 1024 * 1024 + 1}));
  await assert.rejects(ui.readScriptFile({...file, arrayBuffer: async () => new Uint8Array([255]).buffer}));
  console.log('22 workspace UI checks passed');
}
testImport().catch((error) => { console.error(error); process.exitCode = 1; });

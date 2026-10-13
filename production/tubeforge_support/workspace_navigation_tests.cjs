'use strict';
const assert = require('node:assert/strict');
const { createReadCache } = require('./workspace.js');

(async () => {
  let clock = 0, count = 0;
  const cache = createReadCache(async path => ({ path, request: ++count }), 15, () => clock);
  const first = await Promise.all([cache.get('/video'), cache.get('/video')]);
  assert.equal(count, 1, 'simultaneous reads share one request');
  assert.equal(first[0], first[1]);
  assert.equal(cache.peek('/video'), first[0], 'cached page can paint synchronously');
  assert.equal(await cache.get('/video'), first[0], 'switching steps reuses the video');
  await cache.get('/styles');
  assert.equal(count, 2, 'different endpoints remain separate');
  clock = 16;
  assert.notEqual(await cache.get('/video'), first[0], 'expired status is read again');
  const fresh = await cache.get('/video', true);
  assert.equal(fresh.request, 4, 'explicit refresh bypasses cached data');
  cache.clear();
  assert.equal(cache.peek('/video'), undefined, 'logout and writes remove synchronous cached payload');
  assert.equal((await cache.get('/video')).request, 5, 'writes invalidate navigation reads');

  let resolveOld, reads = 0;
  const inFlight = createReadCache(() => ++reads === 1 ? new Promise(resolve => { resolveOld = resolve; }) : Promise.resolve('new'));
  const old = inFlight.get('/project');
  await Promise.resolve();
  inFlight.clear();
  assert.equal(await inFlight.get('/project'), 'new');
  resolveOld('old');
  assert.equal(await old, 'old');
  assert.equal(await inFlight.get('/project'), 'new', 'a stale in-flight read cannot replace post-write data');

  let attempts = 0;
  const failures = createReadCache(async () => { if (++attempts === 1) throw new Error('offline'); return 'recovered'; });
  await assert.rejects(failures.get('/project'), /offline/);
  assert.equal(await failures.get('/project'), 'recovered', 'failed requests can be retried');

  let instantClock = 0, finishBackground, backgroundCalls = 0;
  const instant = createReadCache(() => ++backgroundCalls === 1 ? Promise.resolve('cached page') :
    new Promise(resolve => { finishBackground = resolve; }), 15, () => instantClock, { staleWhileRevalidate: true });
  await instant.get('/workspace');
  instantClock = 20;
  assert.equal(await instant.get('/workspace'), 'cached page', 'expired page appears without waiting for network');
  assert.equal(await instant.get('/workspace'), 'cached page', 'fast successive clicks do not await background refresh');
  assert.equal(backgroundCalls, 2);
  finishBackground('current page');
  await Promise.resolve(); await Promise.resolve();
  assert.equal(await instant.get('/workspace'), 'current page');
  console.log('Navigation cache concurrency, freshness, invalidation and error checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });

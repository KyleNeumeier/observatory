import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULTS,
  validatePreferences,
  distanceKm,
  nearbyAssets,
  createCaseSource,
  safeUrl,
  escapeHtml,
} from '../src/model.js';
test('dateline proximity and inclusive radius', () => {
  const e = { lat: 0, lon: 179.9 },
    a = { id: 'test', lat: 0, lon: -179.9 };
  const d = distanceKm(e, a);
  assert.ok(d > 22 && d < 23);
  assert.equal(nearbyAssets(e, [a], d).length, 1);
  assert.equal(nearbyAssets(e, [a], d - 0.01).length, 0);
});
test('preferences roundtrip and malformed import rejection', () => {
  assert.deepEqual(
    validatePreferences(JSON.parse(JSON.stringify(DEFAULTS))),
    DEFAULTS,
  );
  for (const bad of [
    { ...DEFAULTS, radius: Infinity },
    { ...DEFAULTS, watchlist: 'bad' },
    { ...DEFAULTS, airports: 'true' },
    { ...DEFAULTS, regions: [{ name: 'x', lon: 181, lat: 0, height: 100 }] },
  ])
    assert.throws(() => validatePreferences(bad));
});
test('source adapter follows current replay snapshot and abort signal', async () => {
  let records = [
    {
      id: 'e',
      lat: 1,
      lon: 2,
      depth_km: 3,
      magnitude: 5,
      time: 123,
      name: 'place',
    },
  ];
  const source = createCaseSource(() => records);
  assert.equal((await source.getSnapshot())[0].usgsId, 'e');
  records = [];
  assert.deepEqual(await source.getSnapshot(), []);
  const c = new AbortController();
  c.abort();
  await assert.rejects(source.getSnapshot({ signal: c.signal }));
});
test('untrusted labels and URLs cannot inject HTML or JavaScript', () => {
  assert.equal(safeUrl('javascript:alert(1)'), '#');
  assert.equal(safeUrl('https://usgs.gov/'), 'https://usgs.gov/');
  assert.equal(escapeHtml('<script>'), '&lt;script&gt;');
});

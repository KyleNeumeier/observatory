export const DEFAULTS = Object.freeze({
  version: 1,
  airports: true,
  dams: true,
  earthquakes: true,
  inspector: true,
  radius: 100,
  watchlist: [],
  regions: [],
});
export function validatePreferences(value) {
  if (!value || value.version !== 1)
    throw new Error('Unsupported preferences format');
  const out = { ...DEFAULTS };
  for (const k of ['airports', 'dams', 'earthquakes', 'inspector']) {
    if (typeof value[k] !== 'boolean')
      throw new Error(`Invalid ${k} preference`);
    out[k] = value[k];
  }
  if (!Number.isFinite(value.radius) || value.radius < 10 || value.radius > 500)
    throw new Error('Radius must be 10–500 km');
  out.radius = value.radius;
  if (
    !Array.isArray(value.watchlist) ||
    value.watchlist.length > 1000 ||
    value.watchlist.some((x) => typeof x !== 'string' || x.length > 150)
  )
    throw new Error('Invalid watchlist');
  out.watchlist = [...new Set(value.watchlist)];
  if (!Array.isArray(value.regions) || value.regions.length > 50)
    throw new Error('Invalid saved regions');
  out.regions = value.regions.map((r) => {
    if (
      typeof r.name !== 'string' ||
      !r.name.trim() ||
      r.name.length > 60 ||
      ![r.lon, r.lat, r.height].every(Number.isFinite) ||
      Math.abs(r.lon) > 180 ||
      Math.abs(r.lat) > 90 ||
      r.height < 1 ||
      r.height > 1e8
    )
      throw new Error('Invalid saved camera');
    return { name: r.name, lon: r.lon, lat: r.lat, height: r.height };
  });
  return out;
}
export function distanceKm(a, b) {
  const rad = Math.PI / 180,
    lat1 = a.lat * rad,
    lat2 = b.lat * rad;
  const h =
    Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) *
      Math.cos(lat2) *
      Math.sin(((b.lon - a.lon) * rad) / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.max(0, Math.min(1, h))));
}
export function nearbyAssets(event, assets, radius) {
  return assets
    .map((a) => ({
      ...a,
      distance_km: distanceKm(event, a),
      evidence_id: `asset:${a.id}`,
      method: 'great-circle / mean Earth radius',
      relation: 'nearby',
    }))
    .filter((a) => a.distance_km <= radius)
    .sort((a, b) => a.distance_km - b.distance_km || a.id.localeCompare(b.id));
}
export function createCaseSource(getEvents) {
  return {
    async getSnapshot({ signal } = {}) {
      signal?.throwIfAborted();
      return getEvents().map((e) => ({
        stableId: e.id,
        usgsId: e.id,
        lon: e.lon,
        lat: e.lat,
        depthKm: e.depth_km,
        mag: e.magnitude,
        place: e.name,
        time: e.time,
      }));
    },
  };
}
export function factualBriefing(event, assets) {
  return {
    mode: 'deterministic',
    statements: [
      {
        text: `Magnitude ${event.magnitude} earthquake at ${event.name}; depth ${event.depth_km} km.`,
        evidence_ids: [`event:${event.id}`],
      },
      ...assets.slice(0, 5).map((a) => ({
        text: `${a.name} (${a.kind}) is ${a.distance_km.toFixed(1)} km from the epicenter.`,
        evidence_ids: [`event:${event.id}`, a.evidence_id],
      })),
    ],
    evidence: [
      { id: `event:${event.id}`, url: event.source_url, label: event.name },
      ...assets.map((a) => ({
        id: a.evidence_id,
        url: a.source_url,
        label: a.name,
      })),
    ],
  };
}
export const escapeHtml = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ],
  );
export function safeUrl(value) {
  try {
    const u = new URL(value);
    return ['https:', 'http:'].includes(u.protocol) ? u.href : '#';
  } catch {
    return '#';
  }
}

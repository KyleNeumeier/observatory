import * as C from 'cesium';
import { createEarthquakesLayer } from '../../src/layers/earthquakes/index.js';
import {
  DEFAULTS,
  validatePreferences,
  nearbyAssets,
  createCaseSource,
  factualBriefing,
  escapeHtml as esc,
  safeUrl,
} from './model.js';
import { scatter, distribution } from './charts.js';
import './style.css';

const $ = (id) => document.getElementById(id);
const started = performance.now();
const personal = import.meta.env.DEV;
let prefs;
try {
  prefs = validatePreferences(
    JSON.parse(localStorage.getItem('observatory.preferences')),
  );
} catch {
  prefs = structuredClone(DEFAULTS);
}
let scenarios = [],
  assets = [],
  events = [],
  selected = null,
  nearby = [],
  viewer,
  quakeLayer,
  sequence,
  analysis,
  live = false,
  request = 0,
  paintRequest = 0,
  playing = null;
const date = (t) =>
  new Date(t).toISOString().slice(0, 19).replace('T', ' · ') + ' UTC';
const notice = (text) => {
  $('status').textContent = text;
};
const json = async (url) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}: ${url}`);
  return r.json();
};
function save() {
  try {
    localStorage.setItem('observatory.preferences', JSON.stringify(prefs));
  } catch {
    $('settings-status').textContent =
      'Browser storage unavailable; export preferences to keep them.';
  }
}
function visibleEvents() {
  const search = $('search').value.toLowerCase(),
    minimum = Number($('min-mag').value),
    cutoff = live
      ? Infinity
      : sequence.event.time + Number($('replay').value) * 3600000;
  return events.filter(
    (e) =>
      e.time <= cutoff &&
      e.magnitude >= minimum &&
      (e.name + ' ' + e.id).toLowerCase().includes(search),
  );
}
function visibleAssets() {
  return nearby.filter(
    (a) => prefs[a.kind === 'airport' ? 'airports' : 'dams'],
  );
}
function drawList() {
  const rows = visibleEvents();
  $('event-count').textContent = rows.length;
  $('events').innerHTML =
    rows
      .map(
        (e) =>
          `<button class="event-card ${selected?.id === e.id ? 'selected' : ''}" data-event="${esc(e.id)}"><span class="mag">${e.magnitude.toFixed(1)}</span><span><strong>${esc(e.name)}</strong><small>${new Date(e.time).toISOString().slice(0, 16).replace('T', ' · ')} UTC</small></span></button>`,
      )
      .join('') || '<p class="empty">No events match this time and filter.</p>';
  $('events')
    .querySelectorAll('[data-event]')
    .forEach(
      (b) =>
        (b.onclick = () =>
          selectEvent(events.find((e) => e.id === b.dataset.event))),
    );
}
function drawAssets() {
  const rows = visibleAssets();
  $('nearby-count').textContent = rows.length;
  $('assets').innerHTML =
    rows
      .map(
        (a) =>
          `<div class="asset-row"><span class="asset-icon" style="color:${a.kind === 'dam' ? '#d9b871' : '#70c9db'}">${a.kind === 'dam' ? '▰' : '✈'}</span><div class="asset-title"><a href="${esc(safeUrl(a.source_url))}" target="_blank" rel="noopener noreferrer">${esc(a.name)} ↗</a><small>${a.kind.toUpperCase()} · ${a.distance_km.toFixed(1)} KM</small></div><button class="watch ${prefs.watchlist.includes(a.id) ? 'saved' : ''}" data-watch="${esc(a.id)}" aria-label="${prefs.watchlist.includes(a.id) ? 'Remove' : 'Add'} ${esc(a.name)} ${prefs.watchlist.includes(a.id) ? 'from' : 'to'} watchlist">${prefs.watchlist.includes(a.id) ? '★' : '☆'}</button></div>`,
      )
      .join('') ||
    '<p class="empty">No enabled assets in this radius. Coverage is incomplete; this does not mean no infrastructure exists.</p>';
  $('assets')
    .querySelectorAll('[data-watch]')
    .forEach(
      (b) =>
        (b.onclick = () => {
          const id = b.dataset.watch;
          prefs.watchlist = prefs.watchlist.includes(id)
            ? prefs.watchlist.filter((x) => x !== id)
            : [...prefs.watchlist, id];
          save();
          drawAssets();
          drawPreferences();
        }),
    );
  const nodes = rows.slice(0, 6);
  let graph =
    '<svg viewBox="0 0 280 210" role="img"><title>Earthquake connected to nearby infrastructure; proximity only</title>';
  nodes.forEach((a, i) => {
    const y = 24 + i * 32;
    graph += `<path d="M45 100 Q100 100 142 ${y}" fill="none" stroke="#35524e"/><circle cx="142" cy="${y}" r="4" fill="${a.kind === 'dam' ? '#d9b871' : '#70c9db'}"/><text x="154" y="${y + 3}">${esc(a.name.slice(0, 15))}</text><text x="80" y="${y + 10}" style="font-size:7px">${a.distance_km.toFixed(0)} km</text>`;
  });
  graph += `<circle cx="45" cy="100" r="17" fill="#513b33" stroke="#f58c77"/><text x="30" y="104">M${selected.magnitude.toFixed(1)}</text></svg><p class="empty">${nodes.length} of ${rows.length} links shown · epicenter proximity · ${esc(rows[0]?.method || 'great-circle distance')}</p>`;
  $('relationships').innerHTML = graph;
}
function drawBriefing(value) {
  const evidence = new Map(value.evidence.map((e) => [e.id, e]));
  $('briefing').innerHTML = value.statements
    .map(
      (s) =>
        `<p>${esc(s.text)} ${s.evidence_ids
          .map((id, i) => {
            const e = evidence.get(id);
            return e
              ? `<a href="${esc(safeUrl(e.url))}" title="${esc(e.label)}" target="_blank" rel="noopener noreferrer">[${i + 1}]</a>`
              : '';
          })
          .join('')}</p>`,
    )
    .join('');
  $('briefing-mode').textContent =
    value.mode === 'ai-curated' ? 'AI-CURATED · CITED' : 'VERIFIED FACTS';
}
async function selectEvent(e, fly = true) {
  if (!e) return;
  selected = e;
  const ticket = ++request;
  $('selected-mag').textContent = 'M ' + e.magnitude.toFixed(1);
  $('selected-name').textContent = e.name;
  $('selected-time').textContent = date(e.time);
  $('depth').textContent = e.depth_km.toFixed(1) + ' km';
  $('event-source').href = safeUrl(e.source_url);
  $('coordinates').textContent =
    `${e.lat.toFixed(3)}° N / ${e.lon.toFixed(3)}° E · WGS84`;
  nearby = nearbyAssets(e, assets, prefs.radius);
  if (live) {
    try {
      const response = await json(
        `/api/events/${encodeURIComponent(e.id)}/nearby?radius=${prefs.radius}`,
      );
      if (ticket !== request) return;
      nearby = response;
    } catch (error) {
      notice(
        'Local spatial API unavailable. Showing reference-dataset great-circle distances.',
      );
    }
  }
  if (ticket !== request) return;
  drawList();
  drawAssets();
  drawBriefing(
    !live && e.id === sequence.id && prefs.radius === 100
      ? sequence.briefing
      : factualBriefing(e, nearby),
  );
  await drawMap();
  if (fly) focus(e.lon, e.lat, Math.max(2200000, prefs.radius * 11000));
}
function focus(lon, lat, height) {
  viewer?.camera.flyTo({
    destination: C.Cartesian3.fromDegrees(lon, lat, height),
    duration: 1.3,
  });
}
async function drawMap() {
  if (!viewer || !selected) return;
  const ticket = ++paintRequest;
  if (prefs.earthquakes) {
    quakeLayer.enable(viewer);
    await quakeLayer.update(viewer);
  } else quakeLayer.disable(viewer);
  if (ticket !== paintRequest) return;
  viewer.entities.removeAll();
  if (prefs.earthquakes)
    for (const e of visibleEvents())
      viewer.entities.add({
        id: 'event:' + e.id,
        position: C.Cartesian3.fromDegrees(e.lon, e.lat),
        point: {
          pixelSize: e.id === selected.id ? 12 : 5,
          color: C.Color.fromCssColorString('#f58c77'),
          outlineColor: C.Color.fromCssColorString('#472e29'),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
  viewer.entities.add({
    id: 'radius',
    position: C.Cartesian3.fromDegrees(selected.lon, selected.lat),
    ellipse: {
      semiMajorAxis: prefs.radius * 1000,
      semiMinorAxis: prefs.radius * 1000,
      material: C.Color.fromCssColorString('#b4efca').withAlpha(0.08),
      outline: true,
      outlineColor: C.Color.fromCssColorString('#b4efca').withAlpha(0.65),
      height: 0,
    },
  });
  for (const a of visibleAssets())
    viewer.entities.add({
      id: 'asset:' + a.id,
      position: C.Cartesian3.fromDegrees(a.lon, a.lat),
      point: {
        pixelSize: 7,
        color: C.Color.fromCssColorString(
          a.kind === 'dam' ? '#d9b871' : '#70c9db',
        ),
        outlineColor: C.Color.BLACK,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: a.name,
        font: '11px sans-serif',
        pixelOffset: new C.Cartesian2(10, -12),
        fillColor: C.Color.fromCssColorString('#d1e4e9'),
        style: C.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 3,
        outlineColor: C.Color.fromCssColorString('#10222c'),
        distanceDisplayCondition: new C.DistanceDisplayCondition(0, 900000),
      },
    });
  viewer.scene.requestRender();
}
async function initGlobe() {
  try {
    C.Ion.defaultAccessToken = '';
    viewer = new C.Viewer('globe', {
      baseLayer: false,
      terrainProvider: new C.EllipsoidTerrainProvider(),
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
    });
    viewer.scene.backgroundColor = C.Color.fromCssColorString('#071118');
    viewer.scene.globe.baseColor = C.Color.fromCssColorString('#163245');
    viewer.scene.globe.enableLighting = false;
    viewer.scene.skyAtmosphere.show = false;
    viewer.scene.skyBox.show = false;
    const imagery = await C.TileMapServiceImageryProvider.fromUrl(
      './cesium/Assets/Textures/NaturalEarthII',
    );
    const layer = viewer.imageryLayers.addImageryProvider(imagery);
    layer.brightness = 0.32;
    layer.saturation = 0.25;
    layer.gamma = 0.85;
    try {
      const countries = await C.GeoJsonDataSource.load(
        './data/countries.geojson',
        {
          stroke: C.Color.fromCssColorString('#4a6975'),
          fill: C.Color.fromCssColorString('#19353c').withAlpha(0.9),
          strokeWidth: 1,
        },
      );
      viewer.dataSources.add(countries);
    } catch (error) {
      console.warn(
        'Country outlines unavailable; local imagery remains available',
        error,
      );
    }
    quakeLayer = createEarthquakesLayer({
      source: createCaseSource(visibleEvents),
      symbolScale: 0.1,
      opacityScale: 0.25,
      overlayHost: { setVisible() {}, clearSource() {}, setEntries() {} },
    });
    quakeLayer.init(viewer);
    viewer.screenSpaceEventHandler.setInputAction(({ position }) => {
      const hit = viewer.scene.pick(position);
      const id = hit?.id?.id;
      if (typeof id !== 'string') return;
      if (id.startsWith('event:'))
        selectEvent(
          events.find((e) => e.id === id.slice(6)),
          false,
        );
      else if (id.startsWith('asset:')) {
        const a = assets.find((a) => 'asset:' + a.id === id);
        if (a) {
          notice(`${a.name} · ${a.coverage} · Dataset: ${a.dataset_date}`);
          focus(a.lon, a.lat, 150000);
        }
      }
    }, C.ScreenSpaceEventType.LEFT_CLICK);
  } catch (error) {
    console.warn('Globe unavailable', error);
    $('map-error').hidden = false;
    viewer?.destroy();
    viewer = undefined;
  }
}
function setScenario(id) {
  live = false;
  $('generate').hidden = true;
  $('scenario').disabled = false;
  $('replay').disabled = false;
  $('play').disabled = false;
  $('mode-tag').textContent = '● RECORDED DEMO';
  sequence = scenarios.find((s) => s.id === id) || scenarios[0];
  events = sequence.events;
  $('replay').value = 168;
  stopPlayback();
  updateReplayLabel();
  notice(
    `Recorded case · ${sequence.title} · catalog retrieved ${sequence.event.retrieved_at.slice(0, 10)} · reference infrastructure is not historical`,
  );
  selectEvent(sequence.event);
}
function updateReplayLabel() {
  $('replay-hours').textContent = '+' + $('replay').value + 'h';
  $('replay-time').textContent =
    new Date(sequence.event.time + Number($('replay').value) * 3600000)
      .toISOString()
      .slice(0, 16)
      .replace('T', ' ') + ' UTC';
}
function stopPlayback() {
  clearInterval(playing);
  playing = null;
  $('play').textContent = '▶';
  $('play').setAttribute('aria-label', 'Play event replay');
}
function onReplay() {
  updateReplayLabel();
  const rows = visibleEvents();
  if (!rows.some((e) => e.id === selected?.id) && rows.length)
    selectEvent(rows[0], false);
  else {
    drawList();
    drawMap();
  }
}
function drawPreferences() {
  for (const [id, key] of [
    ['show-airports', 'airports'],
    ['show-dams', 'dams'],
    ['show-earthquakes', 'earthquakes'],
    ['show-inspector', 'inspector'],
  ])
    $(id).checked = prefs[key];
  $('workspace').classList.toggle('hide-inspector', !prefs.inspector);
  $('radius').value = prefs.radius;
  $('radius-value').textContent = prefs.radius + ' km';
  $('regions').innerHTML = prefs.regions
    .map((r, i) => `<button data-region="${i}">${esc(r.name)}</button>`)
    .join('');
  $('regions')
    .querySelectorAll('button')
    .forEach(
      (b) =>
        (b.onclick = () => {
          const r = prefs.regions[Number(b.dataset.region)];
          focus(r.lon, r.lat, r.height);
          $('settings').close();
        }),
    );
  $('watchlist').innerHTML =
    prefs.watchlist
      .map(
        (id) =>
          `<button data-remove="${esc(id)}">${esc(assets.find((a) => a.id === id)?.name || id)} ×</button>`,
      )
      .join('') || 'Star an infrastructure record to save it here.';
  $('watchlist')
    .querySelectorAll('button')
    .forEach(
      (b) =>
        (b.onclick = () => {
          prefs.watchlist = prefs.watchlist.filter(
            (id) => id !== b.dataset.remove,
          );
          save();
          drawPreferences();
          drawAssets();
        }),
    );
}
async function refreshLive() {
  try {
    const [next, health] = await Promise.all([
      json('/api/events?start=' + (Date.now() - 7 * 86400000)),
      json('/api/health'),
    ]);
    if (!live) return;
    events = next;
    if (!events.length) {
      notice(
        'Backend connected, but no events yet. Start the ingestion worker.',
      );
      return;
    }
    const stale =
      !health.feeds.length || health.feeds.some((f) => f.stale || f.error);
    notice(
      `${stale ? 'STALE FEED — last known observations' : 'LOCAL LIVE — ingestion healthy'} · ${events.length} events loaded (up to 1,000; use API pagination for more)`,
    );
    $('source-status').textContent = stale
      ? 'USGS · stale / check worker'
      : 'USGS · local database';
    await selectEvent(
      events.find((e) => e.id === selected?.id) || events[0],
      false,
    );
  } catch (error) {
    notice(
      'Local backend unavailable. Previous observations retained. Start Docker Compose or return to a recorded case.',
    );
  }
}
function bind() {
  $('scenario').onchange = () => setScenario($('scenario').value);
  $('search').oninput = $('min-mag').onchange = () => {
    drawList();
    drawMap();
  };
  $('radius').oninput = () => {
    prefs.radius = Number($('radius').value);
    $('radius-value').textContent = prefs.radius + ' km';
    save();
    selectEvent(selected, false);
  };
  $('reset-view').onclick = () => focus(selected.lon, selected.lat, 2800000);
  $('replay').oninput = () => {
    stopPlayback();
    onReplay();
  };
  $('play').onclick = () => {
    if (playing) return stopPlayback();
    if (Number($('replay').value) >= 168) $('replay').value = 0;
    $('play').textContent = 'Ⅱ';
    $('play').setAttribute('aria-label', 'Pause event replay');
    onReplay();
    playing = setInterval(() => {
      $('replay').value = Math.min(168, Number($('replay').value) + 2);
      onReplay();
      if (Number($('replay').value) >= 168) stopPlayback();
    }, 400);
  };
  $('settings-toggle').onclick = () => {
    $('settings').showModal();
    drawPreferences();
  };
  for (const [id, key] of [
    ['show-airports', 'airports'],
    ['show-dams', 'dams'],
    ['show-earthquakes', 'earthquakes'],
    ['show-inspector', 'inspector'],
  ])
    $(id).onchange = () => {
      prefs[key] = $(id).checked;
      save();
      drawPreferences();
      drawAssets();
      drawMap();
    };
  $('save-region').onclick = () => {
    if (!viewer) return;
    const name = $('region-name').value.trim();
    if (!name) return;
    const p = viewer.camera.positionCartographic;
    prefs.regions = [
      ...prefs.regions.filter((r) => r.name !== name),
      {
        name,
        lon: C.Math.toDegrees(p.longitude),
        lat: C.Math.toDegrees(p.latitude),
        height: p.height,
      },
    ].slice(-50);
    save();
    drawPreferences();
    $('region-name').value = '';
  };
  $('export').onclick = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(prefs, null, 2)], { type: 'application/json' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'observatory-preferences.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $('import').onchange = async () => {
    try {
      const file = $('import').files[0];
      if (!file || file.size > 200000)
        throw Error('Choose a preferences JSON file under 200 KB');
      prefs = validatePreferences(JSON.parse(await file.text()));
      save();
      drawPreferences();
      await selectEvent(selected, false);
      $('settings-status').textContent = 'Preferences imported.';
    } catch (e) {
      $('settings-status').textContent = e.message;
    } finally {
      $('import').value = '';
    }
  };
  $('assets-tab').onclick = $('links-tab').onclick = (e) => {
    const links = e.currentTarget.id === 'links-tab';
    $('assets').hidden = links;
    $('relationships').hidden = !links;
    for (const id of ['assets-tab', 'links-tab']) {
      $(id).classList.toggle('active', (id === 'links-tab') === links);
      $(id).setAttribute(
        'aria-selected',
        String((id === 'links-tab') === links),
      );
    }
  };
  const showResearch = (show) => {
    $('workspace').hidden = show;
    $('research').hidden = !show;
    $('map-tab').classList.toggle('active', !show);
    $('research-tab').classList.toggle('active', show);
    if (!show) {
      viewer?.resize();
      viewer?.scene.requestRender();
    }
  };
  $('research-tab').onclick = () => showResearch(true);
  $('map-tab').onclick = $('back').onclick = () => showResearch(false);
  $('personal-controls').hidden = !personal;
  $('live-mode').onclick = () => {
    live = true;
    stopPlayback();
    $('replay').disabled = true;
    $('play').disabled = true;
    $('replay-time').textContent = 'Live observations';
    $('mode-tag').textContent = '● PERSONAL / LOCAL LIVE';
    $('generate').hidden = false;
    $('settings').close();
    refreshLive();
  };
  $('generate').onclick = async () => {
    const eventId = selected.id,
      ticket = request;
    $('generate').disabled = true;
    try {
      const r = await fetch(
        `/api/events/${encodeURIComponent(eventId)}/briefing?radius=${prefs.radius}`,
        { method: 'POST', headers: { 'X-Observatory-Local': '1' } },
      );
      if (!r.ok) throw Error('Briefing API unavailable');
      const value = await r.json();
      if (ticket === request) drawBriefing(value);
    } catch (e) {
      notice('AI unavailable; the factual briefing remains available.');
    } finally {
      $('generate').disabled = false;
    }
  };
}
function renderResearch() {
  const r = analysis.all,
    s = analysis.sensitivity,
    fmt = (x) => (x == null ? 'N/A' : x.toFixed(3));
  $('research-metrics').innerHTML = [
    ['ANCHOR EVENTS', r.n.toLocaleString(), 'M ≥ 5 · 2021–2025'],
    [
      'MAGNITUDE / 7-DAY COUNT',
      fmt(r.correlations.magnitude__count_7d),
      'Spearman ρ · full cohort',
    ],
    [
      'DEPTH / 7-DAY COUNT',
      fmt(r.correlations.depth_km__count_7d),
      'Spearman ρ · full cohort',
    ],
    [
      'SENSITIVITY COHORT',
      s.n.toLocaleString(),
      `Magnitude ρ = ${fmt(s.correlations.magnitude__count_7d)}`,
    ],
  ]
    .map(
      ([label, value, sub]) =>
        `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${sub}</small></div>`,
    )
    .join('');
  $('scatter').innerHTML = scatter(analysis.rows);
  $('distribution').innerHTML = distribution(analysis.groups);
  $('method').textContent = analysis.method;
  $('limitations').innerHTML = analysis.limitations
    .map((x) => `<li>${esc(x)}</li>`)
    .join('');
}
async function start() {
  [scenarios, assets, analysis] = await Promise.all(
    ['scenarios', 'assets', 'analysis'].map((name) =>
      json(`./data/${name}.json`),
    ),
  );
  $('scenario').innerHTML = scenarios
    .map((s) => `<option value="${esc(s.id)}">${esc(s.title)}</option>`)
    .join('');
  bind();
  drawPreferences();
  renderResearch();
  sequence = scenarios[0];
  events = sequence.events;
  await initGlobe();
  setScenario(sequence.id);
  document.documentElement.dataset.readyMs = (
    performance.now() - started
  ).toFixed(1);
  setInterval(() => {
    if (live) refreshLive();
  }, 60000);
}
start().catch((e) => {
  console.error(e);
  notice(
    'Unable to load recorded data. Run the preparation script and reload. ' +
      e.message,
  );
});

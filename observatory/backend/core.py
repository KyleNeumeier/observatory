"""Pure transformations shared by ingestion, offline demo and tests."""
import math
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def event_record(feature, retrieved_at=None):
    p = feature['properties']
    lon, lat, depth = feature['geometry']['coordinates']
    if p.get('type', 'earthquake') != 'earthquake':
        return None
    if p.get('mag') is None or not all(math.isfinite(float(v)) for v in (lon, lat, depth, p['mag'])):
        return None
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError('Invalid event coordinates')
    return dict(id=feature['id'], name=p.get('place') or feature['id'], lon=lon, lat=lat,
                depth_km=depth, magnitude=p['mag'], time=p['time'], updated=p['updated'],
                source_url=p.get('url') or f"https://earthquake.usgs.gov/earthquakes/eventpage/{feature['id']}",
                retrieved_at=retrieved_at or now(), raw=feature)


def distance_km(a, b):
    """Great-circle reference for portable snapshots; backend uses PostGIS spheroid."""
    lat1, lat2 = map(math.radians, (a['lat'], b['lat']))
    dlat = lat2-lat1
    dlon = math.radians(b['lon']-a['lon'])
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def links(event, assets, radius=100):
    out = []
    for asset in assets:
        distance = distance_km(event, asset)
        if distance <= radius:
            out.append(dict(**asset, distance_km=round(distance, 3),
                            evidence_id='asset:'+asset['id'], relation='nearby',
                            method='great-circle / mean Earth radius'))
    return sorted(out, key=lambda a: (a['distance_km'], a['id']))


def briefing(event, nearby):
    evidence = [{'id': 'event:'+event['id'], 'url': event['source_url'], 'label': event['name']}]
    evidence += [{'id': a['evidence_id'], 'url': a['source_url'], 'label': a['name']} for a in nearby]
    statements = [dict(text=f"Magnitude {event['magnitude']:g} earthquake at {event['name']}; depth {event['depth_km']:g} km.",
                       evidence_ids=[evidence[0]['id']])]
    for a in nearby[:5]:
        statements.append(dict(text=f"{a['name']} ({a['kind']}) is {a['distance_km']:.1f} km from the epicenter.",
                               evidence_ids=[evidence[0]['id'], a['evidence_id']]))
    return dict(mode='deterministic', statements=statements, evidence=evidence,
                caveat='Proximity indicates potential exposure, not confirmed damage or disruption. Infrastructure coverage is incomplete.')


def rank(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0]*len(values)
    i = 0
    while i < len(order):
        j = i+1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for k in order[i:j]:
            result[k] = (i+j-1)/2 + 1
        i = j
    return result


def spearman(x, y):
    if len(x) < 3:
        return None
    a, b = rank(x), rank(y)
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    den = math.sqrt(sum((v-ma)**2 for v in a)*sum((v-mb)**2 for v in b))
    return sum((v-ma)*(w-mb) for v, w in zip(a,b))/den if den else None


def analyze(events, coverage_start_ms, coverage_end_ms):
    """Fixed 2021–2025 anchor cohort; inclusive data coverage, exclusive future start."""
    start = 1609459200000
    end = 1767225600000
    day = 86400000
    ordered = sorted((e for e in events if e['magnitude'] >= 4.5), key=lambda e:e['time'])
    rows = []
    # Spatial latitude prefilter cuts expensive distance calls; time windows bound work.
    import bisect
    times = [e['time'] for e in ordered]
    for e in ordered:
        if e['magnitude'] < 5 or not start <= e['time'] < end:
            continue
        if e['time']-7*day < coverage_start_ms or e['time']+7*day > coverage_end_ms:
            continue
        neighbors = [n for n in ordered[bisect.bisect_left(times,e['time']-7*day):bisect.bisect_right(times,e['time']+7*day)]
                     if n['id'] != e['id'] and abs(n['lat']-e['lat']) <= 1 and distance_km(e,n) <= 100]
        future = [n for n in neighbors if n['time'] > e['time']]
        prior = any(n['magnitude'] >= 5 and n['time'] < e['time'] for n in neighbors)
        rows.append(dict(id=e['id'], magnitude=e['magnitude'], depth_km=e['depth_km'],
                         time=e['time'], count_24h=sum(n['time'] <= e['time']+day for n in future),
                         count_7d=len(future), overlapping_window=prior or any(n['magnitude']>=5 for n in future),
                         preceded_by_anchor=prior))
    def stats(rs):
        return dict(n=len(rs), correlations={f'{x}__{y}':spearman([r[x] for r in rs],[r[y] for r in rs])
                    for x in ('magnitude','depth_km') for y in ('count_24h','count_7d')})
    groups = []
    for low, high in ((5,5.5),(5.5,6),(6,7),(7,10)):
        values = sorted(r['count_7d'] for r in rows if low <= r['magnitude'] < high)
        groups.append(dict(label=f'{low:g}–{high:g}',n=len(values), values=values))
    return dict(all=stats(rows), sensitivity=stats([r for r in rows if not r['preceded_by_anchor']]),
                rows=rows, groups=groups, coverage_start_ms=coverage_start_ms, coverage_end_ms=coverage_end_ms,
                method='Spearman rank correlation with averaged ties. M≥5 anchors, subsequent M≥4.5 within 100 km; 24h and 7d windows.',
                limitations=['Exploratory associations, not causal estimates or forecasts.',
                             'Overlapping sequences create dependent observations; no independent-sample p-values are reported.',
                             'Catalog detection and magnitude reporting vary by region and time.',
                             'Nearby subsequent earthquakes are not automatically classified as aftershocks.',
                             'Sensitivity cohort excludes anchors preceded by M≥5 within 100 km / 7 days.'])

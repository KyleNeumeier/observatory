"""Download once, freeze inputs, reproduce experiment and build three real scenarios.

Run from repo root: python -m observatory.scripts.prepare [--offline]
Cached responses are immutable; use a new cache directory for a fresh catalog revision.
"""
import argparse
import csv
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from observatory.backend.core import analyze, briefing, distance_km, event_record, links, now

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'observatory/data'
PUBLIC=ROOT/'observatory/public/data'
CATALOG='https://earthquake.usgs.gov/fdsnws/event/1/query'


def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')


def download(url, path, offline=False):
    if path.exists():
        return path.read_bytes()
    if offline:
        raise RuntimeError(f'Missing frozen input: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ObservatoryPortfolio/0.1'}),timeout=90) as response:
                data=response.read()
            path.write_bytes(data)
            dump(path.with_suffix(path.suffix+'.meta.json'),{'url':url,'retrieved_at':now(),'sha256':hashlib.sha256(data).hexdigest()})
            return data
        except Exception:
            if attempt==3: raise
            time.sleep(2**attempt)


def catalog_window(start, end, offline):
    params=dict(format='geojson',starttime=start.isoformat(),endtime=end.isoformat(),minmagnitude=4.5,eventtype='earthquake',orderby='time-asc',limit=20000)
    name=start.strftime('%Y%m%d')+'-'+end.strftime('%Y%m%d')
    path=DATA/'raw'/f'{name}.json'
    payload=json.loads(download(CATALOG+'?'+urllib.parse.urlencode(params),path,offline))
    if len(payload['features'])>=20000:
        middle=start+(end-start)/2
        if end-start<timedelta(days=1): raise ValueError('Catalog daily limit exceeded')
        return catalog_window(start,middle,offline)+catalog_window(middle,end,offline)
    stamp=json.loads(path.with_suffix('.json.meta.json').read_text())['retrieved_at']
    return [r for f in payload['features'] if (r:=event_record(f,stamp))]


def asset_records(offline):
    path=DATA/'raw'/'airports.csv'
    raw=download('https://davidmegginson.github.io/ourairports-data/airports.csv',path,offline)
    stamp=json.loads(path.with_suffix('.csv.meta.json').read_text())['retrieved_at']
    assets=[]
    for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        if r['type'] not in ('large_airport','medium_airport'): continue
        assets.append(dict(id='airport:'+r['ident'],name=r['name'],kind='airport',lon=float(r['longitude_deg']),lat=float(r['latitude_deg']),
                           source_url='https://ourairports.com/airports/'+r['ident']+'/',dataset_date=stamp,
                           coverage='Large and medium airports only; OurAirports community data.'))
    # Centroids are representative points, not complete dam geometries or hazard footprints.
    dams=ROOT/'src/data/local_data/dams/dams.geojsonl'
    def coordinates(value):
        if isinstance(value[0],(int,float)):
            yield value[:2]
        else:
            for part in value: yield from coordinates(part)
    for line in dams.read_text(encoding='utf-8').splitlines():
        f=json.loads(line)
        coords=list(coordinates(f['geometry']['coordinates']))
        p=f['properties']; oid=p.get('osm_id',f.get('id'))
        source='relation' if int(oid)<0 else 'way'
        assets.append(dict(id='dam:'+str(oid),name=p.get('name') or 'Unnamed mapped dam',kind='dam',
                           lon=sum(c[0] for c in coords)/len(coords),lat=sum(c[1] for c in coords)/len(coords),
                           source_url=f'https://www.openstreetmap.org/{source}/{abs(int(oid))}',
                           dataset_date='Upstream snapshot 0dbde1e; original collection date unknown',
                           coverage='704-feature OSM/Open Infrastructure Map subset; representative coordinates, incomplete worldwide coverage.'))
    return assets


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--offline',action='store_true'); args=parser.parse_args()
    country_path=DATA/'raw'/'countries.geojson'
    countries=download('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson',country_path,args.offline)
    PUBLIC.mkdir(parents=True,exist_ok=True)
    (PUBLIC/'countries.geojson').write_bytes(countries)
    start=datetime(2020,12,24,tzinfo=timezone.utc); finish=datetime(2026,1,8,tzinfo=timezone.utc)
    all_events={}; current=start
    while current<finish:
        following=min(datetime(current.year+1,1,1,tzinfo=timezone.utc) if current.month==12 else datetime(current.year,current.month+1,1,tzinfo=timezone.utc),finish)
        records=catalog_window(current,following,args.offline)
        for e in records:
            if e['id'] not in all_events or all_events[e['id']]['updated'] <= e['updated']:
                all_events[e['id']]=e
        print(f'{current:%Y-%m}: {len(records)} records',flush=True)
        current=following
    events=sorted(all_events.values(),key=lambda e:(e['time'],e['id']))
    dump(DATA/'catalog.json',events)
    assets=asset_records(args.offline); dump(PUBLIC/'assets.json',assets)
    result=analyze(events,int(start.timestamp()*1000),int(finish.timestamp()*1000))
    dump(PUBLIC/'analysis.json',result)
    scenarios=[]
    for title, year, lat, lon in [('Türkiye · sequence',2023,37,37),('Noto Peninsula · coastal exposure',2024,37.5,137.2),('Taiwan · regional infrastructure',2024,24,121.6)]:
        candidates=[e for e in events if datetime.fromtimestamp(e['time']/1000,timezone.utc).year==year and distance_km(e,dict(lat=lat,lon=lon))<180]
        anchor=max(candidates,key=lambda e:e['magnitude'])
        sequence=[{k:v for k,v in e.items() if k!='raw'} for e in events if anchor['time']<=e['time']<=anchor['time']+7*86400000 and distance_km(anchor,e)<300]
        clean={k:v for k,v in anchor.items() if k!='raw'}
        scenarios.append(dict(id=anchor['id'],title=title,event=clean,events=sequence,briefing=briefing(clean,links(clean,assets))))
    dump(PUBLIC/'scenarios.json',scenarios)
    manifest={'upstream_commit':'0dbde1e36c0177b7664b47702d77ba50f11ddadc',
              'catalog_records':len(events),'assets':len(assets),'anchor_events':result['all']['n'],
              'coverage_start':start.isoformat(),'coverage_end':finish.isoformat(),
              'inputs':[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                            **{k:v for k,v in json.loads(p.with_suffix(p.suffix+'.meta.json').read_text()).items() if k!='sha256'})
                        for p in sorted((DATA/'raw').glob('*')) if not p.name.endswith('.meta.json')]}
    dump(PUBLIC/'manifest.json',manifest)
    print(json.dumps({'events':len(events),'assets':len(assets),'analysis':result['all'],'sensitivity':result['sensitivity']},indent=2))


if __name__=='__main__': main()

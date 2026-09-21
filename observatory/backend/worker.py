import argparse
import json
import logging
import time
from pathlib import Path
import httpx
from .core import event_record, now
from .store import Store

ROOT=Path(__file__).resolve().parents[2]
FEED='https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson'


def poll(store, fetch=httpx.get):
    try:
        response=fetch(FEED,timeout=45)
        response.raise_for_status()
        payload=response.json()
        if not isinstance(payload.get('features'),list):
            raise ValueError('Malformed USGS snapshot')
        retrieved=now()
        records=[event_record(f,retrieved) for f in payload['features']]
        store.upsert_events([r for r in records if r])
        store.mark('usgs-live')
    except Exception as exc:
        store.mark('usgs-live',type(exc).__name__+': '+str(exc)[:200])
        logging.exception('Feed failed; previous records retained')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--import-history',action='store_true')
    args=parser.parse_args()
    store=Store()
    store.initialize()
    assets=ROOT/'observatory/public/data/assets.json'
    if assets.exists():
        store.upsert_assets(json.loads(assets.read_text(encoding='utf-8')))
    if args.import_history:
        records=json.loads((ROOT/'observatory/data/catalog.json').read_text(encoding='utf-8'))
        store.upsert_events(records)
    while True:
        poll(store)
        if args.once:
            return
        time.sleep(60)


if __name__=='__main__':
    main()

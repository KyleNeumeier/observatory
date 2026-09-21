import os
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb


class Store:
    def connect(self):
        return psycopg.connect(os.environ.get('DATABASE_URL','postgresql://observatory:observatory@localhost:5432/observatory'))

    def initialize(self):
        with self.connect() as conn:
            conn.execute(Path(__file__).with_name('schema.sql').read_text())

    def upsert_events(self, records):
        with self.connect() as conn:
            for e in records:
                conn.execute('INSERT INTO event_revisions VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', (e['id'],e['updated'],Jsonb(e)))
                conn.execute('''INSERT INTO events VALUES (%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
                    ON CONFLICT(id) DO UPDATE SET time=excluded.time, updated=excluded.updated, geom=excluded.geom, record=excluded.record
                    WHERE excluded.updated >= events.updated''',(e['id'],e['time'],e['updated'],e['lon'],e['lat'],Jsonb(e)))

    def upsert_assets(self, assets):
        with self.connect() as conn:
            for a in assets:
                conn.execute('''INSERT INTO assets VALUES (%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
                    ON CONFLICT(id) DO UPDATE SET geom=excluded.geom, record=excluded.record, kind=excluded.kind''',
                    (a['id'],a['kind'],a['lon'],a['lat'],Jsonb(a)))

    def events(self, start=0, end=9999999999999, magnitude=0, limit=1000, offset=0):
        with self.connect() as conn:
            return [r[0] for r in conn.execute('''SELECT record - 'raw' FROM events WHERE time BETWEEN %s AND %s
                AND (record->>'magnitude')::float >= %s ORDER BY time DESC,id LIMIT %s OFFSET %s''',(start,end,magnitude,limit,offset))]

    def event(self, id):
        with self.connect() as conn:
            r=conn.execute("SELECT record - 'raw' FROM events WHERE id=%s",(id,)).fetchone()
            return r[0] if r else None

    def nearby(self, event, radius):
        with self.connect() as conn:
            rows=conn.execute('''SELECT record, ST_Distance(geom,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography)/1000 AS distance
                FROM assets WHERE ST_DWithin(geom,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
                ORDER BY distance,id''',(event['lon'],event['lat'],event['lon'],event['lat'],radius*1000))
            return [dict(**r, distance_km=round(d,3), evidence_id='asset:'+r['id'],relation='nearby',method='PostGIS geography / WGS84 spheroid') for r,d in rows]

    def health(self):
        with self.connect() as conn:
            return [dict(id=r[0],last_success=r[1],last_attempt=r[2],error=r[3],stale=r[4]) for r in conn.execute(
                "SELECT *, last_success IS NULL OR last_success < now()-interval '5 minutes' FROM feed_health ORDER BY id")]

    def mark(self, id, error=None):
        with self.connect() as conn:
            conn.execute('''INSERT INTO feed_health(id,last_success,error) VALUES (%s,CASE WHEN %s THEN now() END,%s)
                ON CONFLICT(id) DO UPDATE SET last_attempt=now(), error=excluded.error,
                last_success=CASE WHEN excluded.error IS NULL THEN now() ELSE feed_health.last_success END''',(id,error is None,error))

    def reserve(self, month, amount):
        import math
        if not math.isfinite(amount) or not 0 < amount <= 5:
            raise ValueError('Invalid AI reservation')
        with self.connect() as conn:
            conn.execute('INSERT INTO ai_budget(month) VALUES (%s) ON CONFLICT DO NOTHING',(month,))
            return conn.execute('''UPDATE ai_budget SET reserved_usd=reserved_usd+%s
                WHERE month=%s AND reserved_usd+%s <= 5 RETURNING month''',(amount,month,amount)).fetchone() is not None

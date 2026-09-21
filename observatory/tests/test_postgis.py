"""Real PostGIS integration checks. CI provides a disposable database."""
import os
import pytest
from observatory.backend.store import Store
from .test_backend import event, asset

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Set TEST_DATABASE_URL to a disposable PostGIS database')


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv('DATABASE_URL',os.environ['TEST_DATABASE_URL'])
    db=Store();db.initialize()
    with db.connect() as c:c.execute('TRUNCATE events,event_revisions,assets,feed_health,ai_budget')
    return db


def test_upserts_and_revision_order(store):
    e=event();store.upsert_events([e,e]);new=dict(e,updated=e['updated']+1,magnitude=6)
    store.upsert_events([new,e]);assert store.event('e')['magnitude']==6
    with store.connect() as c:
        assert c.execute('SELECT count(*) FROM events').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM event_revisions').fetchone()[0]==2


def test_dateline_and_inclusive_spheroid_boundary(store):
    e=event(lon=179.9);store.upsert_events([e]);store.upsert_assets([asset(lon=-179.9)])
    assert len(store.nearby(e,23))==1
    assert not store.nearby(e,22)
    with store.connect() as c:
        distance=c.execute('SELECT ST_Distance(a.geom,e.geom)/1000 FROM assets a CROSS JOIN events e').fetchone()[0]
    assert len(store.nearby(e,distance+1e-8))==1
    assert not store.nearby(e,distance-.001)


def test_stale_health_and_atomic_budget(store):
    store.mark('usgs-live');store.mark('usgs-live','timeout')
    assert store.health()[0]['last_success'] is not None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:store.reserve('2026-09',1),range(12)))
    assert sum(results)==5

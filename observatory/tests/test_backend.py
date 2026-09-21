import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from observatory.backend.core import analyze, briefing, distance_km, event_record, links, spearman
from observatory.backend.briefings import select_sentences, generate
from observatory.backend.api import create_app
from observatory.backend.worker import poll

DAY=86400000
T=1640995200000


def event(id='e',time=T,magnitude=5,lat=0,lon=0,depth=10):
    return dict(id=id,time=time,updated=time,magnitude=magnitude,lat=lat,lon=lon,depth_km=depth,name='Test earthquake',source_url='https://earthquake.usgs.gov/',retrieved_at='2026-09-21T00:00:00Z')


def asset(id='a',lon=0):
    return dict(id=id,name='Test airport',kind='airport',lon=lon,lat=0,source_url='https://ourairports.com/')


def test_distance_boundary_and_dateline():
    e=event(lon=179.9);a=asset(lon=-179.9);d=distance_km(e,a)
    assert 22<d<23
    assert len(links(e,[a],d))==1
    assert not links(e,[a],d-.001)


def test_rank_ties_and_constant_series():
    assert spearman([1,2,2,4],[10,20,20,40])==pytest.approx(1)
    assert spearman([1,2,3],[3,2,1])==pytest.approx(-1)
    assert spearman([1,1,1],[1,2,3]) is None


def test_temporal_boundaries_overlap_and_incomplete_windows():
    e=event();records=[event('prior',T-DAY),e,event('same',T,magnitude=4.5),event('day',T+DAY,magnitude=4.5),event('week',T+7*DAY,magnitude=4.5),event('outside',T+7*DAY+1,magnitude=4.5)]
    result=analyze(records,T-8*DAY,T+8*DAY)
    row=next(r for r in result['rows'] if r['id']=='e')
    assert row['count_24h']==1 and row['count_7d']==2 and row['preceded_by_anchor']
    assert result['sensitivity']['n']==1
    assert analyze([e],T-8*DAY,T+6*DAY)['rows']==[]


@pytest.mark.parametrize('i',range(30))
def test_briefing_evaluation_30_cases(i):
    scenarios=json.loads((Path(__file__).parents[1]/'public/data/scenarios.json').read_text(encoding='utf-8'))
    assets=json.loads((Path(__file__).parents[1]/'public/data/assets.json').read_text(encoding='utf-8'))
    e=scenarios[i%3]['event'];near=links(e,assets,10+(i//3)*50)
    result=briefing(e,near)
    ids={r['id'] for r in result['evidence']}
    assert all(set(s['evidence_ids'])<=ids for s in result['statements'])
    assert f"{e['magnitude']:g}" in result['statements'][0]['text']
    assert f"{e['depth_km']:g}" in result['statements'][0]['text']
    for statement,a in zip(result['statements'][1:],near):
        assert f"{a['distance_km']:.1f} km" in statement['text']
    assert not any(word in ' '.join(s['text'].lower() for s in result['statements']) for word in ('destroyed','closed','damaged'))
    assert select_sentences(result,json.dumps({'sentence_ids':[0]}))['statements']==result['statements'][:1]
    with pytest.raises(ValueError):select_sentences(result,'{"sentence_ids":[999]}')
    with pytest.raises(ValueError):select_sentences(result,'{"sentence_ids":[true]}')


class MemoryStore:
    def __init__(self):self.records={'e':event()};self.errors=[]
    def event(self,id):return self.records.get(id)
    def events(self,*args):return list(self.records.values())
    def nearby(self,e,radius):return links(e,[asset()],radius)
    def health(self):return []
    def mark(self,id,error=None):self.errors.append(error)
    def upsert_events(self,rows):
        for r in rows:
            if r['updated']>=self.records.get(r['id'],{'updated':-1})['updated']:self.records[r['id']]=r


def test_api_validation_relationships_and_no_model_fallback(monkeypatch):
    monkeypatch.delenv('AI_CHAT_ENDPOINT',raising=False)
    client=TestClient(create_app(MemoryStore()))
    assert client.get('/api/events/e').status_code==200
    assert client.get('/api/events/missing').status_code==404
    assert client.get('/api/events/e/nearby?radius=-1').status_code==422
    assert client.get('/api/events?start=10&end=1').status_code==422
    assert client.get('/api/events/e/relationships').json()['edges'][0]['target']=='a'
    assert client.post('/api/events/e/briefing',headers={'X-Observatory-Local':'1'}).json()['mode']=='deterministic'
    assert client.post('/api/events/e/briefing').status_code==422
    assert client.post('/api/events/e/briefing',headers={'X-Observatory-Local':'1','Origin':'https://untrusted.example'}).status_code==403
    assert client.get('/openapi.json').status_code==200


def test_outage_retains_observations():
    store=MemoryStore()
    def failure(*args,**kwargs):raise TimeoutError('Test timeout')
    poll(store,failure)
    assert store.records['e']['id']=='e'
    assert 'TimeoutError' in store.errors[-1]


def test_optional_ai_budget_denial_keeps_factual_summary(monkeypatch):
    for k,v in {'AI_CHAT_ENDPOINT':'https://example.com','AI_MODEL':'test','AI_API_KEY':'fake','AI_MAX_REQUEST_USD':'.1'}.items():monkeypatch.setenv(k,v)
    class Denied:
        def reserve(self,*args):return False
    result=generate(event(),[],Denied())
    assert result['mode']=='deterministic' and 'limit' in result['fallback_reason']

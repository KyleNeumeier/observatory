import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Header
from .store import Store
from .core import briefing
from .briefings import generate

DATA=Path(__file__).resolve().parents[1]/'public'/'data'


def create_app(store=None):
    app=FastAPI(title='Observatory earthquake intelligence',version='0.1.0')
    app.state.store=store or Store()

    def event(id):
        record=app.state.store.event(id)
        if record is None:
            raise HTTPException(404,'Unknown earthquake')
        return record

    @app.get('/api/events')
    def events(start:int=0,end:int=9999999999999,magnitude:float=Query(0,ge=-2,le=10),
               limit:int=Query(1000,ge=1,le=10000),offset:int=Query(0,ge=0)):
        if end<start:
            raise HTTPException(422,'end must follow start')
        return app.state.store.events(start,end,magnitude,limit,offset)

    @app.get('/api/events/{id}')
    def details(id:str):
        return event(id)

    @app.get('/api/events/{id}/nearby')
    def nearby(id:str,radius:float=Query(100,gt=0,le=500)):
        return app.state.store.nearby(event(id),radius)

    @app.get('/api/events/{id}/relationships')
    def relationships(id:str,radius:float=Query(100,gt=0,le=500)):
        e=event(id)
        assets=app.state.store.nearby(e,radius)
        return {'nodes':[e,*assets],'edges':[{'source':id,'target':a['id'],
                'relation':'nearby','distance_km':a['distance_km'],'method':a['method'],
                'evidence_ids':['event:'+id,a['evidence_id']]} for a in assets]}

    @app.get('/api/events/{id}/briefing')
    def summary(id:str,radius:float=Query(100,gt=0,le=500)):
        e=event(id)
        return briefing(e,app.state.store.nearby(e,radius))

    @app.post('/api/events/{id}/briefing')
    def ai_summary(id:str,radius:float=Query(100,gt=0,le=500),x_observatory_local:str=Header(...),origin:str|None=Header(None)):
        if x_observatory_local!='1' or (origin and origin not in ('http://127.0.0.1:4180','http://localhost:4180')):
            raise HTTPException(403,'AI generation is available only from the local workspace')
        e=event(id)
        return generate(e,app.state.store.nearby(e,radius),app.state.store)

    @app.get('/api/analysis')
    def analysis():
        path=DATA/'analysis.json'
        if not path.exists():
            raise HTTPException(503,'Run the historical experiment first')
        return json.loads(path.read_text(encoding='utf-8'))

    @app.get('/api/health')
    def health():
        try:
            return {'feeds':app.state.store.health(),'database':'ready'}
        except Exception:
            raise HTTPException(503,'Database unavailable')

    return app


app=create_app()

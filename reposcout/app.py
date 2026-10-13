import asyncio
import json
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from . import store
from .agent import run, markdown
from .models import TaskRequest
from .tools import normalize_repository

pool = ThreadPoolExecutor(max_workers=2)


@asynccontextmanager
async def lifespan(app):
    global pool
    pool = ThreadPoolExecutor(max_workers=2)
    store.init()
    yield
    pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title='RepoScout', lifespan=lifespan)


@app.get('/')
def homepage():
    return FileResponse(store.ROOT / 'web' / 'index.html')


@app.get('/api/health')
def health():
    return {'ok':True,'version':'0.1.0'}


@app.get('/workspace.css')
def stylesheet():
    return FileResponse(store.ROOT / 'web' / 'workspace.css', media_type='text/css')


@app.get('/workspace.js')
def javascript():
    return FileResponse(store.ROOT / 'web' / 'workspace.js', media_type='text/javascript')


@app.post('/api/tasks',status_code=201)
def create(request: TaskRequest):
    if len(set(r.id for r in request.requirements)) != len(request.requirements):
        raise HTTPException(422,'需求 ID 不可重复')
    try:
        request.repositories = [normalize_repository(r) for r in request.repositories]
    except ValueError as error:
        raise HTTPException(422,str(error))
    request.repositories = list(dict.fromkeys(request.repositories))
    if request.mode == 'deepseek':
        import os
        if not os.getenv('DEEPSEEK_API_KEY'):
            raise HTTPException(422,'未配置 DeepSeek，先使用演示或 GitHub 采集模式')
    ident = store.create(request.model_dump())
    pool.submit(run,ident,request)
    return {'id':ident}


@app.get('/api/tasks')
def history():
    return store.recent()


@app.get('/api/tasks/{ident}')
def task(ident: str):
    item = store.get(ident)
    if not item:
        raise HTTPException(404,'任务不存在')
    return item


@app.post('/api/tasks/{ident}/cancel')
def cancel(ident: str):
    task(ident)
    return {'cancelled':store.cancel(ident)}


@app.get('/api/tasks/{ident}/events')
async def events(ident: str, after: int = 0):
    task(ident)
    async def generate():
        cursor = after
        while True:
            batch = store.events(ident,cursor)
            for event in batch:
                cursor = event['id']
                yield 'id: '+str(cursor)+'\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
            if store.get(ident)['status'] not in ('queued','running') and not batch:
                yield 'event: finished\ndata: {}\n\n'
                break
            if not batch:
                yield ': heartbeat\n\n'
            await asyncio.sleep(.4)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'Cache-Control':'no-cache'})


@app.get('/api/tasks/{ident}/export')
def export(ident: str, format: str = 'markdown'):
    report = task(ident)['result']
    if not report:
        raise HTTPException(409,'报告尚未生成')
    if format not in ('markdown','json'):
        raise HTTPException(422,'仅支持 markdown/json')
    text = markdown(report) if format == 'markdown' else json.dumps(report,ensure_ascii=False,indent=2)
    ext = 'md' if format == 'markdown' else 'json'
    return Response(text,media_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="reposcout-{ident}.{ext}"'})

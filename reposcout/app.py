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
from .provider import settings, ModelService, ModelError

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
        try:
            configured = bool(settings().key)
        except ModelError as error:
            raise HTTPException(422, str(error))
        if not configured:
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
    saved = store.load_checkpoint(ident)
    item['resumable'] = item['status'] in ('partial', 'failed', 'interrupted', 'cancelled') and bool(saved)
    if item['resumable'] and not item['result']:
        from .tools import Runtime
        from .checkpoint import restore
        from .orchestrator import fallback
        runtime = Runtime(TaskRequest.model_validate(item['request']), lambda: None, lambda *args: None)
        restore(runtime, saved)
        item['result'] = fallback(runtime, 'interrupted_checkpoint')
    return item


@app.post('/api/tasks/{ident}/resume', status_code=201)
def resume(ident: str):
    original = task(ident)
    if not original['resumable']:
        raise HTTPException(409, '该任务没有可继续的检查点')
    request = TaskRequest.model_validate(original['request'])
    if request.mode == 'deepseek' and not settings().key:
        raise HTTPException(422, '继续调查需要已配置的模型密钥')
    restored = store.load_checkpoint(ident)
    new_id = store.create(request.model_dump())
    store.event(new_id, 'resumed', {'message': '复用已保存资料，使用新一轮预算；模型调用可能产生费用', 'parent_task_id': ident})
    pool.submit(run, new_id, request, restored)
    return {'id': new_id, 'parent_task_id': ident}


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


@app.get('/api/model/config')
def model_config():
    try:
        config = settings()
        return {'provider': 'DeepSeek', 'configured': bool(config.key), 'model': config.model}
    except ModelError as error:
        raise HTTPException(422, str(error))


@app.post('/api/model/test')
def model_test():
    try:
        return ModelService().test_connection()
    except ModelError as error:
        raise HTTPException(422, str(error))

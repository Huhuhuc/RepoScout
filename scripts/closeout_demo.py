"""Reproducible demo. Default: isolated offline recovery; --live: paid API investigation."""
import argparse
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import httpx


def recovery():
    from fastapi.testclient import TestClient
    from reposcout import store
    from reposcout.app import app
    from reposcout.checkpoint import dump
    from reposcout.models import TaskRequest, Requirement
    from reposcout.tools import Runtime
    with tempfile.TemporaryDirectory() as folder, patch.object(store, 'DB', Path(folder)/'demo.db'):
        with TestClient(app) as client:
            request=TaskRequest(question='Offline recovery demo',mode='demo',repositories=['demo/AtlasKB'],
                                requirements=[Requirement(id='R1',text='支持本地部署')])
            parent=store.create(request.model_dump());store.claim(parent)
            runtime=Runtime(request,lambda:None,lambda *args:None)
            runtime.call('read_repository',{'repository':'demo/AtlasKB'})
            store.checkpoint(parent,dump(runtime));store.cancel(parent)
            original=client.get('/api/tasks/'+parent).json()
            response=client.post('/api/tasks/'+parent+'/resume');response.raise_for_status()
            child=response.json()['id']; deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                result=client.get('/api/tasks/'+child).json()
                if result['status'] not in ('queued','running'):break
                time.sleep(.05)
            exported=client.get('/api/tasks/'+child+'/export')
            parent_status=client.get('/api/tasks/'+parent).json()['status']
            assert original['resumable'] and parent_status=='cancelled'
            assert result['status']=='completed' and exported.status_code==200
            assert result['result']['sources']
            return {'scenario':'recovery','data':'fictional demo, isolated temporary database',
                    'model_calls':0,'network_calls':0,'parent_status':parent_status,
                    'child_status':result['status'],'export_status':exported.status_code}


def live(scenario, port, output):
    requirement={'quick':'同时提供同步和异步 API',
                 'followup':'HTTP/2 默认开启，无需额外配置'}[scenario]
    base=f'http://127.0.0.1:{port}'
    with httpx.Client(base_url=base,trust_env=False,timeout=15) as client:
        response=client.post('/api/tasks',json={'question':'演示：核实 HTTPX 的 '+requirement,
            'requirements':[{'id':'R1','text':requirement}], 'repositories':['encode/httpx'],
            'mode':'deepseek','strategy':'auto','max_tokens':60000,'verify_claims':True})
        response.raise_for_status();ident=response.json()['id']
        print(json.dumps({'task_id':ident,'workbench':base,'paid_model_calls':True}),flush=True)
        deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            response=client.get('/api/tasks/'+ident);response.raise_for_status();task=response.json()
            if task['status'] not in ('queued','running'):break
            time.sleep(1)
        else:
            raise TimeoutError('Task still running; inspect workbench before submitting another task')
        output.mkdir(parents=True,exist_ok=True)
        for format,ext in [('markdown','md'),('json','json')]:
            report=client.get('/api/tasks/'+ident+'/export',params={'format':format})
            report.raise_for_status();(output/f'{scenario}-{ident}.{ext}').write_text(report.text,encoding='utf-8')
        return {'task_id':ident,'status':task['status'],'routing':task['result'].get('routing'),
                'metrics':task['result']['metrics'],'output':str(output)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=['recovery','quick','followup'],default='recovery')
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--port',type=int,default=8011)
    parser.add_argument('--output',type=Path,default=Path('data/demo-exports'))
    args=parser.parse_args()
    if args.scenario!='recovery' and not args.live:
        parser.error('quick/followup require explicit --live; this calls the configured model')
    result=recovery() if args.scenario=='recovery' else live(args.scenario,args.port,args.output)
    print(json.dumps(result,ensure_ascii=True,indent=2))

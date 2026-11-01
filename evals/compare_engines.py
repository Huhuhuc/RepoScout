"""Paid bounded two-engine smoke comparison using identical frozen sources."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from .frozen import FrozenRuntime
from .run import score
from reposcout.provider import ModelService
from reposcout.orchestrator import investigate as legacy
from reposcout.graph_engine import investigate as graph

def run(output, count=2):
    output.mkdir(parents=True, exist_ok=False)
    dataset=Path('evals/multi-repo-cases.json')
    cases=json.loads(dataset.read_text(encoding='utf-8'))['cases'][:count]
    result={'created_at':datetime.now(timezone.utc).isoformat(),
        'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),
        'code_sha256':hashlib.sha256(b''.join(p.read_bytes() for p in sorted([*Path('reposcout').glob('*.py'),*Path('evals').glob('*.py')]))).hexdigest(),
        'strategy':'auto','verify_claims':False,'count':count,'scope':'Frozen tasks, one run each; not a statistical benchmark', 'rows':[]}
    for i,case in enumerate(cases):
        for engine in (['legacy','langgraph'] if i%2==0 else ['langgraph','legacy']):
            runtime=FrozenRuntime(case)
            runtime.request.strategy='auto';runtime.request.engine=engine
            service=ModelService(emit=runtime.emit,guard=runtime.guard)
            result['model']=service.config.model
            row={'id':case['id'],'engine':engine,'request':runtime.request.model_dump()}
            start=time.monotonic()
            try:
                report=legacy(runtime,service) if engine=='legacy' else graph(runtime,service,ident=case['id'],path=output/'checkpoints.db')
                a=report['assessments'][0]
                row['score']=score(case,a['status'],[runtime.evidence[e]['quote'] for e in a['evidence_ids']],
                    [s['text'] for s in runtime.sources.values()],report.get('completion',{}).get('type')=='model_submitted')
                row['report']=report
            except Exception as error:
                row['error']=type(error).__name__
                row['score']=score(case,'error',[],[],False)
            row.update(tokens=dict(service.usage),model_requests=service.attempts,
                seconds=round(time.monotonic()-start,3),events=runtime.events)
            result['rows'].append(row)
            (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k not in ('report','events','request')},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-cases',type=int,choices=range(1,13),default=2)
    args=p.parse_args()
    if not args.live:p.error('Paid calls require --live')
    run(args.output,args.max_cases)

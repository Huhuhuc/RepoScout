import json
import tempfile
import unittest
import httpx
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from reposcout import store
from reposcout.app import app
from reposcout.agent import deepseek_agent, validate_report
from reposcout.models import TaskRequest, Requirement, ReportArgs
from reposcout.tools import Runtime
from reposcout.context import snapshot, terms_for
from reposcout.checkpoint import dump, restore
from reposcout.provider import ModelError
from reposcout.official_docs import read_page, TextParser
from test_orchestrator import ScriptService


class ReliabilityTests(unittest.TestCase):
    def runtime(self):
        r=Runtime(TaskRequest(question='核实本地部署',mode='deepseek',max_tools=40,
            repositories=['a/b'],requirements=[Requirement(id='R1',text='支持本地部署')]),lambda:None,lambda *a:None)
        r.repositories=['a/b']
        r.add_source('a/b','readme','README','https://github.com/a/b','Introduction. '*1000,ref='v1')
        r.read_documentation=Mock(return_value={'source_ids':[]})
        r.read_releases=Mock(return_value={'source_ids':[]})
        r.search_issues=Mock(return_value={'source_ids':[]})
        return r

    def test_two_rounds_are_reachable(self):
        r=self.runtime()
        review=('review_evidence',{'assessments':[],'summary':'缺口'})
        def follow(q):return ('investigate_gaps',{'targets':[{'repository':'a/b','requirement_id':'R1','query':q}]})
        service=ScriptService([[review],[follow('local')],[review],[follow('offline')],
            [('submit_report',{'assessments':[],'summary':'保持未知'})]])
        report=deepseek_agent(r,service)
        self.assertEqual(report['research']['rounds_used'],2)
        self.assertEqual(report['completion']['type'],'model_submitted')
        self.assertNotIn('investigate_gaps',service.allowed[-1])

    def test_new_read_windows_prevent_false_stall(self):
        r=self.runtime()
        service=ScriptService([[('read_source',{'source_id':'S1','offset':i*2400})] for i in range(4)]+
            [[('submit_report',{'assessments':[],'summary':'未知'})]])
        r.request.max_followups=0
        deepseek_agent(r,service)
        self.assertIn('read_repository',service.allowed[4])
        self.assertEqual(len(r.read_windows),4)

    def test_repeated_identical_read_is_blocked(self):
        r=self.runtime()
        for _ in range(2):r.call('read_source',{'source_id':'S1'})
        with self.assertRaises(ValueError):r.call('read_source',{'source_id':'S1'})

    def test_model_failure_retains_sources(self):
        r=self.runtime(); service=ScriptService([])
        service.chat=Mock(side_effect=ModelError('offline'))
        report=deepseek_agent(r,service)
        self.assertEqual(report['completion']['reason'],'model_error')
        self.assertEqual(len(report['sources']),1)

    def test_token_limit_stops_before_request(self):
        r=self.runtime();r.request.max_tokens=4000
        service=ScriptService([])
        report=deepseek_agent(r,service)
        self.assertEqual(service.attempts,0)
        self.assertEqual(report['completion']['reason'],'token_budget')

    def test_failed_model_request_is_counted_in_partial_report(self):
        r=self.runtime();service=ScriptService([])
        def fail(*args):
            service.attempts+=1
            raise ModelError('offline')
        service.chat=fail
        report=deepseek_agent(r,service)
        self.assertEqual(report['metrics']['model_requests'],1)

    def test_chinese_and_late_sources_get_context(self):
        r=self.runtime()
        self.assertIn('本地',terms_for('支持本地部署'))
        for i in range(9):r.add_source('a/b','documentation',str(i),'https://github.com/a/b/'+str(i),'x'*5000+' 本地部署支持离线使用。')
        view=snapshot(r,'research','',[])
        self.assertTrue(all(s['excerpts'] for s in view['sources']))
        self.assertIn('本地部署',str(view['sources'][-1]['excerpts']))
        self.assertLessEqual(sum(len(p['text']) for s in view['sources'] for p in s['excerpts']),10000)

    def test_official_sources_precede_issues(self):
        r=self.runtime(); order=[]
        for name in ('read_documentation','read_releases','search_issues'):
            setattr(r,name,Mock(side_effect=lambda name=name,**kw: order.append(name) or {'source_ids':[]}))
        r.review_evidence([], 'initial')
        r.investigate_gaps([{'repository':'a/b','requirement_id':'R1','query':'local','document_path':None}])
        self.assertEqual(order,['read_documentation','read_releases','search_issues'])

    def test_checkpoint_round_trip_resets_budget_not_sources(self):
        r=self.runtime();r.read_source('S1');r.calls=9
        saved=json.loads(json.dumps(dump(r))); other=self.runtime();restore(other,saved)
        self.assertEqual(other.sources,r.sources)
        self.assertEqual(other.read_windows,r.read_windows)
        self.assertEqual(other.calls,0)
        self.assertNotIn('headers',saved['state'])

    def test_resume_does_not_keep_stale_pre_followup_decision(self):
        r=self.runtime();r.review_evidence([], 'initial')
        r.followups=[{'review_index':1,'actions':[{'repository':'a/b','requirement_id':'R1'}]}]
        r.reviews[-1]['assessments'][0]['status']='supported'
        other=self.runtime();restore(other,dump(r))
        self.assertEqual(other.reviews[-1]['assessments'][0]['status'],'unknown')
        self.assertEqual(len(other.reviews[-1]['gaps']),1)

    def test_claim_conditions_are_visible_not_auto_verified(self):
        r=self.runtime();r.sources['S1']['text']='仅企业版支持本地部署'
        e=r.save_evidence('S1','R1','仅企业版支持本地部署')
        report=validate_report(r,ReportArgs(summary='',assessments=[dict(repository='a/b',requirement_id='R1',
            status='supported',explanation='condition',evidence_ids=[e['id']])]))
        check=report['verification'][0]
        self.assertTrue(check['quote_match'])
        self.assertEqual(check['semantic_support'],'needs_review')
        self.assertTrue(check['warnings'])

    def test_model_review_downgrades_unsupported_inference(self):
        from reposcout.semantic_review import review_report
        r=self.runtime();r.model_metrics={};r.closing=True
        e=r.save_evidence('S1','R1','Introduction.')
        report=validate_report(r,ReportArgs(summary='支持',assessments=[dict(repository='a/b',requirement_id='R1',
            status='supported',explanation='bad',evidence_ids=[e['id']])]))
        report['completion']={'type':'model_submitted'}
        service=ScriptService([[('review_claims',{'verdicts':[{'repository':'a/b','requirement_id':'R1',
            'verdict':'insufficient','reason':'摘录没有说明本地部署'}]})]])
        checked=review_report(r,service,report)
        self.assertEqual(checked['assessments'][0]['status'],'unknown')
        self.assertEqual(checked['semantic_review']['status'],'completed')
        self.assertEqual(r.reviews[-1]['assessments'][0]['status'],'unknown')

    def test_incomplete_review_does_not_claim_verification(self):
        from reposcout.semantic_review import review_report
        r=self.runtime();r.model_metrics={}
        e=r.save_evidence('S1','R1','Introduction.')
        report=validate_report(r,ReportArgs(summary='',assessments=[dict(repository='a/b',requirement_id='R1',
            status='supported',explanation='',evidence_ids=[e['id']])]))
        service=ScriptService([[('review_claims',{'verdicts':[]})]])
        self.assertEqual(review_report(r,service,report)['semantic_review']['status'],'failed')

    def test_external_documents_reject_unlinked_or_private_urls(self):
        r=self.runtime()
        for url in ('http://127.0.0.1','https://evil.test/docs','https://docs.langchain.com/unlinked'):
            with self.assertRaises(ValueError):read_page(r,'a/b',url)
        self.assertEqual(r.http_calls,0)

    def test_html_extraction_discards_scripts(self):
        p=TextParser();p.feed('<h1>Manual</h1><script>steal()</script><p>Local</p>')
        self.assertIn('Local',''.join(p.parts));self.assertNotIn('steal',''.join(p.parts))

    def test_official_document_read_is_bounded_and_unauthenticated(self):
        r=self.runtime(); url='https://docs.langchain.com/test'
        r.sources['S1']['text']='[Official docs]('+url+')'
        seen=[]
        def handle(request):
            seen.append(request)
            return httpx.Response(200,headers={'content-type':'text/html'},text='<h1>Guide</h1><p>Local deployment.</p>')
        client=httpx.Client(transport=httpx.MockTransport(handle))
        with patch('reposcout.official_docs.httpx.Client',return_value=client):
            source=read_page(r,'a/b',url)
        self.assertIn('Local deployment.',source['text'])
        self.assertEqual(source['kind'],'official_page')
        self.assertNotIn('authorization',seen[0].headers)
        self.assertTrue(source['metadata']['version_unpinned'])

    def test_restart_checkpoint_is_viewable_and_exportable(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store,'DB',Path(folder)/'test.db'):
            store.init();r=self.runtime();ident=store.create(r.request.model_dump());store.claim(ident)
            store.checkpoint(ident,dump(r))
            with TestClient(app) as client:
                task=client.get('/api/tasks/'+ident).json()
                self.assertEqual(task['status'],'interrupted')
                self.assertTrue(task['resumable'])
                self.assertEqual(len(task['result']['sources']),1)
                self.assertEqual(client.get('/api/tasks/'+ident+'/export').status_code,200)

    def test_resume_creates_linked_task_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store,'DB',Path(folder)/'test.db'):
            with TestClient(app) as client:
                r=self.runtime();ident=store.create(r.request.model_dump());store.claim(ident)
                store.checkpoint(ident,dump(r));store.finish(ident,'partial',{'saved':True})
                with patch('reposcout.app.pool.submit') as submit, patch('reposcout.app.settings',return_value=Mock(key='test')):
                    response=client.post('/api/tasks/'+ident+'/resume')
                self.assertEqual(response.status_code,201)
                self.assertNotEqual(response.json()['id'],ident)
                self.assertEqual(store.get(ident)['result'],{'saved':True})
                self.assertEqual(submit.call_count,1)

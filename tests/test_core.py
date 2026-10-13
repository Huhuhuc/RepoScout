import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from reposcout.models import TaskRequest, Requirement, ReportArgs, Assessment
from reposcout.tools import Runtime, normalize_repository
from reposcout.agent import demo_agent, validate_report
from reposcout import store
from reposcout.app import app


def request(**kwargs):
    return TaskRequest(question='比较知识库项目',requirements=[Requirement(id='R1',text='支持本地部署'),Requirement(id='R2',text='支持 PDF 导入'),Requirement(id='R3',text='回答包含来源引用')],**kwargs)


class CoreTests(unittest.TestCase):
    def runtime(self, **kwargs):
        return Runtime(request(**kwargs),lambda:None,lambda *args:None)

    def test_demo_matrix_and_exclusion(self):
        report = demo_agent(self.runtime())
        self.assertEqual(len(report['assessments']),9)
        self.assertIn('demo/CloudShelf',report['excluded'])
        self.assertIn('demo/PaperNest',report['excluded'])
        self.assertTrue(any(a['status']=='unknown' for a in report['assessments']))

    def test_fabricated_quote_rejected(self):
        r=self.runtime();r.call('read_repository',{'repository':'demo/AtlasKB'})
        with self.assertRaises(ValueError):r.call('save_evidence',{'source_id':'S1','requirement_id':'R1','quote':'每秒处理一百万请求'})

    def test_cross_requirement_evidence_rejected(self):
        r=self.runtime();r.call('read_repository',{'repository':'demo/AtlasKB'})
        e=r.call('save_evidence',{'source_id':'S1','requirement_id':'R1','quote':'支持本地部署'})
        with self.assertRaises(ValueError):validate_report(r,ReportArgs(summary='',assessments=[Assessment(repository='demo/AtlasKB',requirement_id='R2',status='supported',explanation='',evidence_ids=[e['id']])]))

    def test_budget_enforced(self):
        with self.assertRaises(TimeoutError):demo_agent(self.runtime(max_tools=1))

    def test_repository_path_validation(self):
        self.assertEqual(normalize_repository('https://github.com/a/b.git'),'a/b')
        for value in ['../b','https://evil.test/a/b','a/b/c','a/..']:
            with self.assertRaises(ValueError):normalize_repository(value)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=store.DB;store.DB=Path(self.temp.name)/'test.db'
        self.context=TestClient(app);self.client=self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None,None,None);store.DB=self.old;self.temp.cleanup()

    def test_complete_history_events_export(self):
        response=self.client.post('/api/tasks',json=request().model_dump());self.assertEqual(response.status_code,201)
        ident=response.json()['id']
        for _ in range(100):
            task=self.client.get('/api/tasks/'+ident).json()
            if task['status'] not in ('queued','running'):break
            time.sleep(.03)
        self.assertEqual(task['status'],'completed')
        self.assertTrue(store.events(ident))
        self.assertIn('原文证据',self.client.get('/api/tasks/'+ident+'/export').text)
        self.assertEqual(self.client.get('/api/tasks/'+ident+'/export?format=json').status_code,200)

    def test_cancel_prevents_finish(self):
        ident=store.create(request().model_dump());self.assertTrue(store.claim(ident));self.assertTrue(store.cancel(ident))
        self.assertFalse(store.finish(ident,'completed',{'bad':True}))
        self.assertEqual(store.get(ident)['status'],'cancelled')

    def test_restart_marks_interrupted(self):
        ident=store.create(request().model_dump());store.claim(ident);store.init()
        self.assertEqual(store.get(ident)['status'],'interrupted')

    def test_duplicate_requirement_rejected(self):
        data=request().model_dump();data['requirements'][1]['id']='R1'
        self.assertEqual(self.client.post('/api/tasks',json=data).status_code,422)

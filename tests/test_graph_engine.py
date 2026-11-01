import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from reposcout.graph_engine import investigate, recovery_status
from reposcout.tools import Runtime
from reposcout.models import TaskRequest, Requirement
from reposcout.orchestrator import investigate as legacy
from reposcout import store
from test_orchestrator import ScriptService


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'graph.db'
        self.addCleanup(self.temp.cleanup)

    def runtime(self):
        r = Runtime(TaskRequest(question='check PDF', requirements=[Requirement(id='R1',text='PDF')],
                    repositories=['a/b'], max_followups=0),lambda:None,Mock())
        r.repositories=['a/b']
        r.add_source('a/b','readme','README','https://github.com/a/b','An agent.')
        return r

    def submit(self):
        return [('submit_report',{'assessments':[], 'summary':'Unknown'})]

    def test_legacy_parity(self):
        old=legacy(self.runtime(),ScriptService([self.submit()]))
        new=investigate(self.runtime(),ScriptService([self.submit()]),ident='a',path=self.path)
        self.assertEqual(old['assessments'],new['assessments'])
        self.assertEqual(new['completion']['type'],'model_submitted')

    def test_restore_pending_tool_without_repeating_model(self):
        self.assertIsNone(investigate(self.runtime(),ScriptService([self.submit()]),ident='a',path=self.path,pause_after='decide'))
        self.assertTrue(recovery_status('a',self.path)[0])
        service=ScriptService([])
        result=investigate(self.runtime(),service,ident='a',path=self.path,recover=True)
        self.assertEqual(service.attempts,1)
        self.assertEqual(result['metrics']['tokens']['total_tokens'],10)
        self.assertEqual(result['completion']['type'],'model_submitted')

    def test_bad_parameters_are_returned_to_model(self):
        service=ScriptService([[('read_source',{'bad':1})],self.submit()])
        result=investigate(self.runtime(),service,ident='a',path=self.path)
        self.assertEqual(result['completion']['type'],'model_submitted')
        self.assertEqual(service.attempts,2)

    def test_model_budget(self):
        service=ScriptService([[]]*12)
        result=investigate(self.runtime(),service,ident='a',path=self.path)
        self.assertEqual(result['completion']['reason'],'model_budget')
        self.assertEqual(service.attempts,12)

    def test_timeout_is_partial(self):
        service=ScriptService([])
        service.chat=Mock(side_effect=TimeoutError())
        result=investigate(self.runtime(),service,ident='a',path=self.path)
        self.assertEqual(result['completion']['type'],'fallback')

    def test_unconfirmed_node_blocks_replay(self):
        service=ScriptService([])
        service.chat=Mock(side_effect=RuntimeError('simulated crash'))
        with self.assertRaises(RuntimeError):
            investigate(self.runtime(),service,ident='a',path=self.path)
        self.assertFalse(recovery_status('a',self.path)[0])
        with self.assertRaises(ValueError):
            investigate(self.runtime(),ScriptService([]),ident='a',path=self.path,recover=True)

    def test_recovery_claim_only_once(self):
        with patch.object(store,'DB',Path(self.temp.name)/'tasks.db'):
            store.init()
            ident=store.create(self.runtime().request.model_dump())
            store.init()
            self.assertTrue(store.queue_recovery(ident))
            self.assertFalse(store.queue_recovery(ident))

    def test_changed_request_rejected(self):
        investigate(self.runtime(),ScriptService([self.submit()]),ident='a',path=self.path,pause_after='decide')
        r=self.runtime(); r.request.max_tokens=50000
        with self.assertRaises(ValueError):
            investigate(r,ScriptService([]),ident='a',path=self.path,recover=True)

    def test_checkpoint_survives_process_exit(self):
        code = """
import sys
sys.path.insert(0,'tests')
from test_graph_engine import GraphTests, ScriptService, investigate
t=GraphTests()
investigate(t.runtime(),ScriptService([t.submit()]),ident='a',path=sys.argv[1],pause_after='decide')
"""
        subprocess.run([sys.executable,'-c',code,str(self.path)],check=True,capture_output=True)
        service=ScriptService([])
        report=investigate(self.runtime(),service,ident='a',path=self.path,recover=True)
        self.assertEqual(report['completion']['type'],'model_submitted')
        self.assertEqual(service.attempts,1)

    def test_hard_exit_during_model_call_is_not_replayed(self):
        code = """
import sys,os
sys.path.insert(0,'tests')
from test_graph_engine import GraphTests, ScriptService, investigate
t=GraphTests();s=ScriptService([])
s.chat=lambda *args: os._exit(23)
investigate(t.runtime(),s,ident='a',path=sys.argv[1])
"""
        child=subprocess.run([sys.executable,'-c',code,str(self.path)],capture_output=True)
        self.assertEqual(child.returncode,23)
        self.assertFalse(recovery_status('a',self.path)[0])

    def test_tool_timeout_preserves_partial_report(self):
        r=self.runtime(); r.call=Mock(side_effect=TimeoutError())
        report=investigate(r,ScriptService([[('read_source',{'source_id':'S1'})]]),ident='a',path=self.path)
        self.assertEqual(report['completion']['type'],'fallback')
        self.assertTrue(report['sources'])

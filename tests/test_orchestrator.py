import json
import unittest
from unittest.mock import Mock

from reposcout.context import snapshot
from reposcout.models import TaskRequest, Requirement, ReportArgs
from reposcout.tools import Runtime
from reposcout.agent import deepseek_agent, finalize_report, validate_report


class ScriptService:
    def __init__(self, script):
        self.script = iter(script)
        self.attempts = 0
        self.usage = {'total_tokens':0}
        self.allowed = []

    def chat(self, messages, tools):
        self.attempts += 1
        self.usage['total_tokens'] += 10
        self.allowed.append([t['function']['name'] for t in tools])
        calls = next(self.script, [])
        return {'role':'assistant', 'tool_calls':[{'id':str(i),'function':{
            'name':name,'arguments':json.dumps(args)}} for i,(name,args) in enumerate(calls)]}


class OrchestratorTests(unittest.TestCase):
    def runtime(self, tools=20):
        r = Runtime(TaskRequest(question='Check PDF', requirements=[Requirement(id='R1',text='PDF')],
            repositories=['a/b'], mode='github', max_tools=tools),lambda:None,lambda *a:None)
        r.repositories=['a/b']
        r.add_source('a/b','readme','README','https://github.com/a/b','An agent.')
        return r

    def test_budget_reserves_finalization_and_returns_model_report(self):
        r=self.runtime()
        service=ScriptService([[]]*10+[[('submit_report',{'assessments':[],'summary':'未知'})]])
        report=deepseek_agent(r, service)
        self.assertEqual(report['completion']['type'],'model_submitted')
        self.assertEqual(service.allowed[10],['submit_report'])
        self.assertEqual(report['assessments'][0]['status'],'unknown')
        self.assertLessEqual(service.attempts,12)

    def test_invalid_final_report_is_fallback_not_fake_success(self):
        r=self.runtime()
        service=ScriptService([[('submit_report',{'assessments':[{'bad':'data'}],'summary':''})]]*12)
        report=deepseek_agent(r,service)
        self.assertEqual(report['completion']['type'],'fallback')
        self.assertEqual(report['assessments'][0]['status'],'unknown')
        self.assertEqual(service.attempts,12)

    def test_final_review_merged_without_extra_model_round(self):
        r=self.runtime()
        r.closing=True
        report=finalize_report(r,ReportArgs(assessments=[],summary='未知'))
        self.assertEqual(len(r.reviews),1)
        self.assertEqual(report['completion']['type'],'model_submitted')

    def test_unread_requested_candidate_stays_in_matrix_as_unknown(self):
        r=self.runtime()
        r.request.repositories.append('c/d')
        report=validate_report(r,ReportArgs(assessments=[],summary='部分资料'))
        self.assertEqual([(a['repository'],a['status']) for a in report['assessments']],
                         [('a/b','unknown'),('c/d','unknown')])

    def test_context_excerpts_and_full_text_access(self):
        r=self.runtime()
        r.sources['S1']['text']='a'*30000+' PDF is supported.'
        view=snapshot(r,'research','',[])
        self.assertLess(len(json.dumps(view)),15000)
        self.assertIn('PDF is supported',r.read_source('S1',query='PDF')['text'])
        self.assertEqual(len(r.sources['S1']['text']),30018)

    def test_read_cache_does_not_repeat_network_work(self):
        r=self.runtime()
        r.search_issues=Mock(return_value={'source_ids':[]})
        for _ in range(2):r.call('search_issues',{'repository':'a/b','query':'PDF'})
        self.assertEqual(r.search_issues.call_count,1)
        self.assertEqual(r.cache_hits,1)
        self.assertEqual(r.calls,2)

    def test_followup_then_submit_no_review_loop(self):
        r=self.runtime()
        r.search_issues=Mock(return_value={'source_ids':[]})
        service=ScriptService([
            [('review_evidence',{'assessments':[],'summary':'初步'})],
            [('investigate_gaps',{'targets':[{'repository':'a/b','requirement_id':'R1','query':'PDF'}]})],
            [('submit_report',{'assessments':[],'summary':'未发现依据，保持未知'})]])
        report=deepseek_agent(r,service)
        self.assertEqual(report['completion']['type'],'model_submitted')
        self.assertEqual(service.attempts,3)
        self.assertNotIn('investigate_gaps',service.allowed[-1])

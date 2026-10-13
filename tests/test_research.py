import unittest
import json
from unittest.mock import Mock, patch

import httpx

from reposcout.agent import deepseek_agent, finalize_report, validate_report
from reposcout.models import TaskRequest, Requirement, ReportArgs
from reposcout.tools import Runtime


class ResearchTests(unittest.TestCase):
    def runtime(self, max_tools=40):
        r = Runtime(TaskRequest(question='Local model research', mode='github', max_tools=max_tools,
            requirements=[Requirement(id='R1', text='local models')]), lambda: None, lambda *a: None)
        r.repositories.append('a/b')
        r.add_source('a/b', 'readme', 'README', 'https://github.com/a/b', 'Research agent')
        return r

    def review(self, r, assessments=None):
        return r.call('review_evidence', {'assessments': assessments or [], 'summary': 'checkpoint'})

    def follow(self, r, query='local', path=None):
        return r.call('investigate_gaps', {'targets': [{'repository': 'a/b', 'requirement_id': 'R1',
            'query': query, 'document_path': path}]})

    def test_unknown_to_supported_with_document_evidence(self):
        r = self.runtime()
        self.assertEqual(len(self.review(r)['gaps']), 1)
        r.read_document = Mock(side_effect=lambda **_: r.add_source('a/b', 'documentation', 'Install',
            'https://github.com/a/b/docs/install.md', 'Local models are supported.'))
        result = self.follow(r, path='docs/install.md')
        self.assertEqual(result['actions'][0]['candidates'][0]['needs_review'], True)
        self.assertFalse(r.evidence)
        e = r.call('save_evidence', {'source_id': 'S2', 'requirement_id': 'R1', 'quote': 'Local models are supported.'})
        assessments = [dict(repository='a/b', requirement_id='R1', status='supported', explanation='document', evidence_ids=[e['id']])]
        self.review(r, assessments)
        report = finalize_report(r, ReportArgs(assessments=assessments, summary='done'))
        self.assertFalse(report['research']['gaps'])
        self.assertEqual(report['research']['changes'][0]['before'], 'unknown')
        self.assertEqual(report['research']['changes'][0]['after'], 'supported')

    def test_issue_alone_cannot_make_definitive_claim(self):
        r = self.runtime()
        s = r.add_source('a/b', 'issue', 'bug', 'https://github.com/a/b/issues/1', 'local fails')
        e = r.save_evidence(s['id'], 'R1', 'local fails')
        for status in ('supported', 'unsupported'):
            with self.assertRaises(ValueError):
                validate_report(r, ReportArgs(summary='', assessments=[dict(repository='a/b', requirement_id='R1',
                    status=status, explanation='report', evidence_ids=[e['id']])]))

    def test_no_results_stays_unknown_and_round_limit(self):
        r = self.runtime()
        r.search_issues = Mock(return_value={'source_ids': []})
        self.review(r)
        self.follow(r)
        with self.assertRaises(ValueError):
            self.follow(r, query='ollama')  # must review between rounds
        self.review(r)
        with self.assertRaises(ValueError):
            self.follow(r)  # duplicate query
        self.follow(r, query='ollama')
        self.review(r)
        with self.assertRaises(ValueError):
            self.follow(r, query='offline')
        report = finalize_report(r, ReportArgs(assessments=r.reviews[-1]['assessments'], summary='unknown'))
        self.assertEqual(report['assessments'][0]['status'], 'unknown')
        self.assertEqual(report['research']['rounds_used'], 2)

    def test_invalid_target_rejected_before_io(self):
        r = self.runtime()
        self.review(r)
        r.search_issues = Mock()
        with self.assertRaises(ValueError):
            r.call('investigate_gaps', {'targets': [{'repository': 'outside/repo', 'requirement_id': 'R1', 'query': 'local'}]})
        r.search_issues.assert_not_called()
        self.assertFalse(r.followups)

    def test_failure_record_and_finalize_requires_review(self):
        r = self.runtime()
        self.review(r)
        with self.assertRaises(ValueError):
            finalize_report(r, ReportArgs(assessments=r.reviews[-1]['assessments'], summary='premature'))
        r.search_issues = Mock(side_effect=httpx.ConnectError('offline'))
        self.assertEqual(self.follow(r)['actions'][0]['status'], 'failed')
        with self.assertRaises(ValueError):
            finalize_report(r, ReportArgs(assessments=r.reviews[-1]['assessments'], summary='stale'))
        self.review(r)
        self.assertTrue(finalize_report(r, ReportArgs(assessments=r.reviews[-1]['assessments'], summary='done')))

    def test_nested_tool_budget_and_partial_record(self):
        r = self.runtime(max_tools=2)
        self.review(r)
        with self.assertRaises(TimeoutError):
            self.follow(r)
        self.assertEqual(r.followups[0]['actions'][0]['status'], 'budget_exhausted')
        self.assertEqual(r.calls, 2)

    def test_scripted_model_tool_loop_no_external_requests(self):
        r = self.runtime()
        r.read_document = Mock(side_effect=lambda **_: r.add_source('a/b', 'documentation', 'Install',
            'https://github.com/a/b/docs/install.md', 'Local models are supported.'))
        assessments = [dict(repository='a/b', requirement_id='R1', status='supported', explanation='document', evidence_ids=['E1'])]
        script = [
            ('review_evidence', {'assessments': [], 'summary': 'initial'}),
            ('investigate_gaps', {'targets': [{'repository': 'a/b', 'requirement_id': 'R1', 'query': 'local', 'document_path': 'docs/install.md'}]}),
            ('save_evidence', {'source_id': 'S2', 'requirement_id': 'R1', 'quote': 'Local models are supported.'}),
            ('review_evidence', {'assessments': assessments, 'summary': 'updated'}),
            ('submit_report', {'assessments': assessments, 'summary': 'done'})]
        responses = []
        for index, (name, args) in enumerate(script):
            response = Mock()
            response.status_code = 200
            response.json.return_value = {'choices': [{'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': str(index), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}]}
            responses.append(response)
        client = Mock()
        client.request.side_effect = responses
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-only-not-a-real-key'}), patch('reposcout.provider.httpx.Client') as factory:
            factory.return_value.__enter__.return_value = client
            report = deepseek_agent(r)
        self.assertEqual(report['metrics']['model_calls'], 5)
        self.assertEqual(report['research']['rounds_used'], 1)
        self.assertFalse(report['research']['gaps'])
        self.assertEqual(report['research']['changes'][0]['after'], 'supported')

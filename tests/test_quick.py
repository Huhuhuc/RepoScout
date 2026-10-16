import unittest
from unittest.mock import patch
from evals.frozen import FrozenRuntime
from reposcout.agent import deepseek_agent
from test_orchestrator import ScriptService


class QuickTests(unittest.TestCase):
    def runtime(self):
        runtime = FrozenRuntime({'id': 'quick', 'requirement': 'PDF', 'sources': [
            {'kind': 'readme', 'path': 'README.md', 'text': 'PDF is supported.'}]})
        runtime.request.strategy = 'auto'
        runtime.request.max_followups = 0
        return runtime

    def proposal(self, status='supported', quote='PDF is supported.'):
        return {'summary': 'PDF evidence', 'assessments': [{
            'repository': 'fixture/quick', 'requirement_id': 'R1', 'status': status,
            'explanation': 'README evidence', 'source_id': 'S1', 'quote': quote,
            'evidence_basis': 'explicit_statement' if quote else 'absence_of_evidence'}]}

    def test_simple_question_finishes_in_one_model_request(self):
        runtime = self.runtime()
        service = ScriptService([[('assess_readme', self.proposal())]])
        report = deepseek_agent(runtime, service)
        self.assertEqual(service.attempts, 1)
        self.assertEqual(report['completion']['type'], 'model_submitted')
        self.assertEqual(report['routing']['path'], 'quick')
        self.assertEqual(report['assessments'][0]['status'], 'supported')
        self.assertEqual(report['evidence'][0]['quote'], 'PDF is supported.')

    def test_unknown_escalates_and_shares_request_counter(self):
        runtime = self.runtime()
        service = ScriptService([[('assess_readme', self.proposal('unknown', ''))],
                                 [('submit_report', {'summary': 'unknown', 'assessments': []})]])
        report = deepseek_agent(runtime, service)
        self.assertEqual(service.attempts, 2)
        self.assertEqual(report['routing']['path'], 'quick_then_deep')
        self.assertEqual(report['assessments'][0]['status'], 'unknown')
        self.assertIn('read_documentation', service.allowed[1])

    def test_fabricated_quote_escalates_without_persisting_evidence(self):
        runtime = self.runtime()
        service = ScriptService([[('assess_readme', self.proposal(quote='invented quote'))],
                                 [('submit_report', {'summary': 'unknown', 'assessments': []})]])
        report = deepseek_agent(runtime, service)
        self.assertEqual(report['routing']['reason'], 'invalid_quick_assessment')
        self.assertEqual(report['evidence'], [])

    def test_missing_matrix_cell_escalates(self):
        runtime = self.runtime()
        service = ScriptService([[('assess_readme', {'summary': 'missing', 'assessments': []})],
                                 [('submit_report', {'summary': 'unknown', 'assessments': []})]])
        report = deepseek_agent(runtime, service)
        self.assertEqual(report['routing']['path'], 'quick_then_deep')

    def test_low_budget_makes_no_model_request(self):
        runtime = self.runtime()
        runtime.request.max_tokens = 4000
        service = ScriptService([])
        report = deepseek_agent(runtime, service)
        self.assertEqual(service.attempts, 0)
        self.assertEqual(report['completion']['reason'], 'token_budget')

    def test_resumed_sources_skip_quick_phase(self):
        runtime = self.runtime()
        runtime.read_repository('fixture/quick')
        service = ScriptService([[('submit_report', {'summary': 'unknown', 'assessments': []})]])
        report = deepseek_agent(runtime, service)
        self.assertNotIn('assess_readme', service.allowed[0])
        self.assertEqual(report['routing']['path'], 'deep')

    def test_fast_path_honors_semantic_review(self):
        runtime = self.runtime()
        runtime.request.verify_claims = True
        service = ScriptService([[('assess_readme', self.proposal())]])
        with patch('reposcout.semantic_review.review_report', side_effect=lambda r,s,p:p) as review:
            deepseek_agent(runtime, service)
        review.assert_called_once()

    def test_missing_conditions_escalate(self):
        runtime = self.runtime()
        runtime.case['sources'][0]['text'] = 'PDF requires an extra plugin.'
        service = ScriptService([[('assess_readme', self.proposal(quote='PDF requires an extra plugin.'))],
                                 [('submit_report', {'summary': 'unknown', 'assessments': []})]])
        report = deepseek_agent(runtime, service)
        self.assertEqual(report['routing']['reason'], 'evidence_gap_or_conditions')

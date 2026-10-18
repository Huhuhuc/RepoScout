import unittest
from evals.frozen import FrozenRuntime
from reposcout.spans import segments, resolve
from reposcout.context import snapshot
from reposcout.agent import deepseek_agent
from test_orchestrator import ScriptService


class SpanTests(unittest.TestCase):
    def runtime(self):
        return FrozenRuntime({'id': 'span', 'requirement': 'API', 'sources': [
            {'kind': 'readme', 'path': 'README.md', 'text': 'Supports **sync APIs**.\nAnd async APIs.'}]})

    def test_selection_preserves_exact_markdown_and_newlines(self):
        r = self.runtime(); s = r.read_repository('fixture/span')
        part = snapshot(r, 'research', '', [])['sources'][0]['excerpts'][0]
        e = r.call('save_evidence', {'source_id': s['id'], 'requirement_id': 'R1', 'span_id': part['span_id']})
        self.assertEqual(e['quote'], s['text'])
        self.assertEqual(s['text'][e['start']:e['end']], e['quote'])
        self.assertEqual(e['selection'], 'span')

    def test_invalid_cross_source_or_out_of_range_spans_rejected(self):
        r=self.runtime(); s=r.read_repository('fixture/span')
        for value in ('S2:0:3', 'S1:-1:3', 'S1:0:9999', 'S1:3:3', 'invented'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(s, span_id=value)

    def test_conflicting_quote_and_span_rejected(self):
        r=self.runtime(); s=r.read_repository('fixture/span')
        with self.assertRaises(ValueError): resolve(s, quote='unsupported', span_id='S1:0:8')
        with self.assertRaises(ValueError): resolve(s)

    def test_segments_are_exact_bounded_nonempty(self):
        text='汉字\n**test**'*400
        for part in segments('S1', text[123:2523], 123):
            s={'id':'S1','text':text}
            quote, start=resolve(s, span_id=part['span_id'])
            self.assertEqual(quote,part['text'])
            self.assertEqual(start,part['offset'])
            self.assertTrue(0<len(quote)<=700)

    def test_quick_span_finishes_without_quote_copy(self):
        r=self.runtime(); r.request.strategy='auto'
        args={'summary':'Supported', 'assessments':[{'repository':'fixture/span','requirement_id':'R1',
            'status':'supported','explanation':'README', 'source_id':'S1','span_id':'S1:0:22',
            'evidence_basis':'explicit_statement'}]}
        service=ScriptService([[('assess_readme',args)]])
        report=deepseek_agent(r,service)
        self.assertEqual(service.attempts,1)
        self.assertEqual(report['routing']['path'],'quick')
        self.assertEqual(report['evidence'][0]['quote'],r.sources['S1']['text'][:22])

    def test_malformed_document_links_do_not_abort_snapshot(self):
        from reposcout.official_docs import linked_urls
        r=self.runtime();s=r.read_repository('fixture/span')
        s['text']='https://[bad https://docs.langchain.com:broken/a https://docs.langchain.com/valid'
        self.assertEqual(linked_urls(r,'fixture/span'),['https://docs.langchain.com/valid'])
        self.assertTrue(snapshot(r,'research','',[])['sources'])

    def test_all_real_fixture_readmes_can_build_context(self):
        import json
        from pathlib import Path
        cases=json.loads(Path('evals/multi-repo-cases.json').read_text(encoding='utf-8'))['cases']
        for case in cases:
            with self.subTest(case=case['id']):
                r=FrozenRuntime(case);r.read_repository(r.request.repositories[0])
                self.assertTrue(snapshot(r,'research','',[])['sources'])

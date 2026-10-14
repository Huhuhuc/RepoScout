import unittest

from evals.frozen import load_cases, FrozenRuntime
from evals.run import score


class EvaluationTests(unittest.TestCase):
    def test_twelve_distinct_frozen_cases_and_labels(self):
        cases=load_cases()
        self.assertEqual(len(cases),12)
        self.assertEqual(len({c['id'] for c in cases}),12)
        self.assertEqual({c['expected'] for c in cases},{'supported','unsupported','unknown','conflict'})
        for c in cases:
            self.assertEqual(c['sources'][0]['kind'],'readme')
            for quote in c['accepted']:
                self.assertTrue(any(quote in s['text'] for s in c['sources']))

    def test_source_access_never_fetches_remote_data(self):
        for case in load_cases():
            r=FrozenRuntime(case)
            r.call('read_repository',{'repository':r.request.repositories[0]})
            self.assertEqual(r.http_calls,0)
            self.assertNotIn('expected',r.request.model_dump())
            with self.assertRaises(AssertionError):r.fetch('/anything')

    def test_grader_rejects_hallucinated_quote_and_wrong_status(self):
        case=load_cases()[0]
        good=score(case,'supported',case['accepted'],[case['sources'][0]['text']],True)
        self.assertTrue(good['grounded_correct'])
        bad=score(case,'supported',['made up'],[case['sources'][0]['text']],True)
        self.assertFalse(bad['grounded_correct'])
        self.assertEqual(bad['exact_citations'],0)
        self.assertFalse(score(case,'unsupported',[],[],True)['correct'])

    def test_partial_does_not_count_as_completed(self):
        case=load_cases()[0]
        result=score(case,'supported',case['accepted'],[case['sources'][0]['text']],False)
        self.assertFalse(result['completed'])

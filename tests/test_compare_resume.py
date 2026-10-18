import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from evals.compare import run


class ComparisonResumeTests(unittest.TestCase):
    def test_completed_strategy_is_not_billed_again(self):
        with tempfile.TemporaryDirectory() as folder:
            dataset=Path(folder)/'cases.json'; output=Path(folder)/'result.json'
            dataset.write_text(json.dumps({'cases':[{'id':'one','requirement':'PDF',
                'expected':'supported','accepted':['PDF supported'],
                'sources':[{'kind':'readme','path':'README','text':'PDF supported'}]}]}),encoding='utf-8')
            service=Mock(config=Mock(model='test-model'),attempts=1,usage={'total_tokens':2})
            service.chat.return_value={'tool_calls':[{'function':{'arguments':json.dumps(
                {'status':'supported','quotes':['PDF supported'],'explanation':'test'})}}]}
            with patch('evals.compare.STRATEGIES',('same_sources',)), patch('evals.compare.ModelService',return_value=service) as factory, contextlib.redirect_stdout(io.StringIO()):
                first=run(dataset,output,1,1)
                factory.reset_mock()
                resumed=run(dataset,output,1,1,resume=True)
                factory.assert_not_called()
                self.assertEqual(first['summary'],resumed['summary'])
                with self.assertRaises(ValueError):run(dataset,output,1,1)
                with self.assertRaises(ValueError):run(dataset,output,1,2,resume=True)

    def test_changed_dataset_cannot_mix_with_saved_results(self):
        with tempfile.TemporaryDirectory() as folder:
            dataset=Path(folder)/'cases.json';output=Path(folder)/'result.json'
            dataset.write_text('{"cases":[]}',encoding='utf-8')
            output.write_text('{"dataset_sha256":"wrong"}',encoding='utf-8')
            with self.assertRaises(ValueError):run(dataset,output,1,1,resume=True)

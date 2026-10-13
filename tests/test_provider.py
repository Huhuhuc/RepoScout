import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from reposcout.provider import ModelConfig, ModelError, ModelService, settings
from reposcout.app import app


class ProviderTests(unittest.TestCase):
    def test_dotenv_precedence_and_no_interpolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('DEEPSEEK_API_KEY="test-${HOME}"\nDEEPSEEK_MODEL=test-model\n', encoding='utf-8-sig')
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(settings(path).key, 'test-${HOME}')
                self.assertNotIn('test-${HOME}', repr(settings(path)))
            with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'environment'}):
                self.assertEqual(settings(path).key, 'environment')

    def service(self, handler):
        factory = httpx.Client
        transport = httpx.MockTransport(handler)
        return patch('reposcout.provider.httpx.Client', side_effect=lambda **kw: factory(transport=transport, **kw))

    def test_auth_error_sanitized_not_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(401, json={'error': 'secret-do-not-echo'})
        with self.service(handler):
            with self.assertRaises(ModelError) as caught:
                ModelService(ModelConfig('test-key')).test_connection()
        self.assertNotIn('secret', str(caught.exception))
        self.assertEqual(len(calls), 1)

    def test_retry_and_model_list_only(self):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429)
            return httpx.Response(200, json={'data': [{'id': 'test-model'}]})
        with self.service(handler), patch('reposcout.provider.time.sleep'):
            result = ModelService(ModelConfig('test-key','test-model')).test_connection()
        self.assertTrue(result['model_available'])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(r.method == 'GET' and r.url.path == '/models' for r in calls))

    def test_malformed_response(self):
        for response in (httpx.Response(200,json={'choices': []}), httpx.Response(200,text='invalid json')):
            with self.service(lambda _: response):
                with self.assertRaises(ModelError):
                    ModelService(ModelConfig('test-key')).chat([], [])

    def test_network_failure_not_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout('sensitive-upstream-details')
        with self.service(handler):
            with self.assertRaises(ModelError) as caught:
                ModelService(ModelConfig('test-key')).chat([], [])
        self.assertEqual(len(calls), 1)
        self.assertNotIn('sensitive', str(caught.exception))

    def test_usage_and_request_budget(self):
        with self.service(lambda _: httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'}}],
                'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}})):
            service = ModelService(ModelConfig('test-key'))
            service.chat([],[])
            self.assertEqual(service.usage['total_tokens'],12)
            service.attempts=12
            with self.assertRaises(TimeoutError):
                service.chat([],[])

    def test_status_api_never_returns_secret(self):
        with patch('reposcout.app.settings', return_value=ModelConfig('private-test-value','test-model')):
            response = TestClient(app).get('/api/model/config')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['configured'])
        self.assertNotIn('private-test-value',response.text)

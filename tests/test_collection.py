import base64
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import httpx

from reposcout.agent import github_agent, markdown
from reposcout.tools import Runtime
from reposcout.models import TaskRequest, Requirement


class CollectionTests(unittest.TestCase):
    def runtime(self):
        runtime = Runtime(TaskRequest(question='research agents', mode='github',
            repositories=['a/b'], requirements=[Requirement(id='R1', text='local')]), lambda: None, lambda *a: None)
        runtime.contexts['a/b'] = ({'default_branch': 'main'}, 'commit123')
        return runtime

    def test_document_pinned_cached_and_quotable(self):
        r = self.runtime()
        r.fetch = Mock(return_value={'type': 'file', 'encoding': 'base64', 'sha': 'blob123',
            'content': base64.b64encode(b'Local deployment is supported.').decode()})
        source = r.call('read_document', {'repository': 'a/b', 'path': 'docs/install.md'})
        self.assertIn('ref=commit123', r.fetch.call_args.args[0])
        self.assertIn('/blob/commit123/', source['url'])
        self.assertEqual(source, r.read_document('a/b', 'docs/install.md'))
        self.assertEqual(r.fetch.call_count, 1)
        evidence = r.save_evidence(source['id'], 'R1', 'Local deployment')
        self.assertEqual(evidence['start'], 0)

    def test_document_paths_reject_traversal_and_code(self):
        r = self.runtime()
        r.fetch = Mock()
        for path in ('../secret.md', '/docs/a.md', 'docs/../a.md', 'main.py', 'docs\\a.md'):
            with self.assertRaises(ValueError):
                r.read_document('a/b', path)
        r.fetch.assert_not_called()

    def test_issue_scope_and_provenance(self):
        r = self.runtime()
        r.fetch = Mock(return_value={'items': [
            {'title': 'Local fails', 'body': 'User report', 'html_url': 'https://github.com/a/b/issues/1',
             'repository_url': 'https://api.github.com/repos/a/b', 'state': 'closed', 'updated_at': '2026-01-01'},
            {'pull_request': {}, 'repository_url': 'https://api.github.com/repos/a/b'},
            {'repository_url': 'https://api.github.com/repos/other/repo'}]})
        result = r.search_issues('a/b', 'local repo:other/repo is:pr')
        query = parse_qs(urlsplit(r.fetch.call_args.args[0]).query)['q'][0]
        self.assertEqual(query.count('repo:'), 1)
        self.assertEqual(len(result['source_ids']), 1)
        source = r.sources['S1']
        self.assertEqual(source['metadata']['state'], 'closed')
        self.assertFalse(source['metadata']['comments_included'])

    def test_empty_releases_not_unsupported(self):
        r = self.runtime()
        r.fetch = Mock(return_value=[])
        self.assertEqual(r.read_releases('a/b')['status'], 'empty')
        self.assertFalse(r.sources)

    def test_partial_collection_preserves_readme(self):
        r = self.runtime()
        def call(name, args):
            if name == 'read_repository':
                r.repositories.append('a/b')
                return r.add_source('a/b', 'readme', 'README', 'https://github.com/a/b', 'hello')
            raise httpx.ConnectError('offline')
        r.call = call
        report = github_agent(r)
        self.assertEqual(len(report['sources']), 1)
        self.assertEqual(len(report['collections']), 3)
        self.assertEqual(report['assessments'][0]['status'], 'unknown')
        self.assertIn('https://github.com/a/b', markdown(report))

    def test_document_discovery_bounded(self):
        r = self.runtime()
        paths = []
        def fetch(path):
            paths.append(path)
            if '/contents/docs/guide.md?' in path:
                return {'type': 'file', 'encoding': 'base64', 'sha': 'x', 'content': 'aGk='}
            if '/contents/docs?' in path:
                return [{'type': 'file', 'path': 'docs/guide.md'}]
            return []
        r.fetch = fetch
        result = r.read_documentation('a/b')
        self.assertEqual(len(result['source_ids']), 1)
        self.assertEqual(len(paths), 3)

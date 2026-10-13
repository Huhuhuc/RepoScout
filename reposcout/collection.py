"""Bounded GitHub collection; repository content is data, never instructions."""
import base64
import hashlib
from urllib.parse import quote, urlencode

import httpx

from .store import now


class CollectionMixin:
    def repository_context(self, repository):
        from .tools import normalize_repository
        repository = normalize_repository(repository)
        if self.request.mode == 'demo':
            raise ValueError('扩展采集仅用于真实 GitHub 仓库')
        if repository not in self.repositories:
            if len(self.repositories) >= 3:
                raise ValueError('最多调查三个候选仓库')
            self.repositories.append(repository)
        if repository not in self.contexts:
            metadata = self.fetch('/repos/' + repository)
            commit = self.fetch('/repos/' + repository + '/commits/' + quote(metadata['default_branch'], safe=''))
            self.contexts[repository] = (metadata, commit['sha'])
        return repository, self.contexts[repository]

    def add_source(self, repository, kind, title, url, text, ref=None, sha=None, metadata=None):
        existing = next((s for s in self.sources.values() if s['url'] == url), None)
        if existing:
            return existing
        source = dict(id='S' + str(len(self.sources) + 1), repository=repository,
                      kind=kind, title=title, url=url, text=text[:60000],
                      fetched_at=now(), ref=ref, sha=sha, demo=False,
                      truncated=len(text) > 60000, metadata=metadata or {},
                      hash=hashlib.sha256(text[:60000].encode()).hexdigest())
        self.sources[source['id']] = source
        self.emit('source', source)
        return source

    def collection_result(self, repository, kind, sources, error=None):
        record = dict(repository=repository, kind=kind,
                      status=('partial' if sources else 'failed') if error else 'collected' if sources else 'empty',
                      source_ids=[s['id'] for s in sources], error=error)
        self.collections.append(record)
        self.emit('collection', record)
        return record

    def read_document(self, repository, path):
        if (path.startswith('/') or '\\' in path or
                any(p in ('', '.', '..') for p in path.split('/')) or
                not path.lower().endswith(('.md', '.mdx', '.rst', '.txt'))):
            raise ValueError('只支持仓库内的 Markdown、RST、TXT 文档路径')
        repository, (_, ref) = self.repository_context(repository)
        url = f'https://github.com/{repository}/blob/{ref}/{quote(path, safe="/")}'
        existing = next((s for s in self.sources.values() if s['url'] == url), None)
        if existing:
            return existing
        data = self.fetch(f'/repos/{repository}/contents/{quote(path, safe="/")}?' + urlencode({'ref': ref}))
        if not isinstance(data, dict) or data.get('type') != 'file' or data.get('encoding') != 'base64':
            raise ValueError('文档不是可读取的普通文本文件')
        text = base64.b64decode(data['content']).decode('utf-8', errors='replace')
        return self.add_source(repository, 'documentation', path, url, text, ref, data.get('sha'),
                               {'authority': 'repository-maintained'})

    def read_documentation(self, repository):
        repository, (_, ref) = self.repository_context(repository)
        collected, paths, errors = [], [], []
        # A bounded directory walk avoids downloading a huge recursive repository tree.
        pending = ['', 'docs']
        visited = set()
        while pending and len(visited) < 4:
            directory = pending.pop(0)
            if directory in visited:
                continue
            visited.add(directory)
            try:
                entries = self.fetch(f'/repos/{repository}/contents/{quote(directory, safe="/")}?' + urlencode({'ref': ref}))
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404 and directory == 'docs':
                    continue
                errors.append(f'{directory or "/"}: {type(error).__name__}')
                continue
            if not isinstance(entries, list):
                continue
            entries.sort(key=lambda item: (item['path'].split('/')[-1] not in ('docs', 'getting-started', 'introduction', 'guides'), item['path']))
            for item in entries:
                path = item['path']
                if item['type'] == 'dir' and directory and len(pending) < 4:
                    pending.append(path)
                if item['type'] == 'file' and path.lower().endswith(('.md', '.mdx', '.rst', '.txt')):
                    if directory or any(word in path.lower() for word in ('install', 'usage', 'guide', 'deploy')):
                        paths.append(path)
        paths.sort(key=lambda p: (not any(w in p.lower() for w in ('install', 'quickstart', 'deploy', 'usage')), len(p), p))
        for path in paths[:3]:
            try:
                collected.append(self.read_document(repository, path))
            except (ValueError, httpx.HTTPError) as error:
                errors.append(f'{path}: {type(error).__name__}')
        result = self.collection_result(repository, 'documentation', collected, '; '.join(errors) or None)
        result['discovered_paths'] = paths[:30]
        result['coverage'] = '最多扫描四个目录、读取三篇仓库维护文档；未抓取外部文档网站'
        return result

    def read_releases(self, repository):
        repository, _ = self.repository_context(repository)
        items = self.fetch(f'/repos/{repository}/releases?per_page=3')
        sources = []
        for item in items:
            text = (item.get('name') or item['tag_name']) + '\n\n' + (item.get('body') or '')
            sources.append(self.add_source(repository, 'release', item['tag_name'], item['html_url'], text,
                item['tag_name'], metadata={k: item.get(k) for k in ('published_at', 'prerelease', 'draft', 'target_commitish')}))
        return self.collection_result(repository, 'release', sources)

    def search_issues(self, repository, query=''):
        repository, _ = self.repository_context(repository)
        # Strip search operators so model-provided text cannot escape repository scope.
        import re
        terms = re.findall(r'[\w-]+', query, re.UNICODE)[:12]
        params = {'q': f'repo:{repository} is:issue ' + ' '.join(terms),
                  'sort': 'updated', 'order': 'desc', 'per_page': 3}
        data = self.fetch('/search/issues?' + urlencode(params))
        sources = []
        for item in data['items']:
            if 'pull_request' in item or item.get('repository_url', '').lower() != f'https://api.github.com/repos/{repository}'.lower():
                continue
            text = item['title'] + '\n\n' + (item.get('body') or '')
            sources.append(self.add_source(repository, 'issue', item['title'], item['html_url'], text,
                metadata={**{k: item.get(k) for k in ('number', 'state', 'created_at', 'updated_at', 'closed_at')},
                          'authority': 'community-report-not-verified', 'comments_included': False}))
        return self.collection_result(repository, 'issue', sources,
            '搜索结果不完整' if data.get('incomplete_results') else None)

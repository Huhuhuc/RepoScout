import hashlib
import os
import re
import time
import httpx
from .store import now
from .collection import CollectionMixin
from .research import ResearchMixin

DEMO = {
    'demo/AtlasKB': 'AtlasKB 示例资料（虚构）。支持本地部署。支持 PDF 导入。回答包含来源引用。',
    'demo/PaperNest': 'PaperNest 示例资料（虚构）。支持本地部署。不支持 PDF 导入。回答包含来源引用。',
    'demo/CloudShelf': 'CloudShelf 示例资料（虚构）。仅提供云端服务，不支持本地部署。支持 PDF 导入。',
}


def normalize_repository(value):
    value = value.strip().removesuffix('.git').rstrip('/')
    value = re.sub(r'^https://github\.com/', '', value)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('仓库必须是 owner/repo 或完整 GitHub 仓库链接')
    if any(part in ('.','..') for part in value.split('/')):
        raise ValueError('无效仓库路径')
    return value


class Runtime(CollectionMixin, ResearchMixin):
    def __init__(self, request, check, emit):
        self.request, self.check, self.emit = request, check, emit
        self.sources, self.evidence, self.repositories = {}, {}, []
        self.contexts, self.collections = {}, []
        self.reviews, self.followups = [], []
        self.read_cache = {}
        self.cache_hits = 0
        self.calls = self.http_calls = 0
        self.started = time.monotonic()
        self.headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'RepoScout/0.1'}
        token = os.getenv('GITHUB_TOKEN')
        if token:
            self.headers['Authorization'] = 'Bearer ' + token

    def guard(self):
        self.check()
        if time.monotonic() - self.started > 300:
            raise TimeoutError('任务达到 5 分钟上限')

    def fetch(self, path, raw=False):
        self.guard()
        if self.http_calls >= 60:
            raise TimeoutError('网络请求预算已耗尽')
        self.http_calls += 1
        headers = {**self.headers, 'Accept': 'application/vnd.github.raw+json'} if raw else self.headers
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=True) as client:
            with client.stream('GET', 'https://api.github.com' + path, headers=headers) as response:
                if response.status_code in (403,429):
                    raise ValueError('GitHub 限流或拒绝访问；可稍后重试或配置 GITHUB_TOKEN。')
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    self.guard()
                    content.extend(chunk)
                    if len(content) > 1_000_000:
                        raise ValueError('资料超过 1 MB 下载上限')
                if raw:
                    return bytes(content).decode('utf-8', errors='replace')[:60000]
                import json
                return json.loads(content)

    def search_repositories(self, query):
        if self.request.mode == 'demo':
            found = list(DEMO)
        else:
            from urllib.parse import urlencode
            data = self.fetch('/search/repositories?' + urlencode({'q': query, 'per_page': 3}))
            found = [item['full_name'] for item in data['items']]
            if data.get('incomplete_results'):
                self.emit('warning', {'message': 'GitHub 返回的搜索结果可能不完整'})
        for repo in found:
            if repo not in self.repositories and len(self.repositories) < 3:
                self.repositories.append(repo)
        return {'repositories': self.repositories, 'coverage': '最多三个候选，非全网覆盖'}

    def read_repository(self, repository):
        repository = normalize_repository(repository)
        if repository not in self.repositories:
            if len(self.repositories) >= 3:
                raise ValueError('最多调查三个候选仓库')
            self.repositories.append(repository)
        existing = next((s for s in self.sources.values() if s['repository'] == repository and s.get('kind') == 'readme'), None)
        if existing:
            return existing
        if self.request.mode == 'demo':
            if repository not in DEMO:
                raise ValueError('演示模式仅提供内置的三个虚构仓库')
            text, ref, sha = DEMO[repository], 'fixture-v1', None
            metadata = {'description': '虚构评测样例', 'archived': False, 'license': None}
        else:
            repository, (metadata, ref) = self.repository_context(repository)
            from urllib.parse import urlencode
            readme = self.fetch('/repos/' + repository + '/readme?' + urlencode({'ref': ref}))
            sha = readme.get('sha')
            if readme.get('encoding') != 'base64' or not readme.get('content'):
                raise ValueError('README 超过当前支持大小或无可读取正文')
            import base64
            text = base64.b64decode(readme['content']).decode('utf-8', errors='replace')
            truncated = len(text) > 60000
            text = text[:60000]
        ident = 'S' + str(len(self.sources) + 1)
        source = {'id': ident, 'repository': repository, 'kind': 'readme', 'title': 'README', 'url': 'https://github.com/' + repository if self.request.mode == 'demo' else readme['html_url'],
                  'fetched_at': now(), 'ref': ref, 'sha': sha, 'text': text,
                  'hash': hashlib.sha256(text.encode()).hexdigest(), 'demo': self.request.mode == 'demo',
                  'truncated': False if self.request.mode == 'demo' else truncated,
                  'metadata': {k: metadata.get(k) for k in ('description','archived','license','pushed_at','stargazers_count')}}
        self.sources[ident] = source
        self.emit('source', source)
        return source

    def save_evidence(self, source_id, requirement_id, quote):
        source = self.sources.get(source_id)
        if not source:
            raise ValueError('来源不存在')
        if requirement_id not in {r.id for r in self.request.requirements}:
            raise ValueError('需求不存在')
        offset = source['text'].find(quote)
        if offset < 0:
            raise ValueError('摘录必须完整存在于已读取原文')
        old = next((e for e in self.evidence.values() if e['source_id'] == source_id and e['requirement_id'] == requirement_id and e['quote'] == quote), None)
        if old:
            return old
        ident = 'E' + str(len(self.evidence) + 1)
        evidence = {'id': ident, 'source_id': source_id, 'requirement_id': requirement_id, 'quote': quote, 'start': offset, 'end': offset + len(quote)}
        self.evidence[ident] = evidence
        self.emit('evidence', evidence)
        return evidence

    def read_source(self, source_id, offset=0, query=''):
        source = self.sources.get(source_id)
        if not source:
            raise ValueError('来源不存在')
        if query:
            found = source['text'].lower().find(query.lower())
            if found < 0:
                return {'source_id': source_id, 'found': False, 'total_chars': len(source['text'])}
            offset = max(0, found - 150)
        return {'source_id': source_id, 'offset': offset, 'text': source['text'][offset:offset+2400],
                'total_chars': len(source['text']), 'next_offset': min(offset+2400, len(source['text']))}

    def call(self, name, args):
        self.guard()
        if self.calls >= self.request.max_tools:
            raise TimeoutError('工具调用预算已耗尽')
        self.calls += 1
        from .models import SearchArgs, RepositoryArgs, EvidenceArgs, DocumentArgs, IssueArgs, ReportArgs, FollowupArgs, SourceSliceArgs
        schemas = {'search_repositories': SearchArgs, 'read_repository': RepositoryArgs, 'save_evidence': EvidenceArgs,
                   'read_documentation': RepositoryArgs, 'read_document': DocumentArgs,
                   'read_releases': RepositoryArgs, 'search_issues': IssueArgs,
                   'review_evidence': ReportArgs, 'investigate_gaps': FollowupArgs, 'read_source': SourceSliceArgs}
        if name not in schemas:
            raise ValueError('未知工具')
        parsed = schemas[name].model_validate(args).model_dump()
        self.emit('action', {'tool': name, 'arguments': parsed, 'calls': self.calls})
        import json
        import copy
        key = name + json.dumps(parsed, sort_keys=True, ensure_ascii=False)
        cacheable = name in ('read_repository', 'read_documentation', 'read_document', 'read_releases', 'search_issues', 'read_source')
        if cacheable and key in self.read_cache:
            self.cache_hits += 1
            self.emit('cache_hit', {'tool': name, 'message': '复用本任务已获取的相同查询结果'})
            return copy.deepcopy(self.read_cache[key])
        result = getattr(self, name)(**parsed)
        if cacheable:
            self.read_cache[key] = copy.deepcopy(result)
        return result

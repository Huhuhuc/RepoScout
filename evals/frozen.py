import json
from pathlib import Path

from reposcout.models import TaskRequest, Requirement
from reposcout.tools import Runtime

DATASET = Path(__file__).with_name('cases.json')


def load_cases():
    return json.loads(DATASET.read_text(encoding='utf-8'))['cases']


class FrozenRuntime(Runtime):
    def __init__(self, case):
        self.case = case
        self.events = []
        request = TaskRequest(question='调查冻结样例：'+case['requirement'],
            requirements=[Requirement(id='R1',text=case['requirement'])],
            repositories=['fixture/'+case['id']], mode='deepseek', max_tools=16)
        super().__init__(request, lambda: None, lambda kind,payload:self.events.append({'kind':kind,'payload':payload}))

    def fetch(self, *args, **kwargs):
        raise AssertionError('冻结评测禁止外部资料网络访问')

    def add(self, item):
        repo=self.request.repositories[0]
        if repo not in self.repositories:self.repositories.append(repo)
        return self.add_source(repo,item['kind'],item['path'],f'https://example.invalid/{self.case["id"]}/{item["path"]}',
                               item['text'],ref='frozen-v1',metadata={'synthetic':True})

    def read_repository(self, repository):
        self.check_repo(repository)
        return self.add(self.case['sources'][0])

    def check_repo(self, repository):
        if repository != self.request.repositories[0]:raise ValueError('只允许当前冻结样例仓库')

    def read_documentation(self, repository):
        self.check_repo(repository)
        if self.case.get('docs_failure'):raise ValueError('冻结样例：文档服务不可用')
        sources=[self.add(s) for s in self.case['sources'] if s['kind']=='documentation']
        return self.collection_result(repository,'documentation',sources)

    def read_document(self, repository, path):
        self.check_repo(repository)
        if self.case.get('docs_failure'):raise ValueError('冻结样例：文档服务不可用')
        item=next((s for s in self.case['sources'] if s['path']==path),None)
        if not item:raise ValueError('冻结资料中不存在该路径')
        return self.add(item)

    def read_releases(self, repository):
        self.check_repo(repository)
        return self.collection_result(repository,'release',[self.add(s) for s in self.case['sources'] if s['kind']=='release'])

    def search_issues(self, repository, query=''):
        self.check_repo(repository)
        return self.collection_result(repository,'issue',[self.add(s) for s in self.case['sources'] if s['kind']=='issue'])

    def search_repositories(self, query):
        self.repositories=list(self.request.repositories)
        return {'repositories':self.repositories}

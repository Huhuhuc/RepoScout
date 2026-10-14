"""Read-only real GitHub smoke check. No model calls or publication."""
import json
from pathlib import Path
import httpx
from reposcout.models import TaskRequest, Requirement
from reposcout.tools import Runtime
from reposcout.store import now


def main():
    runtime = Runtime(TaskRequest(question='local deep researcher', mode='github',
        requirements=[Requirement(id='R1', text='local deployment')]), lambda: None, lambda *args: None)
    found = runtime.call('search_repositories', {'query': 'local-deep-researcher in:name'})['repositories']
    rows = []
    for repo in found:
        metadata = runtime.fetch('/repos/' + repo)
        source = runtime.call('read_repository', {'repository': repo})
        rows.append({'repository': repo, 'verified': metadata['full_name'].lower() == repo.lower(),
            'url': metadata['html_url'], 'github_id': metadata['id'], 'private': metadata['private'],
            'readme_chars': len(source['text']), 'source_url': source['url'], 'commit': source['ref']})
    invalid = 'Huhuhuc/reposcout-does-not-exist-20261014-725d9a'
    try:
        runtime.fetch('/repos/' + invalid)
        negative = {'repository': invalid, 'rejected': False}
    except httpx.HTTPStatusError as error:
        negative = {'repository': invalid, 'rejected': error.response.status_code == 404,
                    'status': error.response.status_code}
    result = {'checked_at': now(), 'query': 'local-deep-researcher in:name',
              'repositories': rows, 'negative_control': negative, 'http_requests': runtime.http_calls}
    assert rows and all(row['verified'] and row['readme_chars'] for row in rows)
    assert negative['rejected']
    Path('docs/github-live-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()

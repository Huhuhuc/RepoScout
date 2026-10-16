"""Offline integrity checks; this does not validate semantic labels."""
import hashlib
import json
import sys
from pathlib import Path


def validate(path):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))['cases']
    seen = set()
    for case in cases:
        if case['id'] in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case['id'])
        if case['expected'] not in ('supported', 'unsupported', 'unknown', 'conflict'):
            raise ValueError('Invalid expected status')
        if not case['sources'] or case['sources'][0]['kind'] != 'readme':
            raise ValueError('First source must be README')
        for source in case['sources']:
            if hashlib.sha256(source['text'].encode()).hexdigest() != source['sha256']:
                raise ValueError('Source hash mismatch: ' + case['id'])
            if f"/{source['ref']}/" not in source['url'] or len(source['ref']) != 40:
                raise ValueError('Source must be pinned to a full commit')
            if not source.get('fetched_at'):
                raise ValueError('Missing capture time')
        if case['expected'] != 'unknown' and not case['accepted']:
            raise ValueError('Determinate labels need evidence')
        for quote in case['accepted']:
            if not any(quote and quote in s['text'] for s in case['sources']):
                raise ValueError('Label quote is not in sources: ' + case['id'])
    return cases


if __name__ == '__main__':
    cases = validate(sys.argv[1])
    print(json.dumps({'cases': len(cases), 'repositories': len({c['repository'] for c in cases}),
                      'integrity': 'passed', 'model_calls': 0}))

"""Serializable task state; no provider configuration or credentials."""
import copy

FIELDS = ('sources', 'evidence', 'repositories', 'contexts', 'collections', 'reviews',
          'followups', 'read_cache', 'query_counts')


def dump(runtime):
    return {'version': 1, 'state': {key: copy.deepcopy(getattr(runtime, key)) for key in FIELDS},
            'read_windows': list(runtime.read_windows), 'metrics': getattr(runtime, 'model_metrics', {})}


def restore(runtime, data):
    if data.get('version') != 1:
        raise ValueError('检查点版本不兼容')
    for key in FIELDS:
        setattr(runtime, key, copy.deepcopy(data['state'][key]))
    runtime.read_windows = {tuple(item) for item in data.get('read_windows', [])}
    # A failed round can be retried with a distinct query in a new run.
    runtime.prior_metrics = data.get('metrics', {})
    if runtime.followups and runtime.reviews and runtime.followups[-1]['review_index'] == len(runtime.reviews):
        stale = {(a['repository'], a['requirement_id']) for a in runtime.followups[-1]['actions']}
        for assessment in runtime.reviews[-1]['assessments']:
            if (assessment['repository'], assessment['requirement_id']) in stale:
                assessment.update(status='unknown', evidence_ids=[], evidence_basis='uncertain', explanation='上次补查后尚未复核，继续调查时重新确认')
        from .research import gaps_for
        runtime.reviews[-1]['gaps'] = gaps_for(runtime, runtime.reviews[-1]['assessments'])
    runtime.followups = []
    runtime.reviews = runtime.reviews[-1:]
    runtime.query_counts = {}

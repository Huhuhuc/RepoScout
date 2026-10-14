"""Bounded model views; complete source text remains in local task storage."""
import json
import re


def excerpts(source, request):
    text = source['text']
    terms = set(re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{2,}', request.question + ' '.join(r.text for r in request.requirements)))
    terms = sorted(terms, key=lambda term: (-len(term), term))[:16]
    pieces = [{'offset': 0, 'text': text[:1400]}]
    for term in terms:
        at = text.lower().find(term.lower(), 1400)
        if at < 0 or any(abs(at-p['offset']) < 400 for p in pieces):
            continue
        start = max(0, at-100)
        pieces.append({'offset': start, 'text': text[start:start+700]})
        if len(pieces) >= 3:
            break
    return pieces


def snapshot(runtime, phase, reason, previous):
    sources, remaining = [], 10000
    for source in runtime.sources.values():
        entry = {k: source.get(k) for k in ('id','repository','kind','title','ref')}
        entry['total_chars'] = len(source['text'])
        entry['excerpts'] = []
        for piece in excerpts(source, runtime.request):
            if remaining <= 0:
                break
            snippet = piece['text'][:remaining]
            entry['excerpts'].append({'offset': piece['offset'], 'text': snippet})
            remaining -= len(snippet)
        entry['full_text_tool'] = 'read_source(source_id, offset 或 query)'
        sources.append(entry)
    return {
        'task': runtime.request.model_dump(), 'phase': phase, 'stop_reason': reason,
        'budget': {'tools_remaining': runtime.request.max_tools-runtime.calls,
                   'followups_remaining': 2-len(runtime.followups)},
        'sources': sources, 'evidence': list(runtime.evidence.values()),
        'latest_review': runtime.reviews[-1] if runtime.reviews else None,
        'followups': [{'round': f['index'], 'actions': [
            {k:a.get(k) for k in ('repository','requirement_id','query','document_path','status','source_ids','error')}
            for a in f['actions']]} for f in runtime.followups],
        'last_tool_results': previous,
    }


def compact_result(name, output):
    if isinstance(output, dict) and 'text' in output and 'repository' in output:
        return {k: output.get(k) for k in ('id','repository','kind','title','ref')}
    encoded = json.dumps(output, ensure_ascii=False)
    if len(encoded) <= 5000:
        return output
    return {'preview': encoded[:4500], 'truncated': True, 'note': '完整资料已存储，使用 read_source 分段读取。'}

"""Transparent structural checks, never a claim of semantic proof."""
from .context import terms_for


def inspect_claims(runtime, assessments):
    requirements = {r.id: r.text for r in runtime.request.requirements}
    checks = []
    for claim in assessments:
        evidence = [runtime.evidence[e] for e in claim['evidence_ids']]
        sources = [runtime.sources[e['source_id']] for e in evidence]
        quotes = ' '.join(e['quote'] for e in evidence).casefold()
        versions = sorted({s['ref'] for s in sources if s.get('ref')})
        warnings = []
        if len(versions) > 1:
            warnings.append('引用涉及多个 ref，需确认不是版本变化造成的表面冲突')
        if sources and not claim.get('applicable_version'):
            warnings.append('尚未声明结论适用版本')
        if any(word in quotes for word in ('only', 'except', 'requires', '仅', '需要', '限制', 'enterprise')) and not claim.get('conditions'):
            warnings.append('原文可能有适用条件，尚未填写条件说明')
        terms = terms_for(requirements[claim['requirement_id']])
        if evidence and terms and not any(term.casefold() in quotes for term in terms):
            warnings.append('摘录未命中需求词，需检查是否真正相关；跨语言表述可能误报')
        checks.append({'repository': claim['repository'], 'requirement_id': claim['requirement_id'],
            'quote_match': all(e['quote'] in s['text'] for e,s in zip(evidence,sources)) if evidence else None,
            'has_repository_source': any(s['kind'] != 'issue' for s in sources),
            'source_refs': versions, 'applicable_version': claim.get('applicable_version',''),
            'conditions': claim.get('conditions',''), 'semantic_support': 'needs_review', 'warnings': warnings})
    return checks

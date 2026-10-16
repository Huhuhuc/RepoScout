"""One-pass README assessment; uncertain results enter normal investigation."""
import httpx
from pydantic import BaseModel, Field
from .models import Assessment, ReportArgs


class QuickClaim(Assessment):
    source_id: str
    quote: str = Field(default='', max_length=1200)


class QuickReport(BaseModel):
    assessments: list[QuickClaim]
    summary: str = Field(max_length=3000)


def prepare(runtime):
    eligible = (runtime.request.strategy == 'auto' and runtime.request.repositories
                and len(runtime.request.requirements) <= 3 and not runtime.sources
                and runtime.request.max_tools >= len(runtime.request.repositories) *
                    (1 + len(runtime.request.requirements)) + 4)
    runtime.routing = {'requested': runtime.request.strategy, 'path': 'deep',
                       'reason': 'explicit_deep_or_complex_or_resumed'}
    if not eligible:
        return False
    for repo in runtime.request.repositories:
        try:
            runtime.call('read_repository', {'repository': repo})
            runtime.checkpoint()
        except (ValueError, httpx.HTTPError):
            runtime.routing['reason'] = 'readme_unavailable'
            return False
    runtime.routing.update(path='quick', reason='readme_first')
    runtime.emit('phase', {'message': '先核查 README；证据不足时自动深入调查'})
    return True


def assess(runtime, args):
    from .agent import validate_report
    proposed = QuickReport.model_validate(args)
    expected = {(repo, r.id) for repo in runtime.request.repositories for r in runtime.request.requirements}
    keys = [(a.repository, a.requirement_id) for a in proposed.assessments]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError('快速判断必须完整覆盖所有候选和条件，且不可重复')
    # Validate every quote before any evidence is persisted.
    for claim in proposed.assessments:
        source = runtime.sources.get(claim.source_id)
        if not source or source['repository'] != claim.repository or source['kind'] != 'readme':
            raise ValueError('快速判断来源必须是当前候选的 README')
        if claim.quote and claim.quote not in source['text']:
            raise ValueError('快速判断摘录不属于来源原文')
        if claim.status in ('supported', 'unsupported') and (not claim.quote or claim.evidence_basis != 'explicit_statement'):
            raise ValueError('确定性快速判断必须包含明确原文依据')
        if claim.status == 'conflict':
            raise ValueError('冲突需要多来源深入调查')
    assessments = []
    for claim in proposed.assessments:
        source = runtime.sources[claim.source_id]
        evidence = [runtime.call('save_evidence', {'source_id': claim.source_id,
                    'requirement_id': claim.requirement_id, 'quote': claim.quote})['id']] if claim.quote else []
        values = claim.model_dump(exclude={'source_id', 'quote', 'evidence_ids'})
        values.update(evidence_ids=evidence, applicable_version=source['ref'])
        assessments.append(Assessment(**values))
    report_args = ReportArgs(assessments=assessments, summary=proposed.summary)
    report = validate_report(runtime, report_args)
    if report['research']['gaps'] or any(c['warnings'] for c in report['verification']):
        runtime.review_evidence(assessments, proposed.summary)
        runtime.routing.update(path='quick_then_deep', reason='evidence_gap_or_conditions')
        runtime.emit('phase', {'message': '快速核查仍有缺口或条件待确认，进入深入调查'})
        return None
    runtime.stop_reason = 'readme_evidence_ready'
    return report_args

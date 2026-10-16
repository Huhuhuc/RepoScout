"""Evidence-gap tracking and bounded, auditable follow-up collection."""
import copy
import re

import httpx


def gaps_for(runtime, assessments):
    gaps = []
    for item in assessments:
        kinds = {runtime.sources[runtime.evidence[e]['source_id']].get('kind', 'readme')
                 for e in item['evidence_ids']}
        reason = ('conflict' if item['status'] == 'conflict' else
                  'missing_evidence' if not kinds else
                  'community_only' if kinds == {'issue'} else
                  'unresolved' if item['status'] == 'unknown' else None)
        if reason:
            gaps.append(dict(repository=item['repository'], requirement_id=item['requirement_id'],
                             reason=reason, status=item['status']))
    order = {r.id: not r.mandatory for r in runtime.request.requirements}
    return sorted(gaps, key=lambda g: order[g['requirement_id']])


def research_state(runtime, assessments):
    initial = runtime.reviews[0]['assessments'] if runtime.reviews else []
    before = {(a['repository'], a['requirement_id']): a for a in initial}
    changes = []
    for item in assessments:
        old = before.get((item['repository'], item['requirement_id']))
        if old and (old['status'], old['evidence_ids']) != (item['status'], item['evidence_ids']):
            changes.append(dict(repository=item['repository'], requirement_id=item['requirement_id'],
                                before=old['status'], after=item['status'], evidence_ids=item['evidence_ids']))
    return dict(gaps=gaps_for(runtime, assessments), changes=changes,
                reviews=copy.deepcopy(runtime.reviews), followups=copy.deepcopy(runtime.followups),
                rounds_used=len(runtime.followups), rounds_limit=runtime.request.max_followups)


class ResearchMixin:
    def review_evidence(self, assessments, summary):
        from .agent import validate_report
        from .models import ReportArgs
        report = validate_report(self, ReportArgs(assessments=assessments, summary=summary))
        if not report['assessments']:
            raise ValueError('请先读取候选资料，再检查证据缺口')
        review = dict(index=len(self.reviews) + 1, assessments=report['assessments'],
                      gaps=gaps_for(self, report['assessments']), summary=summary)
        self.reviews.append(copy.deepcopy(review))
        self.emit('review', dict(message=f"第 {review['index']} 次证据检查：{len(review['gaps'])} 个缺口", **review))
        return dict(gaps=review['gaps'], followup_rounds_remaining=self.request.max_followups-len(self.followups),
                    instruction='对缺口调用 investigate_gaps；新资料不是证据，请准确摘录后更新矩阵。')

    def investigate_gaps(self, targets):
        if not self.reviews:
            raise ValueError('必须先调用 review_evidence 保存初步矩阵')
        if len(self.followups) >= self.request.max_followups:
            raise ValueError('已达到两轮补查上限；未解决项应保留 unknown 或 conflict')
        if self.followups and self.followups[-1]['review_index'] == len(self.reviews):
            raise ValueError('每轮补查后必须先更新 review_evidence')
        allowed = {(g['repository'], g['requirement_id']) for g in self.reviews[-1]['gaps']}
        signatures, keys = [], set()
        prior = {tuple(a['signature']) for round_ in self.followups for a in round_['actions']}
        for target in targets:
            key = (target['repository'], target['requirement_id'])
            if key not in allowed:
                raise ValueError('该 repository + requirement_id 不在最近一次检查的缺口列表中')
            if key in keys:
                raise ValueError(f'同一目标 {key[0]} / {key[1]} 重复出现；请只保留一个 target，将关键词合并到其 query 字段')
            keys.add(key)
            query = ' '.join(re.findall(r'[\w-]+', target['query'].casefold()))
            if not query:
                raise ValueError('补查关键词不可为空')
            signature = (*key, query, target.get('document_path'))
            if signature in prior:
                raise ValueError('相同查询已补查，请调整关键词或文档路径')
            signatures.append(signature)
        round_ = dict(index=len(self.followups)+1, review_index=len(self.reviews), actions=[])
        self.followups.append(round_)
        for target, signature in zip(targets, signatures):
            self.guard()
            action = dict(**target, signature=list(signature), status='running', source_ids=[], candidates=[])
            round_['actions'].append(action)
            try:
                if target.get('document_path'):
                    source = self.call('read_document', {'repository': target['repository'], 'path': target['document_path']})
                    action['source_ids'] = [source['id']]
                else:
                    errors = []
                    # Official sources first, then community clues. Each read has its own budget.
                    for tool in ('read_documentation', 'read_releases', 'search_issues'):
                        args = {'repository': target['repository']}
                        if tool == 'search_issues': args['query'] = target['query']
                        try:
                            result = self.call(tool, args)
                            action['source_ids'].extend(result.get('source_ids', []))
                            if result.get('error'): errors.append(result['error'])
                        except (ValueError, httpx.HTTPError) as error:
                            errors.append(type(error).__name__)
                    action['source_ids'] = list(dict.fromkeys(action['source_ids']))
                    if errors: action['error'] = '; '.join(errors)
                # Candidate snippets are only retrieval hints, never saved as evidence automatically.
                terms = signature[2].split()
                ranked = []
                for source in self.sources.values():
                    if source['repository'] != target['repository']:
                        continue
                    lower = source['text'].casefold()
                    hits = [term for term in terms if term in lower]
                    if hits:
                        offset = min(lower.find(term) for term in hits)
                        ranked.append((len(hits), source, max(0, offset-100)))
                for _, source, offset in sorted(ranked, key=lambda row: -row[0])[:4]:
                    action['candidates'].append(dict(source_id=source['id'], kind=source['kind'],
                        quote=source['text'][offset:offset+600], needs_review=True))
                action['status'] = ('partial' if action['source_ids'] else 'failed') if action.get('error') else 'collected' if action['source_ids'] else 'empty'
            except (ValueError, httpx.HTTPError) as error:
                action['status'], action['error'] = 'failed', type(error).__name__
            except TimeoutError:
                action['status'] = 'budget_exhausted'
                raise
            finally:
                self.emit('followup', dict(message=f"补查第 {round_['index']} 轮 · {target['repository']} · {target['requirement_id']}", **action))
        return {**copy.deepcopy(round_), 'next_action': '保存确切摘录后更新矩阵；仍有缺口且有新查询方向时 review_evidence 后补查下一轮，否则直接 submit_report。未知项允许保持 unknown。'}

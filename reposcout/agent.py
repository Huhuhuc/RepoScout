import json
import httpx
from .models import Assessment, ReportArgs, RepositoryArgs, SearchArgs, EvidenceArgs, DocumentArgs, IssueArgs, FollowupArgs
from .tools import Runtime, DEMO
from . import store
from .research import research_state
from .provider import ModelService


class Cancelled(Exception):
    pass


def validate_report(runtime, proposed):
    result, excluded = [], []
    by_key = {}
    for assessment in proposed.assessments:
        key = (assessment.repository, assessment.requirement_id)
        if key in by_key:
            raise ValueError('重复判断')
        if assessment.repository not in runtime.repositories:
            raise ValueError('报告候选未调查')
        if assessment.requirement_id not in {r.id for r in runtime.request.requirements}:
            raise ValueError('报告包含未知需求')
        for eid in assessment.evidence_ids:
            evidence = runtime.evidence.get(eid)
            if not evidence or evidence['requirement_id'] != assessment.requirement_id or runtime.sources[evidence['source_id']]['repository'] != assessment.repository:
                raise ValueError('证据与候选或需求不匹配')
        if assessment.status != 'unknown' and not assessment.evidence_ids:
            raise ValueError('确定性判断必须附证据')
        if runtime.request.mode != 'demo' and assessment.status == 'unsupported' and assessment.evidence_basis != 'explicit_statement':
            raise ValueError('不支持必须有原文明确否定或限制，evidence_basis=explicit_statement；未提及、搜索无结果、未发布版本只能判 unknown')
        if assessment.evidence_basis == 'absence_of_evidence' and assessment.status != 'unknown':
            raise ValueError('缺少资料不能证明功能支持或不支持，必须保留 unknown')
        if assessment.status == 'conflict' and len(set(assessment.evidence_ids)) < 2:
            raise ValueError('冲突判断需要至少两条证据')
        if assessment.status in ('supported', 'unsupported') and assessment.evidence_ids and all(runtime.sources[runtime.evidence[e]['source_id']].get('kind') == 'issue' for e in assessment.evidence_ids):
            raise ValueError('社区 Issue 不能单独支撑确定性功能判断；请补查官方资料或保留 unknown')
        by_key[key] = assessment
    for repo in dict.fromkeys([*runtime.request.repositories, *runtime.repositories]):
        for requirement in runtime.request.requirements:
            a = by_key.get((repo, requirement.id), Assessment(repository=repo, requirement_id=requirement.id, status='unknown', explanation='未获得足够证据，待进一步核实'))
            result.append(a.model_dump())
            if requirement.mandatory and a.status == 'unsupported' and repo not in excluded:
                excluded.append(repo)
    from .verification import inspect_claims
    return {'summary': proposed.summary, 'assessments': result, 'excluded': excluded,
            'verification': inspect_claims(runtime, result),
            'research': research_state(runtime, result), 'collections': runtime.collections, 'sources': list(runtime.sources.values()), 'evidence': list(runtime.evidence.values()),
            'requirements': [r.model_dump() for r in runtime.request.requirements],
            'mode': runtime.request.mode, 'routing': getattr(runtime, 'routing', {}), 'prior_run_metrics': getattr(runtime, 'prior_metrics', {}),
            'metrics': {'tool_calls': runtime.calls, 'http_requests': runtime.http_calls, 'cache_hits': runtime.cache_hits, **getattr(runtime, 'model_metrics', {})},
            'limitations': ['仅对引用结构和摘录存在性作自动校验；结论的语义支持关系仍需复核。', '候选范围有限，未执行全网搜索；不验证 README 中的性能声明。']}


def finalize_report(runtime, proposed):
    report = validate_report(runtime, proposed)
    if not runtime.sources:
        raise ValueError('尚未读取任何资料，不能提交调查报告')
    if report['research']['gaps'] and runtime.request.max_followups and not runtime.followups and not getattr(runtime, 'closing', False) and runtime.calls+4 <= runtime.request.max_tools:
        runtime.review_evidence(proposed.assessments, proposed.summary)
        raise ValueError('已保存初步矩阵。请对一个缺口调用 investigate_gaps；其后直接 submit_report，最终复查由程序完成。')
    runtime.review_evidence(proposed.assessments, proposed.summary)
    report = validate_report(runtime, proposed)
    report['completion'] = {'type': 'model_submitted', 'reason': getattr(runtime, 'stop_reason', 'evidence_ready')}
    return report


def demo_agent(runtime):
    repos = runtime.request.repositories or list(DEMO)
    proposed = []
    for repo in repos:
        source = runtime.call('read_repository', {'repository': repo})
        for requirement in runtime.request.requirements:
            text = requirement.text
            feature = '本地部署' if '本地' in text else 'PDF 导入' if 'pdf' in text.lower() else '来源引用' if '引用' in text else None
            quote, status = None, 'unknown'
            if feature:
                for phrase, state in [('不支持 ' + feature, 'unsupported'), ('不支持' + feature, 'unsupported'), ('支持 ' + feature, 'supported'), ('支持' + feature, 'supported'), ('回答包含' + feature, 'supported')]:
                    if phrase in source['text']:
                        quote, status = phrase, state
                        break
            evidence = [runtime.call('save_evidence', {'source_id': source['id'], 'requirement_id': requirement.id, 'quote': quote})['id']] if quote else []
            proposed.append(Assessment(repository=repo, requirement_id=requirement.id, status=status, explanation='依据内置虚构资料的规则判定' if quote else '示例规则无法判定此条件', evidence_ids=evidence))
    return validate_report(runtime, ReportArgs(assessments=proposed, summary='演示完成：这些仓库与资料均为虚构样例，用于展示证据追溯，不代表真实模型效果。'))


def github_agent(runtime):
    repos = runtime.request.repositories
    if not repos:
        # A search seed is intentionally explicit; this mode is collection, not model reasoning.
        repos = runtime.call('search_repositories', {'query': runtime.request.question[:150]})['repositories']
    for repo in repos:
        for tool in ('read_repository', 'read_documentation', 'read_releases', 'search_issues'):
            try:
                runtime.call(tool, {'repository': repo})
            except (ValueError, httpx.HTTPError) as error:
                runtime.collection_result(repo, tool, [], type(error).__name__)
                runtime.emit('warning', {'message': f'{repo} {tool} 读取失败：{type(error).__name__}'})
    if not runtime.sources:
        raise ValueError('未采集到资料，请检查候选仓库、网络或 GitHub 限流。')
    return validate_report(runtime, ReportArgs(assessments=[], summary='已采集真实仓库资料（README、仓库文档、发布记录与最近 Issues，具体覆盖见来源）。未调用模型，功能判断保留为未知；社区反馈不等于已验证事实。'))



def deepseek_agent(runtime, service=None):
    from .orchestrator import investigate
    return investigate(runtime, service)


def run(ident, request, restored=None):
    if not store.claim(ident):
        return
    def check():
        if store.get(ident)['status'] != 'running':
            raise Cancelled()
    runtime = Runtime(request, check, lambda kind,payload: store.event(ident,kind,payload))
    from .checkpoint import dump, restore
    if restored:
        restore(runtime, restored)
    runtime.checkpoint = lambda: store.checkpoint(ident, dump(runtime))
    store.event(ident,'plan',{'message':'读取候选资料 → 保存需求证据 → 生成比较矩阵', 'mode':request.mode})
    try:
        report = {'demo':demo_agent,'github':github_agent,'deepseek':deepseek_agent}[request.mode](runtime)
        check()
        store.finish(ident,'partial' if report.get('completion', {}).get('type') == 'fallback' else 'completed',report)
    except Cancelled:
        store.event(ident,'cancelled',{'message':'任务已取消'})
    except TimeoutError as error:
        partial = validate_report(runtime, ReportArgs(assessments=runtime.reviews[-1]['assessments'] if runtime.reviews else [],summary='预算耗尽，保留已收集资料和最近一次通过结构校验的判断；仍需语义复核。'))
        store.finish(ident,'partial',partial,str(error))
    except Exception as error:
        from .orchestrator import fallback
        partial = fallback(runtime, 'runtime_error')
        store.finish(ident,'partial' if runtime.sources else 'failed',partial,type(error).__name__)
    finally:
        runtime.checkpoint()


def markdown(report):
    lines = ['# RepoScout 选型报告', '', report['summary'], '', f"模式：{report['mode']}", '', '| 候选 | 需求 | 判断 | 证据 |','|---|---|---|---|']
    requirements = {r['id']:r['text'] for r in report['requirements']}
    def cell(value):
        return str(value).replace('|','\\|').replace('\n',' ')
    for a in report['assessments']:
        lines.append('| ' + ' | '.join(map(cell,[a['repository'],requirements[a['requirement_id']],a['status'],', '.join(a['evidence_ids'])])) + ' |')
    lines += ['', '## 执行指标', json.dumps(report.get('metrics', {}), ensure_ascii=False),
              '提交状态：' + report.get('completion', {}).get('type', '非模型模式'), '', '## 原文证据']
    sources = {s['id']:s for s in report['sources']}
    for e in report['evidence']:
        s = sources[e['source_id']]
        lines += ['', f"### {e['id']}", e['quote'], f"来源：{s['url']}，抓取：{s['fetched_at']}，ref：{s['ref']}"]
    research = report.get('research', {})
    lines += ['', '## 证据缺口与补查', f"补查轮数：{research.get('rounds_used', 0)} / 2"]
    for gap in research.get('gaps', []):
        lines.append(f"- {gap['repository']} / {requirements[gap['requirement_id']]}：{gap['reason']}")
    for change in research.get('changes', []):
        lines.append(f"- 判断变化：{change['repository']} / {requirements[change['requirement_id']]}：{change['before']} → {change['after']}")
    for round_ in research.get('followups', []):
        for action in round_['actions']:
            lines.append(f"- 第 {round_['index']} 轮：{action['repository']} / {action['requirement_id']}，查询 {action['query']}，状态 {action['status']}")
    lines += ['', '## 证据检查（非语义证明）']
    if report.get('semantic_review'):
        lines.append(json.dumps(report['semantic_review'], ensure_ascii=False))
    for check in report.get('verification', []):
        lines.append(json.dumps(check, ensure_ascii=False))
    lines += ['', '## 采集来源']
    for source in report['sources']:
        lines += [f"- {source['id']} · {source.get('kind', 'readme')} · {source.get('title', source['repository'])} · {source['url']} · ref: {source['ref']} · 抓取: {source['fetched_at']}"]
    lines += ['', '## 采集覆盖', *[json.dumps(c, ensure_ascii=False) for c in report.get('collections', [])]]
    return '\n'.join(lines + ['', '## 限制', *report['limitations']])

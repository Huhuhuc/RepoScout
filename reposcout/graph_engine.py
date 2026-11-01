"""LangGraph investigation with node-boundary recovery and fail-closed replay."""
import copy
import json
import sqlite3
import time
from uuid import uuid4
from pathlib import Path
from typing import TypedDict

import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from . import store
from .checkpoint import dump, FIELDS
from .context import snapshot, compact_result
from .models import ReportArgs
from .orchestrator import SYSTEM, DEFINITIONS, tool_definitions, fallback, progress, QUICK_INSTRUCTION, FOLLOWUP_INSTRUCTION
from .provider import ModelService

VERSION = 1


class GraphState(TypedDict, total=False):
    version: int
    request: dict
    runtime: dict
    previous: list
    calls: list
    allowed: list
    quick: bool
    no_progress: int
    before: list
    used: int
    sent_chars: int
    attempts: int
    usage: dict
    report: dict
    stop: str
    completed_node: str


class GuardedSaver(SqliteSaver):
    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        token = checkpoint.get('channel_values', {}).get('completed_node')
        if token:
            with self.cursor() as cur:
                cur.execute('UPDATE execution_guard SET node=? WHERE thread=? AND node=?',
                            ('', config['configurable']['thread_id'], token))
        return result


def database():
    return store.DB.with_name('graph-checkpoints.db')


def journal(con):
    con.execute('CREATE TABLE IF NOT EXISTS execution_guard(thread TEXT PRIMARY KEY, node TEXT)')
    con.commit()


def guard_node(saver, ident, node):
    with saver.cursor() as cur:
        cur.execute('INSERT OR REPLACE INTO execution_guard VALUES (?,?)', (ident, node))


def snapshot_runtime(runtime):
    result = dump(runtime)
    result['execution'] = {k: copy.deepcopy(getattr(runtime, k, default)) for k, default in (
        ('calls', 0), ('http_calls', 0), ('cache_hits', 0), ('routing', {}),
        ('closing', False), ('stop_reason', ''), ('prior_metrics', {}))}
    result['elapsed'] = time.monotonic() - runtime.started
    return result


def hydrate(runtime, saved):
    # Exact in-run recovery, unlike checkpoint.restore's new-budget continuation.
    for key in FIELDS:
        setattr(runtime, key, copy.deepcopy(saved['state'][key]))
    runtime.read_windows = {tuple(x) for x in saved['read_windows']}
    runtime.model_metrics = copy.deepcopy(saved['metrics'])
    for key, value in saved['execution'].items():
        setattr(runtime, key, copy.deepcopy(value))
    runtime.started = time.monotonic() - saved['elapsed']


def recovery_status(ident, path=None):
    path = Path(path or database())
    if not path.exists():
        return False, '没有图检查点'
    with SqliteSaver.from_conn_string(str(path)) as saver:
        journal(saver.conn)
        row = saver.conn.execute('SELECT node FROM execution_guard WHERE thread=?', (ident,)).fetchone()
        if row and row[0]:
            return False, '上次节点执行尚未确认，可能已产生远端调用；请使用新预算继续调查'
        value = saver.get({'configurable': {'thread_id': ident}})
        if not value:
            return False, '没有图检查点'
        if value.get('channel_values', {}).get('version') != VERSION:
            return False, '图检查点版本不兼容'
    return True, ''


def build_graph(runtime, service, saver, ident):
    from .quick import prepare, assess
    from .agent import finalize_report

    def node(name, operation):
        def execute(state):
            if state.get('version') != VERSION or state['request'] != runtime.request.model_dump():
                raise ValueError('图状态版本或请求不一致')
            hydrate(runtime, state['runtime'])
            service.attempts = state['attempts']
            service.usage = dict(state['usage'])
            started = time.monotonic()
            token = name + ':' + uuid4().hex
            guard_node(saver, ident, token)
            runtime.emit('graph_node', {'message': '执行图节点：' + name, 'node': name})
            try:
                runtime.guard()
                update = operation(state)
            except TimeoutError:
                update = {'stop': 'budget_or_time', 'report': fallback(runtime, 'budget_or_time')}
            except (ValueError, httpx.HTTPError) as error:
                runtime.emit('warning', {'message': '图节点异常，保留部分报告', 'error_type': type(error).__name__})
                update = {'stop': 'node_error', 'report': fallback(runtime, 'node_error')}
            runtime.model_metrics = dict(model_calls=update.get('used', state['used']),
                model_requests=service.attempts, tokens=dict(service.usage),
                context_chars_sent=max(update.get('sent_chars', state['sent_chars']),
                    getattr(runtime, 'model_metrics', {}).get('context_chars_sent', 0)))
            if update.get('report'):
                update['report']['metrics'].update(runtime.model_metrics)
                update['report']['engine'] = 'langgraph'
            runtime.emit('graph_result', {'message': '节点完成：' + name, 'node': name,
                'elapsed_ms': round((time.monotonic()-started)*1000),
                'model_requests': service.attempts, 'tokens': service.usage.get('total_tokens', 0),
                'tools_used': runtime.calls, 'tools_limit': runtime.request.max_tools,
                'token_limit': runtime.request.max_tokens, 'stop_reason': update.get('stop', state.get('stop', '')),
                'feedback': update.get('previous', []), 'remaining_calls': len(update.get('calls', []))})
            runtime.checkpoint()
            return {**update, 'runtime': snapshot_runtime(runtime),
                    'attempts': service.attempts, 'usage': dict(service.usage),
                    'completed_node': token}
        return execute

    def prepare_node(state):
        return {'quick': bool(prepare(runtime))}

    def decide(state):
        if service.attempts >= 12:
            return {'stop': 'model_budget', 'report': fallback(runtime, 'model_budget')}
        reasons = []
        if service.attempts >= 8: reasons.append('reserve_final_requests')
        if runtime.calls >= runtime.request.max_tools-3: reasons.append('tool_budget')
        if time.monotonic()-runtime.started >= 210: reasons.append('time_budget')
        if state['no_progress'] >= 3: reasons.append('no_progress')
        if service.usage.get('total_tokens', 0) >= runtime.request.max_tokens*.65: reasons.append('token_reserve')
        if runtime.request.max_followups and len(runtime.followups) >= runtime.request.max_followups: reasons.append('followup_limit')
        if runtime.reviews and not runtime.reviews[-1]['gaps']: reasons.append('evidence_ready')
        runtime.closing = bool(reasons) or getattr(runtime, 'closing', False)
        runtime.stop_reason = ','.join(reasons) or getattr(runtime, 'stop_reason', 'research')
        allowed = {'save_evidence', 'read_source', 'submit_report'} if runtime.closing else set(DEFINITIONS)-{'assess_readme'}
        if state['quick'] and not runtime.closing: allowed = {'assess_readme'}
        if not runtime.request.max_followups: allowed.discard('investigate_gaps')
        if service.attempts >= 10 or runtime.calls >= runtime.request.max_tools: allowed = {'submit_report'}
        context = snapshot(runtime, 'finalize' if runtime.closing else 'research', runtime.stop_reason, state['previous'])
        context['budget']['model_requests_remaining'] = 12-service.attempts
        if state['quick']:
            context['instruction'] = QUICK_INSTRUCTION
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}]
        chars = sum(len(m['content']) for m in messages)
        if service.usage.get('total_tokens', 0)+chars+len(json.dumps(tool_definitions(allowed), ensure_ascii=False))+2500 > runtime.request.max_tokens:
            return {'stop': 'token_budget', 'report': fallback(runtime, 'token_budget')}
        message = service.chat(messages, tool_definitions(allowed))
        calls = message.get('tool_calls') or []
        update = {'calls': calls, 'allowed': sorted(allowed), 'previous': [],
                  'before': list(progress(runtime)), 'used': state['used']+1,
                  'sent_chars': state['sent_chars']+chars}
        if not calls:
            update.update(quick=False, no_progress=state['no_progress']+1,
                          previous=[{'error': '请调用允许的工具或 submit_report'}])
        return update

    def tools(state):
        call, *remaining = state['calls']
        name = call['function']['name']
        update = {'calls': remaining}
        try:
            if name not in state['allowed']:
                raise ValueError('当前阶段不允许此工具')
            args = json.loads(call['function']['arguments'])
            if name == 'assess_readme':
                update['quick'] = False
                proposal = assess(runtime, args)
                if proposal is None:
                    update['calls'] = []
                    output = {'instruction': FOLLOWUP_INSTRUCTION}
                else:
                    update['report'] = finalize_report(runtime, proposal)
                    update['calls'] = []
                    return update
            elif name == 'submit_report':
                update['report'] = finalize_report(runtime, ReportArgs.model_validate(args))
                update['calls'] = []
                return update
            else:
                output = runtime.call(name, args)
        except (ValueError, httpx.HTTPError) as error:
            if name == 'assess_readme':
                update['quick'] = False
                runtime.routing.update(path='quick_then_deep', reason='invalid_quick_assessment')
            output = {'error': str(error)[:500] if isinstance(error, ValueError) else type(error).__name__}
            runtime.emit('tool_error', {'tool': name, 'message': output['error']})
        update['previous'] = [*state['previous'], {'tool': name, 'result': compact_result(name, output)}][-6:]
        if not update['calls']:
            update['no_progress'] = state['no_progress']+1 if list(progress(runtime)) == state['before'] else 0
        return update

    def review(state):
        report = state['report']
        if runtime.request.verify_claims and not state.get('stop'):
            from .semantic_review import review_report
            report = review_report(runtime, service, report)
        return {'report': report}

    def finish(state):
        runtime.emit('submitted' if not state.get('stop') else 'phase',
                     {'message': '图执行已结束', 'reason': state.get('stop', 'model_submitted')})
        return {'report': state['report']}

    def after_decide(state):
        return 'finish' if state.get('report') else 'tools' if state['calls'] else 'decide'

    def after_tools(state):
        if state.get('stop'): return 'finish'
        if state.get('report'): return 'review'
        return 'tools' if state['calls'] else 'decide'

    graph = StateGraph(GraphState)
    for name, operation in [('prepare', prepare_node), ('decide', decide), ('tools', tools),
                            ('review', review), ('finish', finish)]:
        graph.add_node(name, node(name, operation))
    graph.add_edge(START, 'prepare')
    graph.add_conditional_edges('prepare', lambda s: 'finish' if s.get('report') else 'decide')
    graph.add_conditional_edges('decide', after_decide)
    graph.add_conditional_edges('tools', after_tools)
    graph.add_edge('review', 'finish')
    graph.add_edge('finish', END)
    return graph.compile(checkpointer=saver)


def investigate(runtime, service=None, *, ident, path=None, recover=False, pause_after=None):
    """pause_after is for bounded offline checkpoint tests, never a completed run."""
    service = service or ModelService(emit=runtime.emit, guard=runtime.guard)
    path = Path(path or database())
    path.parent.mkdir(parents=True, exist_ok=True)
    if recover:
        ok, reason = recovery_status(ident, path)
        if not ok: raise ValueError(reason)
    config = {'configurable': {'thread_id': ident}, 'recursion_limit': 512}
    with GuardedSaver.from_conn_string(str(path)) as saver:
        journal(saver.conn)
        graph = build_graph(runtime, service, saver, ident)
        if recover:
            saved = graph.get_state(config)
            if saved.values['request'] != runtime.request.model_dump():
                raise ValueError('恢复请求与图检查点不一致')
            hydrate(runtime, saved.values['runtime'])
            if not saved.next: return saved.values['report']
            initial = None
        else:
            if saver.get(config): raise ValueError('任务已有图检查点，不能覆盖')
            initial = {'version': VERSION, 'request': runtime.request.model_dump(),
                'runtime': snapshot_runtime(runtime), 'previous': [], 'calls': [], 'allowed': [],
                'quick': False, 'no_progress': 0, 'before': [], 'used': 0, 'sent_chars': 0,
                'attempts': service.attempts, 'usage': dict(service.usage), 'report': {}, 'stop': ''}
        # sync durability guarantees checkpoint commit before a returned values event.
        for _ in graph.stream(initial, config, stream_mode='values', durability='sync',
                                  interrupt_after=[pause_after] if pause_after else None):
            pass
        saved = graph.get_state(config)
        hydrate(runtime, saved.values['runtime'])
        if saved.next: return None
        return saved.values['report']

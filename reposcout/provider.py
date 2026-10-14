"""Server-side model configuration and transport. Never expose provider bodies."""
import os
import time
from dataclasses import dataclass, field

import httpx
from dotenv import dotenv_values

from .store import ROOT


class ModelError(ValueError):
    pass


@dataclass(frozen=True)
class ModelConfig:
    key: str = field(repr=False)
    model: str = 'deepseek-flash'


def settings(path=None):
    values = dotenv_values(path or ROOT / '.env', encoding='utf-8-sig', interpolate=False)
    def value(name, default=''):
        return (os.environ.get(name, values.get(name)) or default).strip()
    model = value('DEEPSEEK_MODEL', 'deepseek-flash')
    if len(model) > 100 or not all(c.isalnum() or c in '-_./' for c in model):
        raise ModelError('模型名称格式无效，请检查 DEEPSEEK_MODEL')
    return ModelConfig(value('DEEPSEEK_API_KEY'), model)


ERRORS = {400: '模型请求格式错误', 401: '密钥认证失败，请检查本地 API Key',
          402: '模型账户余额不足', 403: '模型服务拒绝访问', 404: '模型或接口不存在',
          422: '模型请求参数无效', 429: '模型服务限流，请稍后重试',
          500: '模型服务内部错误', 503: '模型服务繁忙'}


class ModelService:
    def __init__(self, config=None, emit=None, guard=None):
        self.config = config or settings()
        if not self.config.key:
            raise ModelError('尚未配置密钥，请在项目 .env 中填写 DEEPSEEK_API_KEY')
        self.emit = emit or (lambda *args: None)
        self.guard = guard or (lambda: None)
        self.attempts = 0
        self.usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    def request(self, method, path, payload=None, limit=12):
        for retry in range(2):
            self.guard()
            if self.attempts >= limit:
                raise TimeoutError('达到模型网络请求预算（包含重试）')
            self.attempts += 1
            started = time.monotonic()
            status = None
            try:
                with httpx.Client(timeout=35, trust_env=True, follow_redirects=False) as client:
                    response = client.request(method, 'https://api.deepseek.com' + path,
                        headers={'Authorization': 'Bearer ' + self.config.key}, json=payload)
                status = response.status_code
            except httpx.TransportError:
                # A timed-out generation may already be billed; don't repeat it automatically.
                raise ModelError('模型网络连接失败或超时，请检查网络后重试') from None
            finally:
                self.emit('model_request', {'attempt': self.attempts, 'status': status,
                          'elapsed_ms': round((time.monotonic()-started)*1000)})
            if status in (429, 500, 503) and retry == 0 and self.attempts < limit:
                self.emit('model_retry', {'message': ERRORS[status] + '，将重试一次'})
                time.sleep(1)
                continue
            if status != 200:
                raise ModelError(ERRORS.get(status, '模型服务返回异常状态'))
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError()
                return data
            except ValueError:
                raise ModelError('模型服务返回了无效 JSON') from None

    def chat(self, messages, tools):
        data = self.request('POST', '/chat/completions', {'model': self.config.model,
            'messages': messages, 'tools': tools, 'max_tokens': 2500, 'thinking': {'type': 'disabled'}})
        try:
            message = data['choices'][0]['message']
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError()
            for call in message.get('tool_calls') or []:
                if not isinstance(call['id'], str) or not isinstance(call['function']['name'], str) or not isinstance(call['function']['arguments'], str):
                    raise ValueError()
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelError('模型响应缺少有效消息或工具调用结构') from None
        usage = data.get('usage') or {}
        for name in self.usage:
            number = usage.get(name)
            if isinstance(number, int) and number >= 0:
                self.usage[name] += number
        self.emit('model_usage', {'call': self.attempts, 'usage': dict(self.usage)})
        return message

    def test_connection(self):
        data = self.request('GET', '/models', limit=2)
        items = data.get('data')
        if not isinstance(items, list) or any(not isinstance(x, dict) or not isinstance(x.get('id'), str) for x in items):
            raise ModelError('模型列表响应格式异常')
        available = any(x['id'] == self.config.model for x in items)
        return {'connected': True, 'model_available': available, 'model': self.config.model,
                'message': '认证成功，所选模型可用；工具调用尚需调查任务验证' if available else
                '认证成功，但模型列表未包含所选名称；请核对 DEEPSEEK_MODEL',
                'models': [x['id'] for x in items]}

# RepoScout 选型报告

候选仅 encode/httpx。README 声明支持 HTTP/1.1 与 HTTP/2，但未说明默认行为；docs/http2.md 明确写明 HTTP/2 默认不启用（因 HTTP/1.1 更稳健，未来版本可能改变），并给出开启步骤：安装 httpx[http2] 可选依赖 + 客户端设置 http2=True。因此“HTTP/2 默认开启，无需额外配置”判定为 unsupported，依据为官方文档的明确否定陈述；HTTP/2 功能本身可用，但需额外依赖与显式配置。docs/api.md 的陈述与之一致（Client 可启用 HTTP/2），无冲突。

模式：deepseek

| 候选 | 需求 | 判断 | 证据 |
|---|---|---|---|
| encode/httpx | HTTP/2 默认开启，无需额外配置 | unsupported | E2, E3, E1 |

## 执行指标
{"tool_calls": 1, "http_requests": 0, "cache_hits": 0, "model_calls": 2, "model_requests": 3, "tokens": {"prompt_tokens": 15517, "completion_tokens": 923, "total_tokens": 16440}, "context_chars_sent": 37281}
提交状态：model_submitted

## 原文证据

### E1
ent**, has support for both **HTTP/1.1 and HTTP/2**, and provides both **sync and async APIs**.

---

Install HTTPX using pip:

```shell
$ pip install httpx
```

Now, let's get started:

```pycon
>>> import httpx
>>> r = httpx.get('https://www.example.org/')
>>> r
<Response [200 OK]>
>>> r.status_code
200
>>> r.headers['content-type']
'text/html; charset=UTF-8'
>>> r.text
'<!doctype html>\n<html>\n<head>\n<title>Example Domain</title>...'
```

Or, using the command-line client.

```shell
$ pip install 'httpx[cli]'  # The command line client is an optional dependency.
```

Which now allows us to use HTTPX directly from the command-line...

<p align="center">
  <img width="700" src="docs/img/h
来源：https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/README.md，抓取：2026-10-18T03:24:16.937006+00:00，ref：b5addb64f0161ff6bfe94c124ef76f6a1fba5254

### E2
ponse prioritization,
and server push.

For a comprehensive guide to HTTP/2 you may want to check out "[http2 explained](https://http2-explained.haxx.se/)".

## Enabling HTTP/2

When using the `httpx` client, HTTP/2 support is not enabled by default, because
HTTP/1.1 is a mature, battle-hardened transport layer, and our HTTP/1.1
implementation may be considered the more robust option at this point in time.
It is possible that a future version of `httpx` may enable HTTP/2 support by default.

If you're issuing highly concurrent requests you might want to consider
trying out our HTTP/2 support. 
来源：https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/http2.md，抓取：2026-10-18T03:24:37.946903+00:00，ref：b5addb64f0161ff6bfe94c124ef76f6a1fba5254

### E3
You can do so by first making sure to install
the optional HTTP/2 dependencies...

```shell
$ pip install httpx[http2]
```

And then instantiating a client with HTTP/2 support enabled:

```python
client = httpx.AsyncClient(http2=True)
...
```

You can also instantiate a client as a context manager, to ensure that all
HTTP connections are nicely scoped, and will be closed once the context block
is exited.

```python
async with httpx.AsyncClient(http2=True) as client:
    ...
```

HTTP/2 support is available on both `Client` and `AsyncClient`, although it's
typically more useful in async contexts if you're issuing lots of concurrent
requests.

## Inspecting the HTTP version

Enabling HTTP/2 su
来源：https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/http2.md，抓取：2026-10-18T03:24:37.946903+00:00，ref：b5addb64f0161ff6bfe94c124ef76f6a1fba5254

## 证据缺口与补查
补查轮数：0 / 2
- 判断变化：encode/httpx / HTTP/2 默认开启，无需额外配置：unknown → unsupported

## 证据检查（非语义证明）
{"status": "completed", "independent_model": false, "method": "same_model_separate_prompt", "verdicts": [{"repository": "encode/httpx", "requirement_id": "R1", "verdict": "supported_by_quotes", "reason": "E2 明确写明“HTTP/2 support is not enabled by default”，并指出未来版本才可能默认启用；E3 要求安装 httpx[http2] 并显式设置 http2=True。这些摘录直接支持 claim.status=unsupported，即“默认开启、无需额外配置”不成立。E1 仅声明支持 HTTP/1.1 与 HTTP/2，未提及默认状态，符合 claim 的描述。摘录未反驳 claim，无冲突。"}]}
{"repository": "encode/httpx", "requirement_id": "R1", "quote_match": true, "has_repository_source": true, "source_refs": ["b5addb64f0161ff6bfe94c124ef76f6a1fba5254"], "applicable_version": "b5addb64f0161ff6bfe94c124ef76f6a1fba5254", "conditions": "HTTP/2 需 pip install httpx[http2] 安装可选依赖，并在 Client/AsyncClient 上设置 http2=True。", "semantic_support": "needs_review", "warnings": []}

## 采集来源
- S1 · readme · README · https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/README.md · ref: b5addb64f0161ff6bfe94c124ef76f6a1fba5254 · 抓取: 2026-10-18T03:24:16.937006+00:00
- S2 · documentation · docs/quickstart.md · https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/quickstart.md · ref: b5addb64f0161ff6bfe94c124ef76f6a1fba5254 · 抓取: 2026-10-18T03:24:30.594804+00:00
- S3 · documentation · docs/api.md · https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/api.md · ref: b5addb64f0161ff6bfe94c124ef76f6a1fba5254 · 抓取: 2026-10-18T03:24:32.232861+00:00
- S4 · documentation · docs/async.md · https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/async.md · ref: b5addb64f0161ff6bfe94c124ef76f6a1fba5254 · 抓取: 2026-10-18T03:24:34.265393+00:00
- S5 · documentation · docs/http2.md · https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/docs/http2.md · ref: b5addb64f0161ff6bfe94c124ef76f6a1fba5254 · 抓取: 2026-10-18T03:24:37.946903+00:00

## 采集覆盖
{"repository": "encode/httpx", "kind": "documentation", "status": "collected", "source_ids": ["S2", "S3", "S4"], "error": null, "discovered_paths": ["docs/quickstart.md", "docs/api.md", "docs/async.md", "docs/http2.md", "docs/index.md", "docs/logging.md", "docs/exceptions.md", "docs/advanced/ssl.md", "docs/contributing.md", "docs/compatibility.md", "docs/code_of_conduct.md", "docs/troubleshooting.md", "docs/advanced/clients.md", "docs/advanced/proxies.md", "docs/advanced/timeouts.md", "docs/advanced/extensions.md", "docs/advanced/transports.md", "docs/advanced/event-hooks.md", "docs/third_party_packages.md", "docs/environment_variables.md", "docs/advanced/authentication.md", "docs/advanced/text-encodings.md", "docs/advanced/resource-limits.md"], "coverage": "最多扫描四个目录、读取三篇仓库维护文档；未抓取外部文档网站"}

## 限制
仅对引用结构和摘录存在性作自动校验；结论的语义支持关系仍需复核。
候选范围有限，未执行全网搜索；不验证 README 中的性能声明。
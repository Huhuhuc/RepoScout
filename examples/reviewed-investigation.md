# RepoScout 选型报告

对 langchain-ai/local-deep-researcher 的 R1（支持 Ollama 本地模型）核实完成：README 存在明确的 Ollama 支持声明、专用配置章节与配置样例，判定为 supported（explicit_statement），证据 ID 为 E1–E3。版本/条件已注明：适用版本为上述 README 提交，使用需本地 Ollama 服务与 .env 中 LLM_PROVIDER=ollama；gpt-oss 模型在 Ollama 中不支持 JSON 模式，须改用 use_tool_calling。无未决缺口或冲突项，无 unknown 结论。

模式：deepseek

| 候选 | 需求 | 判断 | 证据 |
|---|---|---|---|
| langchain-ai/local-deep-researcher | 支持 Ollama 本地模型 | supported | E1, E2, E3 |

## 执行指标
{"tool_calls": 17, "http_requests": 6, "cache_hits": 3, "model_calls": 10, "model_requests": 11, "tokens": {"prompt_tokens": 38133, "completion_tokens": 1991, "total_tokens": 40124}, "context_chars_sent": 59523}
提交状态：model_submitted

## 原文证据

### E1
Local Deep Researcher is a fully local web research assistant that uses any LLM hosted by [Ollama](https://ollama.com/search) or [LMStudio](https://lmstudio.ai/).
来源：https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md，抓取：2026-10-14T10:53:01.463547+00:00，ref：03537326ffa0dd90c9702bece2f3aeba5d84162a

### E2
### Selecting local model with Ollama

1. Download the Ollama app for Mac [here](https://ollama.com/download).

2. Pull a local LLM from [Ollama](https://ollama.com/search). As an [example](https://ollama.com/library/deepseek-r1:8b):
```shell
ollama pull deepseek-r1:8b
```
来源：https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md，抓取：2026-10-14T10:53:01.463547+00:00，ref：03537326ffa0dd90c9702bece2f3aeba5d84162a

### E3
LLM_PROVIDER=ollama
OLLAMA_BASE_URL="http://localhost:11434" # Ollama service endpoint, defaults to `http://localhost:11434`
LOCAL_LLM=model # the model to use, defaults to `llama3.2` if not set
来源：https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md，抓取：2026-10-14T10:53:01.463547+00:00，ref：03537326ffa0dd90c9702bece2f3aeba5d84162a

## 证据缺口与补查
补查轮数：0 / 2

## 证据检查（非语义证明）
{"status": "completed", "independent_model": false, "method": "same_model_separate_prompt", "verdicts": [{"repository": "langchain-ai/local-deep-researcher", "requirement_id": "R1", "verdict": "supported_by_quotes", "reason": "E1 明确说明该工具使用由 Ollama 托管的任意 LLM，E2 给出 Ollama 本地模型选择步骤（下载 Ollama、ollama pull），E3 给出 LLM_PROVIDER=ollama、OLLAMA_BASE_URL、LOCAL_LLM 配置。摘录一致支持“支持 Ollama 本地模型”，版本引用一致（同 commit）。"}]}
{"repository": "langchain-ai/local-deep-researcher", "requirement_id": "R1", "quote_match": true, "has_repository_source": true, "source_refs": ["03537326ffa0dd90c9702bece2f3aeba5d84162a"], "applicable_version": "README @ 03537326ffa0dd90c9702bece2f3aeba5d84162a", "conditions": "本地需运行 Ollama 服务（默认端点 http://localhost:11434）；通过 .env 设置 LLM_PROVIDER=ollama 可覆盖 configuration.py 中的默认值；README 另提示（8/6/25）gpt-oss 模型在 Ollama 中不支持 JSON 模式，需在配置中选择 use_tool_calling。", "semantic_support": "needs_review", "warnings": []}

## 采集来源
- S1 · readme · README · https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md · ref: 03537326ffa0dd90c9702bece2f3aeba5d84162a · 抓取: 2026-10-14T10:53:01.463547+00:00

## 采集覆盖
{"repository": "langchain-ai/local-deep-researcher", "kind": "documentation", "status": "empty", "source_ids": [], "error": null, "discovered_paths": [], "coverage": "最多扫描四个目录、读取三篇仓库维护文档；未抓取外部文档网站"}
{"repository": "langchain-ai/local-deep-researcher", "kind": "release", "status": "empty", "source_ids": [], "error": null}

## 限制
仅对引用结构和摘录存在性作自动校验；结论的语义支持关系仍需复核。
候选范围有限，未执行全网搜索；不验证 README 中的性能声明。

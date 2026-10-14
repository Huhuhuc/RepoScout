# RepoScout 选型报告

针对 langchain-ai/local-deep-researcher 的两项需求核查：R1（Ollama 本地模型）在 README 中有明确支持依据（开篇说明 + Ollama 配置专节），判定 supported；R2（PDF 文件导入）在 README 全文及检索中均未出现相关描述，既无支持也无明确否定，按证据缺失判定 unknown。已遵守预算，未做重复补查，保留未知项。

模式：deepseek

| 候选 | 需求 | 判断 | 证据 |
|---|---|---|---|
| langchain-ai/local-deep-researcher | 支持通过 Ollama 使用本地模型 | supported | E1, E2 |
| langchain-ai/local-deep-researcher | 支持上传 PDF 文件作为研究资料 | unknown |  |

## 执行指标
{"tool_calls": 20, "http_requests": 3, "cache_hits": 8, "model_calls": 11, "model_requests": 11, "tokens": {"prompt_tokens": 36710, "completion_tokens": 1723, "total_tokens": 38433}, "context_chars_sent": 66060}
提交状态：model_submitted

## 原文证据

### E1
Local Deep Researcher is a fully local web research assistant that uses any LLM hosted by [Ollama](https://ollama.com/search) or [LMStudio](https://lmstudio.ai/).
来源：https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md，抓取：2026-10-14T05:04:31.327951+00:00，ref：03537326ffa0dd90c9702bece2f3aeba5d84162a

### E2
### Selecting local model with Ollama

1. Download the Ollama app for Mac [here](https://ollama.com/download).

2. Pull a local LLM from [Ollama](https://ollama.com/search). As an [example](https://ollama.com/library/deepseek-r1:8b):
```shell
ollama pull deepseek-r1:8b
```
来源：https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md，抓取：2026-10-14T05:04:31.327951+00:00，ref：03537326ffa0dd90c9702bece2f3aeba5d84162a

## 证据缺口与补查
补查轮数：0 / 2
- langchain-ai/local-deep-researcher / 支持上传 PDF 文件作为研究资料：missing_evidence

## 采集来源
- S1 · readme · README · https://github.com/langchain-ai/local-deep-researcher/blob/03537326ffa0dd90c9702bece2f3aeba5d84162a/README.md · ref: 03537326ffa0dd90c9702bece2f3aeba5d84162a · 抓取: 2026-10-14T05:04:31.327951+00:00

## 采集覆盖

## 限制
仅对引用结构和摘录存在性作自动校验；结论的语义支持关系仍需复核。
候选范围有限，未执行全网搜索；不验证 README 中的性能声明。
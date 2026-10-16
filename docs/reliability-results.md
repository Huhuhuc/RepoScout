# 可靠性改进验收

整理日期：2026-10-16。真实模型与对照实验执行于 2026-10-14，未重新调用模型生成相同数据。本记录编写时改动仅本地保存；后续已按用户要求上传并公开源码。最新变更见 adaptive-results.md。

## 已实现

- 允许两轮不同查询的补查，统一工具与控制器指令；读取新正文窗口计为进展，相同查询第三次执行时拒绝。
- 补查优先仓库文档、Release，再查询 Issue。增加仓库已链接的外部文档读取工具，目前限 docs.langchain.com、python.langchain.com、docs.llamaindex.ai、docs.haystack.deepset.ai、docs.n8n.io、docs.dify.ai。只读取 HTTPS 文本、禁止重定向、限制 1 MB，不发送 GitHub/模型凭据；外部网页版本未固定。
- 中文词组/双字片段匹配，每个来源分配正文窗口，避免后加入来源没有上下文。
- SQLite 检查点；模型异常返回部分报告，重启中断仍可查看/导出已保存资料。“继续调查”创建关联的新任务，复用资料，重置执行预算与补查轮数；原任务保留，旧版任务没有检查点时不显示该按钮。
- 恢复前将“已补查但未复核”的旧判断降为未知，避免沿用过期结论。
- 页面可设置 Token 预算；按累计 usage 与下一次请求字符估算控制调用，65% 时准备收尾。此估算不是供应商账单硬限额；预算太小会返回部分报告。
- 原文匹配、来源类型、版本、限制条件分别展示。可选同模型独立提示复核；复核不足/矛盾的确定性判断降为未知。复核失败或预算不足明确显示，绝不标为已验证。UI 默认勾选，直接 API 请求需设置 verify_claims=true。

## 真实调用

任务 de4e2d15abe24ebfae3cd908dd7c3f42 完成 GitHub 资料读取、证据保存、最终提交及模型复核。11 次模型网络请求（含复核）、17 次工具调用、40,124 Token；判断支持 Ollama 本地模型，并记录适用 commit 与配置条件。[原始记录](reliability-live.json)、[报告](../examples/reviewed-investigation.md)。仍存在重复读取，不能据这次结果宣称成本已降低。

## 同资料对照

真实仓库 langchain-ai/local-deep-researcher 的一个固定 README，3 项人工标注任务：Ollama 支持、gpt-oss/Ollama JSON mode 限制、PDF 导入未获证实。每项重复两次，三种策略共享同一个冻结资料池。不是跨项目大规模基准。

| 策略 | 判断正确 | 有效提交 | 总 Token | 模型请求 |
|---|---:|---:|---:|---:|
| 全资料一次回答 | 5/6 | 6/6 | 23,255 | 6 |
| 关闭定向补查 Agent | 6/6 | 6/6 | 134,694 | 41 |
| 完整 Agent | 6/6 | 6/6 | 172,682 | 50 |

这组实验没有证明定向补查带来额外准确率收益，完整 Agent 成本反而更高。关闭补查仅禁用 investigate_gaps，直接资料检索仍可用；本次对照未启用额外语义复核。下一阶段需要更多仓库、多来源缺口和多条件任务，才能判断补查在哪些场景值得使用。不要将 6/6 写成普遍准确率。

原始数据：[真实资料快照](../evals/real-cases.json)、[完整结果](../evals/results/reliability-real.json)。运行器会记录资料哈希，冻结期间禁止访问外部资料，包括官方网页。

```powershell
# 不调用模型
.\.venv\Scripts\python.exe -m evals.compare
# 显式付费运行，另存结果
.\.venv\Scripts\python.exe -m evals.compare --live --max-cases 3 --repeats 2 --output evals/results/new-comparison.json
```

## 验证边界

自动测试覆盖两轮补查、停止条件、Token 预算、异常结果、检查点恢复、取消/重启、外部文档约束与模型复核降级。外部官方网页采集本轮使用 HTTP mock 验证，未宣称完成所有文档站点的实网兼容验证。恢复入口在本地演示模式验证；真实模型复核已实跑。此轮验收时 CI 尚未运行；后续云端结果见仓库 Actions。

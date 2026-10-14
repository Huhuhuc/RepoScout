# DeepSeek 真实验收 · 2026-10-14

密钥认证成功，官方模型列表返回 deepseek-flash / deepseek-v4-pro。将旧模板 deepseek-chat 改为 deepseek-flash；显式使用非思考模式。密钥没有记录在文档或 Git 中。

固定任务：调查 langchain-ai/local-deep-researcher 是否支持 Ollama 本地模型、PDF 文件导入。每轮最多 12 次模型请求、20 次工具调用，三轮实测后停止调用。

1. 首轮完成提交，但错误地把未发现 PDF 资料判为不支持，未通过人工语义验收。增加 evidence_basis 字段及 absence_of_evidence 只能对应 unknown 的校验；仍不是通用语义证明器。
2. 第二轮正确保留 PDF 为未知，但因重复检查耗尽预算。修正最终矩阵比较：说明措辞变化不要求重查，判断与证据变化仍要求重查。
3. 第三轮确实完成真实工具调用、非法摘录纠正、重复目标参数纠正、Issue 补查和更新矩阵，但最终提交前补查后未复查，达到请求上限，返回 partial。Ollama 为支持，PDF 为未知。新增明确参数说明与可执行错误提示，未再付费复跑。

结论：真实认证、模型响应、工具执行与参数错误恢复已验证；预算保护和部分报告保存已验证。尚不能宣布真实端到端稳定验收通过，需要下一次有预算的回归确认最终提交。

逐轮任务 ID、状态和 Token 记录见 deepseek-acceptance.json。Token 数为接口累计用量，不等于金额；未按未经核实的价格估算费用。30 项离线测试通过。

官方参考：https://api-docs.deepseek.com/guides/tool_calls/


## 2026-10-14 后续验收

本页前文为历史记录。最新预算收尾、真实模型完成记录、41 项回归及 12 项冻结评测见 [本地迭代与验收](completion-and-evaluation.md)。

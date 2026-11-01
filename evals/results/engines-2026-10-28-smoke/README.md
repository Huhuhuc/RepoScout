# 双执行器真实模型冒烟对照

2026-10-28，DeepSeek deepseek-flash。相同冻结资料池、auto 策略、关闭可选语义复核；每个执行器每题一次，交替执行顺序。没有实时 GitHub 网络请求，使用此前保存的真实仓库资料。

| 任务 | 执行器 | 有效完成／判断／严格评分 | 模型请求 | Token | 秒 |
|---|---|---|---:|---:|---:|
| HTTPX 同步与异步 API | legacy | 全部通过 | 4 | 14,128 | 12.644 |
| HTTPX 同步与异步 API | langgraph | 全部通过 | 1 | 2,265 | 2.285 |
| HTTPX 默认启用 HTTP/2 | legacy | 全部通过 | 7 | 37,720 | 23.935 |
| HTTPX 默认启用 HTTP/2 | langgraph | 全部通过 | 6 | 31,982 | 21.594 |

合计：legacy 51,848 Token、11 次请求、36.579 秒；langgraph 34,247 Token、7 次请求、23.879 秒。全部 86,095 Token、18 次请求。Token 为接口 usage 汇总，未换算账单金额。

第一题 legacy 快速判断不满足完整性约束，升级深入调查；langgraph 快速路径完成。第二题 langgraph 出现重复判断，工具返回错误后纠正并完成。

这验证了两个真实模型执行路径能提交报告，以及 LangGraph 的工具反馈纠错。仅两个 HTTPX 任务、单次运行，不能推断整体准确率或稳定节约成本。快速路径提示措辞在两个实现中仍有差异，故这不是严格隔离框架因素的因果实验；正式评测前需统一提示。未覆盖实际网络故障或真实模型调用中断恢复。

完整报告、工具事件、配置、模型名、代码和资料哈希保存在 results.json。checkpoints.db 是本地检查点，不纳入 Git。

重跑时使用新的输出目录：

```powershell
.\.venv\Scripts\python.exe -X utf8 -u -m evals.compare_engines --live --output evals/results/engines-smoke-new
```

# Legacy / LangGraph 真实模型对照

运行日期：2026-10-28；收尾核验：2026-11-01。模型：`deepseek-flash`。

## 方法与结果

12 个冻结资料任务（HTTPX、Pydantic、FastAPI），每种执行器每题运行一次，共 24 次。使用 auto 策略、关闭额外语义复核；两种执行器使用相同资料、任务与主要提示词，并逐题交替执行顺序。模型仍有随机性，错误反馈与执行实现也存在差异，因此不能把结果差异完全归因于 LangGraph。

| 指标 | legacy | langgraph |
|---|---:|---:|
| 判断正确 | 11/12 | 12/12 |
| 正常提交报告 | 9/12 | 12/12 |
| 严格证据评分通过 | 8/12 | 11/12 |
| 模型请求数 | 75 | 75 |
| 总 Token | 296648 | 316892 |
| 总耗时（秒） | 187.734 | 203.434 |

本轮 LangGraph 总 Token 增加约 6.8%，耗时增加约 8.4%。Token 不是实际账单金额。该结果是小规模单轮观察，不是统计显著的性能提升或通用准确率；严格证据评分不是证据召回率。

原始结果见 [results.json](results.json)，包括数据与代码哈希、参数、报告、事件、评分和用量。检查点数据库不发布。

## 失败样本复核

- legacy 的 `httpx-vector`、`pydantic-pdf`、`fastapi-background` 未正常提交，返回预算停止后的部分报告；前两题标签碰巧正确也不算完成。
- 两种执行器的 `fastapi-websocket` 都引用 README 的 `Many extra features (thanks to Starlette) such as:` 和 `**WebSockets**` 列表，摘录精确匹配原文。评分仅接受官方教程中的 `You can use [WebSockets]`，因此未通过。
- 上述 README 提供功能支持线索，但未展示具体路由声明；该案例同时暴露了接受片段覆盖不足和路由级证据不够具体的问题。保留原分数，不在看到结果后修改数据集以提高成绩。后续应由独立复核者明确证据粒度、扩充可接受片段并发布新的数据集版本，再运行新的对照。

## 复现

在项目根目录配置 `.env` 后运行（会产生模型费用，输出目录必须不存在）：

```powershell
.\.venv\Scripts\python.exe -m evals.compare_engines --live --max-cases 12 --output evals/results/my-engines-comparison
```

冻结资料不重新访问 GitHub，但推理会调用真实模型。当前比较脚本逐次保存结果，不支持断点补跑；中断后保留部分结果，不能将其当成完整对照。

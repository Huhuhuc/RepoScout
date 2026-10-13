# RepoScout 开源调研与改进路线

调研日期：2026-10-13。范围：上游 README、部分核心源码、评测说明、官方接口文档和许可证文件。没有安装或运行上游项目，没有调用模型 API；运行性能和兼容性仍需后续验证。下面将可核实的上游能力与我们的设计建议分开。引用 main 分支的文件会变化，开始复用代码时必须记录 commit SHA 并锁定依赖。

## 结论

建议独立开发 RepoScout，参考 Local Deep Researcher 的搜索—总结—发现缺口—补查循环，以及 GPT Researcher 的来源追踪和采集分层。先实现轻量单 Agent，保留将调研步骤迁移到 LangGraph 的接口。完整二次开发 GPT Researcher 是可选替代方案，适合优先交付通用研究产品；针对本科面试和开源选型场景，我们更需要可解释的需求判断、证据结构和评测。

RepoScout 的差异应是每条需求都有判定依据，而不是报告字数更多。我们的改进建议针对当前产品目标，不意味着上游项目一定缺少所有类似能力。

## 已有项目比较

| 项目 | 已核实的用途 | 对 RepoScout 的价值 | 采用方式 |
| --- | --- | --- | --- |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | 通用调研及报告生成 | 理解采集、上下文、写作的分层 | 阅读核心模块；必要时用 SDK 做基线 |
| [Local Deep Researcher](https://github.com/langchain-ai/local-deep-researcher) | 迭代检索、总结和缺口反思 | 小规模循环更容易理解与复现 | 核心流程参考 |
| [Deep Agents](https://github.com/langchain-ai/deepagents) | 含上下文管理的 Agent harness | 学习工具和大结果管理 | 第一版按需选择，不整体引入所有能力 |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | 深度研究示例 | 阅读澄清、简报及调查结构 | 历史架构参考；仓库目前已归档 |
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | 网页采集及 Markdown 生成 | 动态网页和正文抽取 | 第一版静态读取；后续可选适配器 |
| [Jina Reader](https://github.com/jina-ai/reader) | URL 内容转换、搜索服务 | 获取干净网页内容 | 可选外部服务，保留原始 URL |

### GPT Researcher：参考分层与来源管理

阅读入口：

- [ResearchConductor 源码](https://github.com/assafelovic/gpt-researcher/blob/main/gpt_researcher/skills/researcher.py)
- [ReportGenerator 源码](https://github.com/assafelovic/gpt-researcher/blob/main/gpt_researcher/skills/writer.py)
- [评测说明](https://github.com/assafelovic/gpt-researcher/blob/main/evals/README.md)

源码中的研究模块区分搜索结果和实际页面内容，并维护 visited_urls。评测目录覆盖事实问答和报告对来源的幻觉检查。

我们的改进：明确区分 discovered、fetched、failed 三种来源状态；抓取失败不能仅因 URL 已访问就永远跳过。保存内容快照、摘要和证据摘录，避免只存摘要。用选型任务评测代替直接套用通用事实问答。文档里的上游样例成绩不能写成自己的指标。

### Local Deep Researcher：最合适的流程学习入口

阅读入口：[graph.py](https://github.com/langchain-ai/local-deep-researcher/blob/main/src/ollama_deep_researcher/graph.py)。README 描述了查询生成、搜索、总结、反思缺口和再次搜索的循环，支持本地模型运行。

我们的改进：将自由文本总结转为“候选项目 × 用户要求”的结构化证据矩阵。补查必须对应一个未解决条件。连续两轮无新增证据时结束，输出 unknown。设置真实网络请求、模型请求和上下文大小三类预算，避免只限制图循环次数。

### Deep Agents / LangGraph：可采用的框架能力

阅读入口：

- [研究示例](https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/README.md)
- [研究工具源码](https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/research_agent/tools.py)
- [工作流和 Agent 的区别](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)

Deep Agents 示例体现了搜索、读取正文和任务组织。LangGraph 的 checkpointer 与跨任务 store 用途不同，内存 checkpoint 不能保证进程重启后数据存在。

我们的选择：让模型根据证据缺口选择下一次工具，程序校验动作和预算；不要将固定步骤包装成自由决策。第一版用 SQLite 保存任务及来源，重启标记 interrupted。若后续迁移 LangGraph，使用持久化 checkpointer，并另外保存来源快照及产品数据。

### Open Deep Research：仅作历史参考

仓库页目前显示 2026-08-21 已归档。可阅读 [deep_researcher.py](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py) 中需求澄清与研究简报的设计。不要以旧 README 的模型默认值或排行榜成绩证明当前效果。

### Crawl4AI 和 Jina Reader：采集组件

[Crawl4AI Markdown 文档](https://docs.crawl4ai.com/core/markdown-generation/) 可用于学习正文生成。Jina Reader 提供 URL 转换接口。

我们的选择：静态官方页面先使用 HTTP 抓取与正文抽取；只有静态读取确实失败时才考虑动态浏览器适配器。不同采集器可能产生不同文本，记录 extractor 名称与版本。不得把摘要模型生成的内容当成原文；外部采集服务的结果也必须记录实际成功或失败。

## 必需接口资料与实现影响

### GitHub API

官方资料：

- [搜索接口](https://docs.github.com/en/rest/search/search)
- [限流说明](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [仓库内容接口](https://docs.github.com/en/rest/repos/contents)

搜索有独立限流：当前文档列出未认证 10 次/分钟、认证普通搜索 30 次/分钟；代码搜索单独处理并需要认证。搜索最多返回 1,000 个结果，可能出现 incomplete_results。实现应读取限流响应头，不把固定数字作为永久保证；展示覆盖范围，不声称找到了全 GitHub 最佳项目。

公共数据允许无认证访问，但额度有限。内容接口对文件大小与下载 URL 有限制，README 优先通过专用接口读取，其他文件设置大小上限。仓库资料记录 repo、ref、blob SHA 或内容哈希，避免默认分支改变后无法复现。

GitHub 仓库搜索不是互联网全文搜索。不能把复杂中文选型条件直接当作可靠仓库查询；模型生成若干技术关键词及语言/topic 条件，搜索后才做能力验证。

### 网站搜索

[Tavily Search 官方接口](https://docs.tavily.com/documentation/api-reference/endpoint/search) 支持域名限制、原始内容等参数。

第一版将 search_repositories 和 search_web 分开。search_web 为可选 provider：没有配置时，仍可通过用户候选仓库、README 的官方链接和明确 URL 读取完成有限调查，报告标注“未进行全网搜索”。不能用关键词在仓库内搜索冒充全网搜索。Tavily 是可选依赖，不能假定无需密钥或无限免费。

### DeepSeek

[官方 Tool Calls 文档](https://api-docs.deepseek.com/guides/tool_calls/) 的搜索摘要可访问，但本轮完整页面读取失败。因此只确认工具调用文档存在；strict/beta、具体模型及消息参数必须在接入时重新核实，不以本轮摘要确定适配实现。

默认使用 Mock；未来显式配置后使用 DeepSeek。工具调用参数始终由本地结构校验。模型请求失败、工具返回失败和报告校验失败分别记录。

## RepoScout 的六项具体改进

### 1. 从文章报告变为需求证据矩阵

每个 Requirement 有文本、是否硬性、判定口径。每个 Candidate 对每项要求有 supported、unsupported、unknown 或 conflict，附 Evidence IDs。只有同一条件和适用版本明确矛盾时才标记 conflict；不同版本的差异独立展示。没有找到依据不等于不支持。

### 2. 证据记录可复查

Source 保存 canonical_url、requested_url、抓取时间、资料日期、ref、content_hash、extractor 和 fetch_status。Evidence 保存 source_id、精确摘录和在规范化正文中的字符偏移。偏移针对保存的正文，不声称对应原始 HTML。Claim 保存结论与 evidence_ids，Report 引用 Claim。

搜索摘要只用于发现来源，必须读取正文才能形成最终证据。引用 ID 有效与摘录匹配可以自动检查，引用语义是否支持结论需要人工或另外的评审，二者分别计分。

### 3. 有目的的补查

Agent 每轮返回结构化 action、工具参数和简短 decision_summary，记录可展示的行动理由，不保存隐藏思维链。程序检查动作是否合法。补查针对版本、依赖、部署条件或功能缺口；停止规则为关键条件已解决、两轮无新证据、预算到达或用户取消。

### 4. 对选型结论做约束处理

明确违反硬性条件的项目保留在比较表并标记 excluded，不进入推荐第一名。未知硬性条件的候选只能给条件性建议。stars、最近提交和发布记录是元数据，不能单独代表质量、稳定性或适用性。许可证列出识别结果及官方文件链接，不作法律结论。

### 5. 把预算拆开

原设计的 20 次工具调用不能等同于 20 次 HTTP 请求。read_repository 一次逻辑调用可能产生多个请求。修订建议：默认 20 次工具调用、60 次外部 HTTP 请求（重试计入）、12 次模型调用、2 轮补查、5 分钟任务上限；保留一次报告生成额度。单页面限制下载大小和正文长度，任务限制总上下文。所有值可配置并写入任务快照。

### 6. 建立自己的可复现评测

首批至少 12 个固定任务，使用冻结资料快照，覆盖：满足全部条件、违反硬性条件、没有依据、版本差异、同版本资料冲突、限流、抓取失败、恶意页面指令、重复内容、无法核实的性能声明、预算耗尽和取消。真实实时网络任务单独展示，不与冻结样本混算。

基线 A：固定候选和相同初始证据，一次模型直接输出。实验 B：相同模型、候选、资料池和输出格式，允许缺口补查。记录证据增量和额外成本。另做取消补查的消融实验。人工判定约束正确率和引用支持率；自动检查证据结构、去重、预算和失败处理。重复运行与审阅人记录进入评测报告。Mock 只验流程，不能产生模型能力成绩。

## 复用路径比较

| 路径 | 适用情况 | 代价 | 本项目建议 |
| --- | --- | --- | --- |
| Fork GPT Researcher | 优先快速交付完整研究产品 | 需要熟悉较大代码库，个人贡献必须清楚界定 | 可作为后续替代或评测基线 |
| 基于 LangGraph 搭建 | 强调图编排、暂停恢复和框架实践 | 需要锁定并理解依赖、checkpoint 与业务数据库关系 | 后续需要恢复能力时采用 |
| 独立轻量循环＋成熟采集组件 | 优先掌握决策、证据和评测 | 自己负责控制循环、持久化和错误处理 | 第一版推荐，与原设计一致 |

实现时借鉴机制而不整体复制上游提示词和 UI。直接复制或修改源码时记录原仓库、commit、文件和修改点，保留该代码要求的许可与署名。

## 许可证记录

- [GPT Researcher LICENSE](https://github.com/assafelovic/gpt-researcher/blob/main/LICENSE)：Apache-2.0。
- [Deep Agents LICENSE](https://github.com/langchain-ai/deepagents/blob/main/LICENSE)：MIT。
- [Local Deep Researcher LICENSE](https://github.com/langchain-ai/local-deep-researcher/blob/main/LICENSE)：MIT。
- [Jina Reader](https://github.com/jina-ai/reader)：仓库显示 Apache-2.0；托管服务条款与源码许可分别确认。
- [Crawl4AI LICENSE](https://github.com/unclecode/crawl4ai/blob/main/LICENSE)：复用时阅读完整许可证及上游署名要求，本轮不将其简化成无需条件的许可。

这些是项目资料记录，不代替对具体复用文件的许可检查。

## 建议实施顺序和交付物

1. Source、Evidence、Requirement、CandidateAssessment 数据结构及 12 个离线资料场景；交付可审阅的样本与标准答案。
2. 单 Agent 控制循环、模型适配器、参数校验和预算；交付命令行完整调研和轨迹。
3. GitHub API、静态网页及可选 web search provider；交付一份真实公开仓库调查报告，明确 Mock/real 模式。
4. 证据核验、需求矩阵与报告导出；交付可点击引用与错误案例。
5. FastAPI、持久化事件、中文前端；交付历史任务、取消、执行进度和证据查看，黑灰与暖橙配色。
6. 固定评测、基线、消融、项目架构和演示说明；真实模型验证完成后再写简历指标。

本轮成果是调研与实施建议，尚未实现上述功能；未安装上游、未运行基准，不声称已验证性能。

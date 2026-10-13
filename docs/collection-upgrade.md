# 多来源采集升级

沿用已批准的 RepoScout 设计，完成路线第一步：从 README 采集扩展到仓库维护文档、发布记录和社区 Issues。不需要模型密钥。

实现选择：继续使用 GitHub 官方 REST API，统一来源模型；暂不引入任意网页爬虫。文档路径限定文本格式，使用固定 commit 读取，下载大小和调用次数受原有预算约束。

执行顺序：扩展来源工具 → 接入采集策略与模型工具 → 来源页和导出 → 离线回归及真实仓库验收。

验收：15 项测试通过；真实采集 langchain-ai/local-deep-researcher、assafelovic/gpt-researcher，最终页面验收得到 14 个来源（2 README、3 文档、3 Release、6 Issues），8 次工具调用、19 次 HTTP。未调用付费模型。采集元数据见 collection-smoke.json。

限制：文档发现有目录深度/数量上限；未覆盖外部文档网站；采集模式读取最新 Issues，不声称与用户需求语义相关；关键词 Issue 搜索可由模型调用。当前没有引用语义核验或真实模型质量评测。

接口参考：
- https://docs.github.com/en/rest/repos/contents
- https://docs.github.com/en/rest/releases/releases
- https://docs.github.com/en/rest/search/search
- https://docs.github.com/en/rest/issues/issues

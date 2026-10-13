# 模型接入层

按用户批准的方案实现 .env 配置、连接测试、统一模型服务层。

- provider.py 负责配置、官方 HTTP 请求、错误分类、有限重试、请求耗时和 Token 汇总；agent.py 保留任务和工具循环。
- python-dotenv 读取项目绝对路径 .env；禁止变量插值，环境变量优先，密钥不进入状态接口、配置对象 repr 或服务错误消息。
- 页面支持刷新配置与显式连接测试；GET /api/model/config 只返回 configured/provider/model。POST /api/model/test 请求官方 GET /models，检查认证及模型名称，不生成回答。
- 401/402/422 直接报告；429/500/503 最多重试一次，重试也计入 12 次任务模型请求上限。网络超时不自动重放生成请求，以免重复生成。
- 成功报告记录模型请求次数和累计 Token；执行轨迹记录耗时、状态和重试，不记录认证头。
- 所有模型调用仍受原有任务总时长与工具预算限制。当前没有按金额计费器或 Token 硬上限。

验证：29 项测试通过，包括配置优先级、脱敏、认证失败不重试、限流重试、模型列表接口、非法响应、用量累计、请求预算和离线 Agent 完整循环。未使用真实密钥，未进行付费调用。

官方参考：
- https://api-docs.deepseek.com/api/list-models/
- https://api-docs.deepseek.com/quick_start/error_codes/

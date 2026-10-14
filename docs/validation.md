# 第一版验证记录

2026-10-13，本机 Windows，独立 Python 3.13 虚拟环境。

- unittest 9 项通过：演示矩阵、硬性条件排除、伪造摘录拒绝、跨需求证据拒绝、工具预算、仓库路径、历史与导出、取消后不提交、重启中断、重复需求校验（其中一项测试包含历史与导出多个断言）。
- workspace.js 通过 node --check。
- 实际读取 langchain-ai/local-deep-researcher README：10,481 字符，2 次 GitHub HTTP 请求；记录 blob SHA。此项只验证公开资料读取，不验证模型推理。
- 浏览器通过：创建演示调查、完成报告（3 候选、8 证据、11 工具调用）、证据链接切换到证据视图、返回比较报告。
- 工作台截图见 images/workspace.png。
- 最新 Starlette 对 httpx 测试适配器给出弃用提示；目前测试通过，后续升级时需要调整测试客户端。

未调用 DeepSeek，未验证真实模型工具循环；未验证全网搜索、官方网页读取和冻结资料质量评测。

## 多来源升级回归

15 项 unittest 全部通过，新增：文档 commit 固定与缓存/引用、非法路径拒绝、Issue 仓库范围和社区来源标记、空发布列表、部分采集失败保留、有限文档发现。JavaScript 语法检查通过。真实双仓库抓取记录见 collection-smoke.json；未调用 DeepSeek。

## 证据缺口与补查回归

22 项测试通过（新增 7 项），包含五次离线模拟模型响应的完整补查闭环；JavaScript 语法检查通过。浏览器实际运行演示任务，显示 1 个证据缺口、0/2 补查轮次；Markdown 导出包含缺口记录。截图：images/evidence-gaps.png。真实模型尚未调用。

## 模型接入层回归

29 项测试通过；页面显示未配置、禁用测试按钮，刷新配置正常。连接测试和重试采用 HTTP MockTransport 验证，没有真实模型请求。截图 images/model-settings.png。.env 已被 git check-ignore 确认忽略。


## 2026-10-14 后续验收

本页前文为历史记录。最新预算收尾、真实模型完成记录、41 项回归及 12 项冻结评测见 [本地迭代与验收](completion-and-evaluation.md)。

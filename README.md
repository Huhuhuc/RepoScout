# RepoScout

**让开源选型的每个判断都有原文依据。**

输入需求与最多三个候选仓库，保存调查轨迹、资料和证据，生成比较矩阵。中文工作台采用黑灰与暖橙配色。

![调研工作台](docs/images/workspace.png)

布局借鉴成熟工具的工作区与工具轨迹分层，详见 [参考说明](docs/workspace-references.md)。

## 运行

Windows 双击 `start-reposcout.bat`，首次安装依赖后打开 http://127.0.0.1:8011 。需要 Python 3.11+。启动器不会覆盖已有 `.env`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m uvicorn reposcout.app:app --host 127.0.0.1 --port 8011
```

先选择演示模式，使用默认的本地部署、PDF、引用三个条件。示例仓库全部虚构，规则策略确定比较结果；它不模拟真实模型研究质量。

Windows 自检：`powershell -ExecutionPolicy Bypass -File .\start-reposcout.ps1 -Check`。更换端口加 `-Port 8012`。Linux/macOS 可运行 `bash start-reposcout.sh`（本机尚未实跑该平台）。

本地交付材料：[真实报告](examples/real-investigation.md) · [架构图](docs/architecture.md) · [验收记录](docs/completion-and-evaluation.md) · [截图导览视频](docs/demo/reposcout-walkthrough.mp4)。当前未发布或部署公网。

## 三种模式

| 模式 | 数据 | 决策 |
|---|---|---|
| demo | 内置虚构快照 | 明确限定的规则，测试流程 |
| github | 真实 GitHub README、仓库文档、Release、Issue | 只采集，功能判断为未知 |
| deepseek | 真实 GitHub README、仓库文档、Release、Issue | 模型动态选工具并提交结构化报告 |

GitHub 模式建议输入明确仓库，例如 `langchain-ai/local-deep-researcher`。无候选时直接将问题用作 GitHub 查询；复杂中文查询质量有限。已开始真实 DeepSeek 验收，过程与发现见 docs/deepseek-acceptance.md。

## 配置 DeepSeek

复制 `.env.example` 为 `.env`，在本地填写：

```dotenv
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_MODEL=deepseek-flash
```

运行服务后，在页面点击“刷新配置”，再点“测试连接”。配置每次从本地读取，无需重启；已开始的调查继续使用启动时的配置。系统环境变量优先于 `.env`。不要提交真实密钥；`.env` 已被 Git 忽略。可用模型名称以你账户的模型列表为准，测试会提示所选模型是否存在。

测试连接仅请求官方 `/models`，不会生成回答；认证成功不代表 Agent 工具链已完成真实验收。选择 DeepSeek 调查模式才会发送任务内容并生成回答，产生模型调用费用。页面和状态接口不返回密钥。

可选的 `GITHUB_TOKEN` 仍通过进程环境变量配置。模型服务地址固定为官方 DeepSeek，暂不支持自定义网关。

## 当前实现

- Requirement / Source / Evidence / Assessment 四类数据。
- 摘录必须属于来源原文，证据必须关联同一候选与需求。
- 支持、不支持、未知、冲突；违反硬性条件的候选列为 excluded。
- 单 Agent 工具调用循环，模型参数本地校验。
- SQLite 历史任务、执行事件、取消、重启中断标记。
- 工具预算、60 次网络请求上限、12 次模型调用上限、5 分钟任务上限。
- SSE 进度、证据查看、Markdown/JSON 导出。
- 调查/收尾阶段切换、最终报告预算预留、任务内只读缓存与有界上下文；无有效最终提交明确标为部分完成。

## 多来源采集

- README 与仓库文档固定到同一个 commit；保存正文、原链接、抓取时间与哈希。
- 每个候选最多扫描四个目录、读取三篇文档、三个发布记录和三个 Issues。
- GitHub 采集模式读取最近 Issues；DeepSeek 工具支持按关键词补查。Issue 不包含评论，社区报告不等于官方结论。
- 页面与导出保留来源类型、版本、状态和采集失败记录；无结果不等于不支持。
- 当前官方文档指仓库内维护的文档，外部文档网站尚未接入。

## 证据缺口驱动补查

DeepSeek 模式新增 `review_evidence` 和 `investigate_gaps`：初步矩阵 → 缺口检查 → 最多两轮定向文档/Issue 补查 → 保存摘录 → 更新矩阵。工作台与导出显示未解决项和判断变化。社区 Issue 不可单独支撑确定性功能判断。

无密钥模式显示结构性缺口，功能判断仍保持未知。完整工具循环同时保留离线模拟回归；真实调用验收见 docs/deepseek-acceptance.md。细节见 [补查设计与验证](docs/evidence-followup.md)。

## 明确的边界

第一版没有全网搜索、任意网页读取、语义引用审判、多 Agent、自动恢复或向量检索。GitHub HTTP 只允许固定 API 域名且不跟随重定向。报告的引用结构校验不能证明结论语义正确。采集模式不从 README 关键词推断真实能力。DeepSeek 接口配置与真实任务验收记录见 docs/deepseek-acceptance.md。

这是本地单用户原型，无登录、多租户与公网部署能力。保持绑定 127.0.0.1。README 长度和下载大小有限；报告保存抓取时间、ref 和哈希，源正文可能截断。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

41 项自动测试通过。12 个冻结合成案例已用真实 DeepSeek 跑完：README 单次回答正确 7/12，调查模式正确 12/12；总 Token 分别为 6,133 与 178,197。调查模式可读取额外资料，这不是同资料推理对照，也不代表真实任务准确率 100%。[完整结果与限制](evals/README.md)。

真实仓库存在性另行验证：搜索返回的 3 个仓库均读取到 GitHub 元数据和 README，不存在的负例返回 404。[验证记录](docs/github-live-verification.json)。可执行 `python -m scripts.verify_live_github` 复查（访问 GitHub，不调用模型）。

`.github/workflows/ci.yml` 已包含 Windows/Linux 与 Python 3.11/3.13 测试矩阵；由于尚未推送，当前仅有本机验证结果。

## 学习来源

- [GPT Researcher](https://github.com/assafelovic/gpt-researcher)：调研、来源与报告分层。
- [Local Deep Researcher](https://github.com/langchain-ai/local-deep-researcher)：迭代研究循环。
- [GitHub REST 文档](https://docs.github.com/en/rest)：公开仓库读取与限流。

本版独立编写，未复制上游源码。调研结论位于工作区 docs/2026-10-13-RepoScout开源调研与改进路线.md。

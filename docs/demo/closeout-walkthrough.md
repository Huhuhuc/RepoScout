# RepoScout 面试演示脚本

以下三段分别展示直接取证、深入调查和恢复能力。快速/深入段调用真实模型和实时 GitHub，答案取决于当时资料；恢复段为明确标注的离线虚构样例，不消耗模型费用、不改动个人数据库。

## 启动

在仓库目录执行 `start-reposcout.bat`，打开 http://127.0.0.1:8011 。本地 .env 已配置者无需重新填密钥。不要在录屏中展示 .env。

## 第一段：条件明确时取证

工作台输入仓库 `encode/httpx`，条件“同时提供同步和异步 API”，选择 DeepSeek、自动策略。

讲解：程序先读取 README，模型选择原文片段编号；后端从已存来源按范围截取，保存 URL、commit、正文位置。若条件足够明确则直接提交，复核开关可增加一次调用。不能保证所有模型响应均走快速路径；出现限制或无效参数会升级调查。

可用命令创建相同任务并导出报告：

```powershell
.\.venv\Scripts\python.exe -m scripts.closeout_demo --scenario quick --live
```

## 第二段：区别“支持”和“默认开启”

仍使用 `encode/httpx`，条件“HTTP/2 默认开启，无需额外配置”。

README 说明支持 HTTP/2，不足以证明默认开启。观察 Agent 是否补充读取 docs/http2.md，在证据页查看默认开关和配置条件。若网络限流或工具预算耗尽，应展示实际部分报告，不把未知改成不支持。

```powershell
.\.venv\Scripts\python.exe -m scripts.closeout_demo --scenario followup --live
```

## 第三段：无费用演示检查点恢复

```powershell
.\.venv\Scripts\python.exe -m scripts.closeout_demo
```

使用临时数据库和虚构演示资料，经 API 验证：已取消任务有检查点 → 创建关联新任务 → 完成并导出；旧任务仍为 cancelled。输出 model_calls=0、child_status=completed、export_status=200。它验证恢复工程流程，不验证真实模型效果。

真实任务也可在已有检查点时取消，然后点击“继续调查”，但新任务获得新预算，会继续产生费用。不要为了演示中断用户正在运行的任务。

## 建议录屏顺序

1. 说明输入是仓库与条件，输出是带证据的判断矩阵。
2. 展示第一段报告及原文位置，再看请求数和 Token。
3. 展示第二段如何区分 README 能力描述与文档限制。
4. 运行离线恢复命令，解释检查点和关联任务。
5. 展示固定数据集对照结果及失败案例，明确成本和覆盖边界。

每段先检查资料页和结果，实际路径不符预期时照实说明。脚本导出默认保存在 data/demo-exports/，不自动加入 Git。

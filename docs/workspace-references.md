# 工作台布局参考

用户要求参考成熟 Agent 工具的布局。以下只借鉴信息结构，页面独立编写，未复制标识、素材或源码。

- [Langflow Playground 官方文档](https://docs.langflow.org/concepts-playground)：工作台支持输入测试、查看 Agent 工具调用和输出。参考结果区与工具轨迹分开展示。
- [Langflow 可视化编辑器](https://docs.langflow.org/concepts-overview)：工作区与 Playground、Logs 等入口分层。RepoScout 不实现编辑画布，采用任务列表与报告视图。
- [Dify 仓库](https://github.com/langgenius/dify)：工作流、模型与可观测性在工作空间中组织。参考固定侧栏和顶部运行操作。未安装或直接操作 Dify 企业控制台；此处不声称复刻其实时界面。

RepoScout 的落地结构：左侧导航与历史、中间比较报告/证据/来源标签页、右侧执行轨迹、顶部新建和导出，运行统计取自实际结果。新建表单可收起；历史任务重新加载输入。保留黑灰、低饱和暖橙和灰绿状态色。

表格结论点击证据 ID 时切换证据标签并定位。轨迹默认简要说明，工具参数可展开。未实现的功能不设空按钮。第一版仍为本地单用户原型。

# 方案参考与实现边界

核验日期：2026-10-25。以下是官方仓库，参考交互或架构思路；除项目明确列出的依赖外，未复制这些仓库的实现，也不声称已经集成整套框架。

- [LangGraph](https://github.com/langchain-ai/langgraph)：有状态工具执行、可检查的过程和人工确认。
- [assistant-ui](https://github.com/assistant-ui/assistant-ui)：对话、工具状态和可恢复的操作反馈。
- [React Flow / xyflow](https://github.com/xyflow/xyflow)：节点流程的视觉关联；本轮小规模流程使用原生HTML/SVG，避免引入无实际必要的图编辑器依赖。
- [Impeccable](https://github.com/pbakaus/impeccable)：产品层级、克制动效、响应式与可访问性。

Agent页面中显示的是实际执行的工具、输入摘要及结果，不展示模型隐藏推理。规则模式不冒充模型，外部模型按原有显式配置和数据授权使用。

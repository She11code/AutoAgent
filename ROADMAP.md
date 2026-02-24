# Auto-Agent 开发路线图

## 当前状态 (v0.1.0)

### 已完成功能
- [x] 多Agent协作框架（Supervisor + ReAct + Plan）
- [x] 四层状态管理（messages, runtime, knowledge, task_context）
- [x] 提示词外置到 MD 文件
- [x] 记忆持久化（Memory/SQLite/PostgreSQL）
- [x] 领域知识管理
- [x] 远程 API 同步层
- [x] 基础单元测试

---

## Phase 1: 稳定性 (v0.2.0)

### 1.1 测试覆盖
- [ ] 增加 Agent 节点级别的单元测试
- [ ] 增加 ReAct 循环集成测试
- [ ] 增加 Plan 执行集成测试
- [ ] 添加 `pytest-cov` 覆盖率报告
- 目标：覆盖率 > 80%

### 1.2 错误处理
- [ ] 添加 LLM 调用重试逻辑（exponential backoff）
- [ ] 添加 API 同步失败降级策略
- [ ] 统一错误类型定义 (`src/exceptions.py`)
- [ ] 添加错误恢复节点

### 1.3 日志与可观测性
- [ ] 结构化日志（structlog）
- [ ] Agent 执行追踪（可选：LangSmith 集成）
- [ ] 关键指标埋点（执行时间、token 消耗）

---

## Phase 2: 功能扩展 (v0.3.0)

### 2.1 新 Agent 模式
- [ ] **Debate Agent**: 多角色辩论模式，适合决策分析
- [ ] **Tool Expert Agent**: 专注于工具调用的专家模式
- [ ] **Human-in-the-Loop**: 支持人工审核/批准节点

### 2.2 工具管理
- [ ] 统一的工具注册中心 (`src/tools/`)
- [ ] 工具发现和自动文档生成
- [ ] 内置常用工具（搜索、代码执行、文件操作）

### 2.3 流式支持
- [ ] 支持 `astream_events` 流式输出
- [ ] 长任务进度回调
- [ ] 中间结果可视化

---

## Phase 3: 易用性 (v0.4.0)

### 3.1 CLI 工具
```bash
auto-agent run examples/demo.py
auto-agent debug --session-id xxx
auto-agent export --format mermaid
```
- [ ] 创建 `cli/` 模块
- [ ] 支持交互式调试
- [ ] 支持导出执行图

### 3.2 配置简化
- [ ] YAML 配置文件支持 (`config/agents.yaml`)
- [ ] 环境变量统一管理
- [ ] 多环境配置（dev/staging/prod）

### 3.3 更多示例
- [ ] 代码审查 Agent
- [ ] 文档生成 Agent
- [ ] 数据分析 Agent
- [ ] 多轮对话机器人

---

## Phase 4: 生产就绪 (v1.0.0)

### 4.1 部署支持
- [ ] Docker 镜像
- [ ] Kubernetes Helm Chart
- [ ] 健康检查端点
- [ ] 优雅关闭

### 4.2 性能优化
- [ ] 提示词缓存
- [ ] 并行 Agent 执行
- [ ] 连接池管理
- [ ] 内存使用优化

### 4.3 安全性
- [ ] 敏感信息脱敏（API Key 等）
- [ ] 输入验证和清理
- [ ] 权限控制（可选）

---

## 长期愿景

### Agent 能力增强
- 自我反思和自我改进
- 长期记忆（向量数据库）
- 多模态支持（图像、音频）

### 生态建设
- LangGraph 模板市场
- 插件系统
- 社区贡献指南

---

## 贡献优先级

| 优先级 | 领域 | 说明 |
|--------|------|------|
| P0 | 测试覆盖 | 确保核心功能稳定 |
| P0 | 错误处理 | 生产环境必备 |
| P1 | 日志/追踪 | 问题排查必需 |
| P1 | CLI 工具 | 提升开发体验 |
| P2 | 新 Agent 模式 | 扩展适用场景 |
| P2 | 流式支持 | 长任务必需 |
| P3 | 部署方案 | 生产就绪 |

---

## 版本发布节奏

- **v0.2.0** - 4周 - 稳定性改进
- **v0.3.0** - 6周 - 功能扩展
- **v0.4.0** - 4周 - 易用性提升
- **v1.0.0** - 4周 - 生产就绪

总计约 4-5 个月达到 v1.0.0。

---

## 如何参与

1. 在 Issues 中认领任务
2. 提交 PR 前先讨论设计方案
3. 遵循 `CLAUDE.md` 中的开发规范
4. 添加测试覆盖新功能

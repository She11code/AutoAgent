# Auto-Agent

基于 LangGraph + LangChain 的多Agent协作系统，支持 **ReAct、Plan 高级 Agent 模式**。

## 特性

- **两种 Agent 模式**
  - ReAct Agent：观察-思考-行动循环
  - Plan Agent：规划-执行-反思循环

- **多层次状态管理**
  - 程序运行态（Runtime State）：远程API状态实时同步
  - 领域知识层（Domain Knowledge）：静态知识注入到System Prompt
  - 对话记忆层（Conversation Memory）：历史消息持久化
  - 任务上下文（Task Context）：Agent工作空间

- **灵活的配置**
  - Agent 注册中心：统一管理 Agent 类型
  - 子图作为节点：灵活组合各种 Agent 模式
  - 多种记忆存储后端

## 安装

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 或使用 uv
uv sync
```

## 快速开始

```python
import asyncio
from langchain_anthropic import ChatAnthropic
from src.core.state import create_initial_state
from src.core.graph import create_app_with_agents
from src.agents import create_supervisor_node, create_react_node, create_plan_node

async def main():
    # 初始化LLM (Anthropic Claude)
    llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0,
    )

    # 创建 Agent 节点
    researcher = create_react_node(llm, tools=[], name="researcher", max_steps=3)
    coder = create_react_node(llm, tools=[], name="coder", max_steps=3)

    # 创建 Supervisor（指定可用的 Agent）
    supervisor = create_supervisor_node(
        llm=llm,
        valid_agents={"researcher", "coder"},
    )

    # 创建应用
    app = create_app_with_agents(
        supervisor_node=supervisor,
        agent_nodes={
            "researcher": researcher,
            "coder": coder,
        },
        use_persistence=True,
    )

    # 创建初始状态
    state = create_initial_state(
        session_id="demo",
        user_id="user1",
    )
    state["messages"] = [{"role": "user", "content": "写一个Python函数"}]

    # 运行
    result = await app.ainvoke(
        state,
        config={"configurable": {"thread_id": "demo"}}
    )
    print(result["messages"][-1].content)

asyncio.run(main())
```

## 项目结构

```
Auto-Agent/
├── src/
│   ├── core/               # 核心模块
│   │   ├── state.py        # State定义
│   │   ├── reducers.py     # 自定义Reducer
│   │   └── graph.py        # StateGraph构建
│   ├── agents/             # Agent实现
│   │   ├── supervisor.py   # Supervisor路由（独立类）
│   │   ├── registry.py     # Agent类型注册中心
│   │   ├── utils.py        # 工具函数
│   │   ├── react/          # ReAct Agent（子图）
│   │   │   ├── graph.py
│   │   │   └── nodes/
│   │   │       ├── observe.py
│   │   │       ├── think.py
│   │   │       └── act.py
│   │   └── plan/           # Plan Agent（子图）
│   │       ├── graph.py
│   │       └── nodes/
│   │           ├── decompose.py
│   │           ├── execute.py
│   │           └── reflect.py
│   ├── sync/               # API同步层
│   ├── knowledge/          # 领域知识管理
│   └── memory/             # 记忆管理
├── config/                 # 配置
├── examples/               # 示例
└── tests/                  # 测试
```

## Agent 模式

> 详细文档见 [src/agents/README.md](src/agents/README.md)

### ReAct Agent
观察-思考-行动循环，适合需要多次迭代的复杂任务。

```python
from src.agents import create_react_node
react_agent = create_react_node(
    llm=llm,
    tools=[search_tool, code_tool],
    name="researcher",
    system_prompt="",  # 可选：自定义提示词
    max_steps=5,
)
```

### Plan Agent
规划-执行-反思循环，适合需要分解的复杂任务。

```python
from src.agents import create_plan_node
plan_agent = create_plan_node(
    llm=llm,
    tools=[],
    name="planner",
    system_prompt="",  # 可选：自定义提示词
    max_steps=10,
)
```

### Supervisor
协调器，负责任务分解和路由决策。

```python
from src.agents import create_supervisor_node
supervisor = create_supervisor_node(
    llm=llm,
    valid_agents={"researcher", "coder"},
    system_prompt="",  # 可选：自定义提示词
)
```

## 上下文管理

Agent 执行时从 `MultiAgentState` 读取上下文并注入到 Prompt。

**详细文档**: [docs/context-flow.md](docs/context-flow.md) - LLM 上下文数据来源和数据流详解

```
┌──────────────────┐      ┌─────────────────────┐
│  MultiAgentState │ ──→  │  build_system_prompt │
└────────┬─────────┘      └──────────┬──────────┘
         │                           │
         ├─ domain_knowledge ────────┼─→ 注入领域知识
         ├─ runtime ─────────────────┼─→ 注入运行态变量
         ├─ task_context ────────────┼─→ 读取任务/历史
         └─ messages ────────────────┴─→ 对话历史
                                     │
                                     ▼
                              LLM Prompt
```

**只有 3 个节点直接调用 LLM**：
- **Supervisor**: 读取 messages、agent_results、plan_steps、task_status、plan_status
- **Think**: 读取 current_task、plan_steps、react_iterations、tools
- **Decompose**: 读取 task_assignments、tools、domain_knowledge

### 上下文注入工具

```python
from src.agents.utils import (
    inject_knowledge,       # 注入领域知识
    inject_runtime_vars,    # 注入运行态变量
    build_system_prompt,    # 构建完整提示词
    get_current_task,       # 获取当前任务
    get_previous_results,   # 获取历史结果
)

# 自定义提示词 + 上下文注入
prompt = build_system_prompt(
    state=state,
    base_prompt="你是一个助手",
    include_knowledge=True,
    include_runtime=False,
)
```

### 自定义提示词

各 Agent 支持通过参数或修改默认常量自定义提示词：

| 文件 | 默认常量 | 模板变量 |
|------|----------|----------|
| `supervisor.py` | `DEFAULT_SUPERVISOR_PROMPT` | `{available_agents}` |
| `react/nodes/think.py` | `DEFAULT_THINK_PROMPT` | `{task}`, `{iterations}`, `{tools}` |
| `plan/nodes/decompose.py` | `DEFAULT_DECOMPOSE_PROMPT` | `{task}`, `{tools}`, `{context}` |

详见 [src/agents/README.md](src/agents/README.md)

## 状态架构

```
┌─────────────────────────────────────────────┐
│              MultiAgentState                │
├─────────────────────────────────────────────┤
│ messages: List[BaseMessage]  (add_messages) │
│ runtime: RuntimeState        (覆盖更新)     │
│ domain_knowledge: DomainKnowledge (覆盖)    │
│ task_context: TaskContext    (追加/覆盖)    │
│ session_id: str                             │
│ user_id: str                                │
└─────────────────────────────────────────────┘
```

### Reducer策略

| 字段 | Reducer | 说明 |
|------|---------|------|
| messages | add_messages | 追加消息，支持去重 |
| runtime | 覆盖 | API同步后完整替换 |
| domain_knowledge | 覆盖 | 会话开始时注入 |
| task_assignments | operator.add | 任务分配累积 |
| agent_results | operator.add | Agent结果累积 |

## 配置

复制 `.env.example` 到 `.env` 并配置：

```env
# Anthropic Claude (必须)
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# 远程API（可选）
REMOTE_API_BASE_URL=http://localhost:8080
```

## 示例

- [basic_usage.py](examples/basic_usage.py) - 基础用法
- [with_api_sync.py](examples/with_api_sync.py) - 带API同步

## License

MIT

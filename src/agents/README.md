# Agents 模块

多 Agent 系统的核心实现，包含 Supervisor 协调器和 ReAct/Plan 两种 Agent 模式。

## 目录结构

```
src/agents/
├── __init__.py          # 模块导出
├── supervisor.py        # Supervisor 协调器
├── registry.py          # Agent 类型注册中心
├── utils.py             # 上下文注入工具函数
├── prompts/             # 提示词模板文件
│   ├── __init__.py      # load_prompt() 加载器
│   ├── supervisor.md    # Supervisor 决策提示
│   ├── react/
│   │   └── think.md     # ReAct 思考提示
│   └── plan/
│       ├── decompose.md # Plan 分解提示
│       └── reflect.md   # Plan 反思提示
├── react/               # ReAct Agent 子图
│   ├── graph.py         # 子图定义
│   └── nodes/
│       ├── think.py     # 思考节点
│       ├── act.py       # 行动节点
│       └── observe.py   # 观察节点
└── plan/                # Plan Agent 子图
    ├── graph.py         # 子图定义
    └── nodes/
        ├── decompose.py # 分解节点
        ├── execute.py   # 执行节点
        └── reflect.py   # 反思节点
```

---

## Agent 模式

### 1. ReAct Agent

**流程**: `init → think → act → observe → think → ... → finalize`

适合需要多次工具调用的迭代任务。

```python
from src.agents import create_react_node

agent = create_react_node(
    llm=llm,
    tools=[search_tool, code_tool],
    name="researcher",
    system_prompt="",      # 可选：自定义提示词
    max_steps=5,
)
```

### 2. Plan Agent

**流程**: `init → decompose → execute → execute → ... → reflect → finalize`

适合需要分解为多步骤的复杂任务。

```python
from src.agents import create_plan_node

agent = create_plan_node(
    llm=llm,
    tools=[],
    name="planner",
    system_prompt="",      # 可选：自定义提示词
    max_steps=10,
    reflect_on_failure=True,
)
```

### 3. Supervisor

**职责**: 任务分解、路由决策、结果整合

```python
from src.agents import create_supervisor_node

supervisor = create_supervisor_node(
    llm=llm,
    valid_agents={"researcher", "coder", "planner"},
    system_prompt="",      # 可选：自定义提示词
    max_iterations=10,
)
```

---

## 上下文管理

### 四层状态架构

Agent 执行时从 `MultiAgentState` 读取上下文，构建 LLM Prompt：

| 层级 | 字段 | 用途 | 注入方式 |
|------|------|------|----------|
| 对话记忆 | `messages` | 对话历史 | 自动传递给 LLM |
| 领域知识 | `domain_knowledge` | 静态知识注入 | `inject_knowledge()` |
| 运行态 | `runtime` | 远程 API 变量 | `inject_runtime_vars()` |
| 任务上下文 | `task_context` | Agent 工作空间 | 节点内部读取 |

### 上下文注入流程

```
┌──────────────────┐
│  MultiAgentState │
└────────┬─────────┘
         │
         ▼  读取各层
┌─────────────────────────────────────┐
│  build_system_prompt(state, base)   │
│  ├─ inject_knowledge()              │
│  │    └─ state["domain_knowledge"]  │
│  └─ inject_runtime_vars()           │
│       └─ state["runtime"]           │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  SystemMessage(content=prompt)      │
│  HumanMessage(content=context)      │
└────────┬────────────────────────────┘
         │
         ▼
      LLM 调用
```

---

## 自定义提示词

### 方式 1: 通过工厂函数参数

```python
# ReAct Agent 自定义提示词
custom_react_prompt = """你是一个专业的代码审查员。

## 当前任务
{task}

## 审查历史
{iterations}

## 可用工具
{tools}

请审查代码并给出改进建议。"""

agent = create_react_node(
    llm=llm,
    tools=[],
    name="reviewer",
    system_prompt=custom_react_prompt,
)

# Supervisor 自定义提示词
custom_supervisor_prompt = """你是项目管理员。

## 可用专家
{available_agents}

## 决策规则
1. 优先分配给最合适的专家
2. 避免重复工作
"""

supervisor = create_supervisor_node(
    llm=llm,
    valid_agents={"reviewer", "fixer"},
    system_prompt=custom_supervisor_prompt,
)
```

### 方式 2: 编辑 MD 文件（推荐）

静态提示词模板存储在 `src/agents/prompts/` 目录，直接编辑对应的 `.md` 文件即可：

| 文件 | 用途 | 模板变量 |
|------|------|----------|
| `prompts/supervisor.md` | Supervisor 决策 | `{available_agents}` |
| `prompts/react/think.md` | ReAct 思考 | `{task}`, `{iterations}`, `{tools}` |
| `prompts/plan/decompose.md` | Plan 分解 | `{task}`, `{tools}`, `{context}` |
| `prompts/plan/reflect.md` | Plan 反思 | `{task}`, `{plan_status}`, `{trigger}` |

编辑时保留模板变量占位符，例如 `{task}`、`{tools}` 等。这些变量会在运行时动态替换。

### 动态上下文注入

以下内容**不在** MD 文件中，由代码动态注入：
- `domain_knowledge`: 领域知识（通过 `build_system_prompt()`）
- `runtime`: 运行时变量（通过 `inject_runtime_vars()`）

### 提示词模板变量

不同 Agent 支持不同的模板变量：

**Supervisor**:
- `{available_agents}` - 可用 Agent 列表

**ReAct Think**:
- `{task}` - 当前任务
- `{iterations}` - 历史迭代记录
- `{tools}` - 可用工具列表

**Plan Decompose**:
- `{task}` - 原始任务
- `{tools}` - 可用工具
- `{context}` - 之前工作上下文

---

## 工具函数

`utils.py` 提供上下文注入和状态更新的工具函数：

```python
from src.agents.utils import (
    inject_knowledge,       # 注入领域知识到提示词
    inject_runtime_vars,    # 注入运行态变量
    build_system_prompt,    # 构建完整系统提示
    get_current_task,       # 获取分配的任务
    get_previous_results,   # 获取历史结果
    create_agent_message,   # 创建消息更新
    create_agent_result,    # 创建结果更新
)

# 使用示例
prompt = build_system_prompt(
    state=state,
    base_prompt="你是一个助手",
    include_knowledge=True,
    include_runtime=False,
)
# 结果:
# "你是一个助手
#
#  ## 领域知识
#  Python是一种高级编程语言..."
```

---

## Agent 注册中心

`registry.py` 提供统一的 Agent 创建机制：

```python
from src.agents.registry import AgentRegistry, AgentType, AgentConfig

# 使用注册中心创建 Agent
config = AgentConfig(
    name="my_agent",
    agent_type=AgentType.REACT,
    llm=llm,
    tools=[search_tool],
    max_react_steps=5,
)
agent = AgentRegistry.create_agent(config)

# 注册自定义 Agent 类型
AgentRegistry.register_factory(AgentType.CUSTOM, my_custom_factory)
```

---

## 添加新的 Agent 类型

1. 在 `src/agents/new_type/` 创建目录结构
2. 实现 `graph.py` 和 `nodes/`
3. 在 `registry.py` 注册工厂函数
4. 在 `__init__.py` 导出

示例:

```python
# src/agents/new_type/graph.py
from langgraph.graph import StateGraph, END
from ...core.state import MultiAgentState

def create_new_type_node(llm, name="new_agent", **kwargs):
    async def process(state: MultiAgentState):
        # 从 state 读取上下文
        task = state.get("task_context", {}).get("current_task", "")

        # 构建提示词（可注入领域知识）
        from ..utils import build_system_prompt
        prompt = build_system_prompt(state, f"处理任务: {task}")

        # 调用 LLM
        result = await llm.ainvoke(prompt)

        # 返回状态更新
        return {
            "messages": [AIMessage(content=result.content, name=name)],
            "task_context": {"agent_results": [{"agent": name, "result": result.content}]}
        }

    builder = StateGraph(MultiAgentState)
    builder.add_node("process", process)
    builder.set_entry_point("process")
    builder.add_edge("process", END)
    return builder.compile()
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| [supervisor.py](supervisor.py) | Supervisor 协调器实现 |
| [registry.py](registry.py) | Agent 类型注册中心 |
| [utils.py](utils.py) | 上下文注入工具函数 |
| [prompts/](prompts/) | 提示词模板文件目录 |
| [react/graph.py](react/graph.py) | ReAct 子图定义 |
| [plan/graph.py](plan/graph.py) | Plan 子图定义 |
| [../core/state.py](../core/state.py) | 状态定义 |
| [../knowledge/manager.py](../knowledge/manager.py) | 知识管理 |

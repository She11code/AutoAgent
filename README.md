# Auto-Agent

A multi-agent collaboration system built on LangGraph + LangChain, supporting **ReAct and Plan advanced Agent patterns**.

## Features

- **Two Agent Modes**
  - ReAct Agent: Observe-Think-Act loop
  - Plan Agent: Plan-Execute-Reflect loop

- **Multi-layer State Management**
  - Runtime State: Real-time synchronization with remote API
  - Domain Knowledge: Static knowledge injection into System Prompt
  - Conversation Memory: Historical message persistence
  - Task Context: Agent workspace

- **Flexible Configuration**
  - Agent Registry: Unified management of Agent types
  - Subgraph as Node: Flexible composition of various Agent modes
  - Multiple memory storage backends

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# Or use uv
uv sync
```

## Quick Start

```python
import asyncio
from langchain_anthropic import ChatAnthropic
from src.core.state import create_initial_state
from src.core.graph import create_app_with_agents
from src.agents import create_supervisor_node, create_react_node, create_plan_node

async def main():
    # Initialize LLM (Anthropic Claude)
    llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0,
    )

    # Create Agent nodes
    researcher = create_react_node(llm, tools=[], name="researcher", max_steps=3)
    coder = create_react_node(llm, tools=[], name="coder", max_steps=3)

    # Create Supervisor (specify available Agents)
    supervisor = create_supervisor_node(
        llm=llm,
        valid_agents={"researcher", "coder"},
    )

    # Create application
    app = create_app_with_agents(
        supervisor_node=supervisor,
        agent_nodes={
            "researcher": researcher,
            "coder": coder,
        },
        use_persistence=True,
    )

    # Create initial state
    state = create_initial_state(
        session_id="demo",
        user_id="user1",
    )
    state["messages"] = [{"role": "user", "content": "Write a Python function"}]

    # Run
    result = await app.ainvoke(
        state,
        config={"configurable": {"thread_id": "demo"}}
    )
    print(result["messages"][-1].content)

asyncio.run(main())
```

## Project Structure

```
Auto-Agent/
├── src/
│   ├── core/               # Core modules
│   │   ├── state.py        # State definitions
│   │   ├── reducers.py     # Custom reducers
│   │   └── graph.py        # StateGraph building
│   ├── agents/             # Agent implementations
│   │   ├── supervisor.py   # Supervisor routing (standalone class)
│   │   ├── registry.py     # Agent type registry
│   │   ├── utils.py        # Utility functions
│   │   ├── react/          # ReAct Agent (subgraph)
│   │   │   ├── graph.py
│   │   │   └── nodes/
│   │   │       ├── observe.py
│   │   │       ├── think.py
│   │   │       └── act.py
│   │   └── plan/           # Plan Agent (subgraph)
│   │       ├── graph.py
│   │       └── nodes/
│   │           ├── decompose.py
│   │           ├── execute.py
│   │           └── reflect.py
│   ├── sync/               # API sync layer
│   ├── knowledge/          # Domain knowledge management
│   └── memory/             # Memory management
├── config/                 # Configuration
├── examples/               # Examples
└── tests/                  # Tests
```

## Agent Modes

> See [src/agents/README.md](src/agents/README.md) for detailed documentation

### ReAct Agent
Observe-Think-Act loop, suitable for complex tasks requiring multiple iterations.

```python
from src.agents import create_react_node
react_agent = create_react_node(
    llm=llm,
    tools=[search_tool, code_tool],
    name="researcher",
    system_prompt="",  # Optional: custom prompt
    max_steps=5,
)
```

### Plan Agent
Plan-Execute-Reflect loop, suitable for complex tasks requiring decomposition.

```python
from src.agents import create_plan_node
plan_agent = create_plan_node(
    llm=llm,
    tools=[],
    name="planner",
    system_prompt="",  # Optional: custom prompt
    max_steps=10,
)
```

### Supervisor
Coordinator responsible for task decomposition and routing decisions.

```python
from src.agents import create_supervisor_node
supervisor = create_supervisor_node(
    llm=llm,
    valid_agents={"researcher", "coder"},
    system_prompt="",  # Optional: custom prompt
)
```

## Context Management

Agents read context from `MultiAgentState` during execution and inject it into prompts.

**Detailed Documentation**: [docs/context-flow.md](docs/context-flow.md) - LLM context data sources and data flow explained

```
┌──────────────────┐      ┌─────────────────────┐
│  MultiAgentState │ ──→  │  build_system_prompt │
└────────┬─────────┘      └──────────┬──────────┘
         │                           │
         ├─ domain_knowledge ────────┼─→ Inject domain knowledge
         ├─ runtime ─────────────────┼─→ Inject runtime variables
         ├─ task_context ────────────┼─→ Read tasks/history
         └─ messages ────────────────┴─→ Conversation history
                                     │
                                     ▼
                              LLM Prompt
```

**Only 3 nodes call LLM directly**:
- **Supervisor**: Reads messages, agent_results, plan_steps, task_status, plan_status
- **Think**: Reads current_task, plan_steps, react_iterations, tools
- **Decompose**: Reads task_assignments, tools, domain_knowledge

### Context Injection Utilities

```python
from src.agents.utils import (
    inject_knowledge,       # Inject domain knowledge
    inject_runtime_vars,    # Inject runtime variables
    build_system_prompt,    # Build complete prompt
    get_current_task,       # Get current task
    get_previous_results,   # Get historical results
)

# Custom prompt + context injection
prompt = build_system_prompt(
    state=state,
    base_prompt="You are an assistant",
    include_knowledge=True,
    include_runtime=False,
)
```

### Custom Prompts

Each Agent supports custom prompts via parameters or by modifying default constants:

| File | Default Constant | Template Variables |
|------|------------------|-------------------|
| `supervisor.py` | `DEFAULT_SUPERVISOR_PROMPT` | `{available_agents}` |
| `react/nodes/think.py` | `DEFAULT_THINK_PROMPT` | `{task}`, `{iterations}`, `{tools}` |
| `plan/nodes/decompose.py` | `DEFAULT_DECOMPOSE_PROMPT` | `{task}`, `{tools}`, `{context}` |

See [src/agents/README.md](src/agents/README.md) for details

## State Architecture

```
┌─────────────────────────────────────────────┐
│              MultiAgentState                │
├─────────────────────────────────────────────┤
│ messages: List[BaseMessage]  (add_messages) │
│ runtime: RuntimeState        (overwrite)    │
│ domain_knowledge: DomainKnowledge (overwrite)│
│ task_context: TaskContext    (append/overwrite)│
│ session_id: str                             │
│ user_id: str                                │
└─────────────────────────────────────────────┘
```

### Reducer Strategies

| Field | Reducer | Description |
|-------|---------|-------------|
| messages | add_messages | Append messages with deduplication |
| runtime | overwrite | Full replacement after API sync |
| domain_knowledge | overwrite | Injected at session start |
| task_assignments | operator.add | Cumulative task assignments |
| agent_results | operator.add | Cumulative agent results |

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# Anthropic Claude (required)
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# Remote API (optional)
REMOTE_API_BASE_URL=http://localhost:8080
```

## Examples

- [basic_usage.py](examples/basic_usage.py) - Basic usage
- [with_api_sync.py](examples/with_api_sync.py) - With API synchronization

## License

MIT

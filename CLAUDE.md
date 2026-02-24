# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Test, and Run Commands

```bash
# Install dependencies
pip install -e .

# Run tests
pytest
pytest tests/test_state.py -v                    # Single file
pytest tests/test_state.py::TestStateCreation::test_create_initial_state -v  # Single test

# Lint and format
ruff check src/
ruff format src/

# Run example
python examples/basic_usage.py
```

## Architecture Overview

Multi-agent system built on LangGraph using **Orchestrator-Worker pattern** with **subgraphs as nodes**.

```
START → Supervisor → [react_agent|plan_agent|...] → Supervisor → ... → END
```

Supervisor decomposes tasks and routes to specialized agents. Each agent is a compiled subgraph that processes and returns to Supervisor.

### Four-Layer State Architecture (`src/core/state.py`)

| Layer | Field | Reducer | Purpose |
|-------|-------|---------|---------|
| Conversation | `messages` | `add_messages` | Dialog history with deduplication |
| Runtime | `RuntimeState` | overwrite | Remote API variables, real-time sync |
| Knowledge | `DomainKnowledge` | overwrite | Static domain knowledge (<10KB) in system prompt |
| Task Context | `TaskContext` | `deep_merge_dict_reducer` | Agent assignments, status, results |

**Key insight**: Different lifecycles require different reducers. Messages accumulate, runtime/knowledge replace entirely, task context supports partial updates via `deep_merge_dict_reducer` in `src/core/reducers.py`.

### Agent Types (`src/agents/`)

| Type | Pattern | Use Case |
|------|---------|----------|
| **ReAct** | think → act → observe loop | Iterative tasks with tool use |
| **Plan** | decompose → execute → reflect | Complex multi-step tasks |

Both are **compiled subgraphs** using shared `MultiAgentState`, allowing them to be used as nodes in the parent graph.

### Supervisor (`src/agents/supervisor.py`)

The Supervisor uses structured output with `AgentDecision` Pydantic model to decide:
- `next_agent`: Which agent to route to (or "FINISH")
- `task_description`: Task assignment for the next agent
- `reasoning`: Decision rationale

### Key Files

| File | Purpose |
|------|---------|
| `src/core/state.py` | State definitions and factory functions |
| `src/core/reducers.py` | `deep_merge_dict_reducer` for nested dict updates |
| `src/core/graph.py` | `MultiAgentGraphBuilder`, `create_app_with_agents()` |
| `src/agents/registry.py` | `AgentType` enum, `AgentRegistry` for agent creation |
| `src/agents/supervisor.py` | `SupervisorAgent` class, structured output routing |
| `src/agents/utils.py` | `build_system_prompt()`, `inject_knowledge()`, context helpers |
| `src/agents/prompts/__init__.py` | `load_prompt()` function with caching |
| `config/settings.py` | Pydantic settings, `get_llm()` returns ChatAnthropic |

## Configuration

Copy `.env.example` to `.env`. Required: `ANTHROPIC_API_KEY`

The system supports Anthropic-compatible APIs (e.g., Zhipu GLM). Configure via:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (default: `claude-sonnet-4-5-20250929`)
- `ANTHROPIC_BASE_URL` (optional, for compatible APIs)

## Usage Pattern

```python
from src.agents import create_supervisor_node, create_react_node, create_plan_node
from src.core.graph import create_app_with_agents
from src.core.state import create_initial_state

# Create agent nodes (compiled subgraphs)
researcher = create_react_node(llm, tools=[search_tool], name="researcher", max_steps=5)
planner = create_plan_node(llm, tools=[], name="planner", max_steps=10)

# Create Supervisor
supervisor = create_supervisor_node(llm, valid_agents={"researcher", "planner"})

# Build application
app = create_app_with_agents(
    supervisor_node=supervisor,
    agent_nodes={"researcher": researcher, "planner": planner},
    use_persistence=True,
)

# Invoke
state = create_initial_state(session_id="demo", user_id="user1")
result = await app.ainvoke(state, config={"configurable": {"thread_id": "demo"}})
```

## Adding a New Agent Type

1. Create `src/agents/new_type/graph.py` with `create_new_type_node()` function
2. Add nodes in `src/agents/new_type/nodes/`
3. Register in `src/agents/registry.py`:
   ```python
   class AgentType(Enum):
       NEW_TYPE = "new_type"

   def _create_new_type_agent(config: AgentConfig):
       from .new_type import create_new_type_node
       return create_new_type_node(llm=config.llm, ...)

   AgentRegistry.register_factory(AgentType.NEW_TYPE, _create_new_type_agent)
   ```
4. Export from `src/agents/__init__.py`

## Custom Prompts

Edit markdown files in `src/agents/prompts/` or pass `system_prompt` parameter:

| File | Template Variables |
|------|-------------------|
| `prompts/supervisor.md` | `{available_agents}` |
| `prompts/react/think.md` | `{task}`, `{iterations}`, `{tools}` |
| `prompts/plan/decompose.md` | `{task}`, `{tools}`, `{context}` |
| `prompts/plan/reflect.md` | `{task}`, `{plan_status}`, `{trigger}` |

Prompts are loaded via `load_prompt("react/think")` from `src/agents/prompts/__init__.py` with caching.

## Tools (`src/tools/`)

Custom tool framework for defining vertical domain tools. Use `@register_tool` decorator:

```python
from src.tools import register_tool, ToolRegistry

@register_tool("search", "搜索内部知识库")
def search(query: str) -> str:
    return f"搜索 '{query}' 的结果..."

# In Agent
agent = create_react_node(llm, tools=ToolRegistry.get_all(), name="researcher")
```

See `src/tools/README.md` for details on prompt engineering with tool descriptions.

## Supporting Modules

| Module | Purpose |
|--------|---------|
| `src/tools/` | Tool framework (`@register_tool`, `ToolRegistry`) |
| `src/knowledge/manager.py` | `KnowledgeManager` for domain knowledge injection |
| `src/sync/` | API sync layer for runtime state |
| `src/memory/` | Checkpointer and store implementations |

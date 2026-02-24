# -*- coding: utf-8 -*-
"""
ReAct Agent Debug Script

Simulate ReAct execution and print prompts sent to LLM.
"""
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage


# ==================== Mock LLM for Debugging ====================
class MockLLM:
    """Mock LLM that prints the prompt and returns a simulated response"""

    def __init__(self, name="mock-llm"):
        self.name = name
        self.call_count = 0

    def with_structured_output(self, schema):
        return MockStructuredLLM(self, schema)

    async def ainvoke(self, messages):
        self.call_count += 1
        print(f"\n{'='*70}")
        print(f"[LLM CALL #{self.call_count}]")
        print(f"{'='*70}")

        for msg in messages:
            msg_type = type(msg).__name__
            print(f"\n--- {msg_type} ---")
            print(msg.content)

        # Simulate response
        return type('Response', (), {'content': f'[Mock Response {self.call_count}]'})


class MockStructuredLLM:
    """Mock structured output LLM"""

    def __init__(self, parent, schema):
        self.parent = parent
        self.schema = schema

    async def ainvoke(self, messages):
        self.parent.call_count += 1
        print(f"\n{'='*70}")
        print(f"[LLM CALL #{self.parent.call_count}] - Structured Output: {self.schema.__name__}")
        print(f"{'='*70}")

        for msg in messages:
            msg_type = type(msg).__name__
            print(f"\n--- {msg_type} ---")
            print(msg.content)

        # Return mock structured output based on call count
        if self.parent.call_count == 1:
            # First call: decide to search
            return self.schema(
                thought="User wants to know how to send HTTP requests in Python. I should search for this information.",
                action="search",
                action_input={"query": "Python HTTP requests library"},
                final_answer=None
            )
        else:
            # Second call: finish
            return self.schema(
                thought="I have gathered enough information about Python HTTP requests. The requests library is the standard way to send HTTP requests.",
                action="finish",
                action_input=None,
                final_answer="Python发送HTTP请求推荐使用requests库。\n\n基本用法:\n- GET请求: requests.get(url)\n- POST请求: requests.post(url, data={})\n- 添加headers: requests.get(url, headers={})"
            )


# ==================== Mock Tools ====================
def mock_search_tool(query: str) -> str:
    """Mock search tool"""
    return f"Search results for '{query}': requests is the most popular Python HTTP library. Usage: requests.get(url), requests.post(url, data=...)"


# ==================== Import and Run ====================
async def main():
    print("=" * 70)
    print("ReAct Agent Debug - Prompt Visualization")
    print("=" * 70)

    # Import after path setup
    from src.core.state import create_initial_state
    from src.agents.react.nodes.think import think_node, ThinkOutput
    from src.agents.react.nodes.act import act_node
    from src.agents.react.nodes.observe import observe_node
    from pydantic import BaseModel, Field

    # Create mock LLM
    llm = MockLLM()

    # Create initial state
    state = create_initial_state(
        session_id="debug-session",
        user_id="debug-user",
        domain_knowledge={
            "content": "Python是一种高级编程语言，支持多种编程范式。requests库是Python中最流行的HTTP客户端库。",
            "version": "1.0",
            "tags": ["python", "http", "requests"]
        }
    )

    # Set up task
    state["task_context"]["current_task"] = "如何用Python发送HTTP请求？"
    state["task_context"]["task_assignments"] = [
        {"agent": "researcher", "task": "如何用Python发送HTTP请求？"}
    ]

    # Simulate previous agent results
    state["task_context"]["agent_results"] = [
        {"agent": "planner", "result": "这是一个关于Python HTTP请求的问题，建议使用requests库解决。", "status": "completed"}
    ]

    # Tools
    tools = [
        type('Tool', (), {
            'name': 'search',
            'description': 'Search the internet for information',
            'invoke': lambda self, x: mock_search_tool(x.get('query', ''))
        })()
    ]

    # Create tools_map for act_node
    tools_map = {tool.name: tool for tool in tools}

    print("\n[Initial State]")
    print(f"  Task: {state['task_context']['current_task']}")
    print(f"  Domain Knowledge: {state['domain_knowledge']['content'][:50]}...")
    print(f"  Previous Results: {len(state['task_context']['agent_results'])} items")

    # ==================== Step 1: Think ====================
    print("\n" + "=" * 70)
    print("STEP 1: Think Node")
    print("=" * 70)

    result = await think_node(
        state=state,
        llm=llm,
        tools=tools,
        system_prompt="",
        agent_name="researcher",
        max_steps=5
    )

    # Update state
    state["task_context"].update(result["task_context"])
    print(f"\n[Think Result]")
    print(f"  Status: {state['task_context'].get('react_status')}")
    if state["task_context"].get("react_iterations"):
        last_iter = state["task_context"]["react_iterations"][-1]
        print(f"  Thought: {last_iter.get('thought')}")
        print(f"  Action: {last_iter.get('action')}")

    # ==================== Step 2: Act ====================
    if state["task_context"].get("react_status") == "acting":
        print("\n" + "=" * 70)
        print("STEP 2: Act Node")
        print("=" * 70)

        act_result = await act_node(
            state=state,
            tools_map=tools_map,
            agent_name="researcher"
        )

        state["task_context"].update(act_result.get("task_context", {}))
        print(f"\n[Act Result]")
        if act_result.get("messages"):
            print(f"  Message: {act_result['messages'][0].content[:100]}...")

        # ==================== Step 3: Observe ====================
        print("\n" + "=" * 70)
        print("STEP 3: Observe Node")
        print("=" * 70)

        observe_result = await observe_node(state)

        state["task_context"].update(observe_result.get("task_context", {}))
        print(f"\n[Observe Result]")
        if state["task_context"].get("react_iterations"):
            last_iter = state["task_context"]["react_iterations"][-1]
            print(f"  Observation: {last_iter.get('observation', 'N/A')[:100]}...")

        # ==================== Step 4: Think Again ====================
        print("\n" + "=" * 70)
        print("STEP 4: Think Node (Second Round)")
        print("=" * 70)

        result2 = await think_node(
            state=state,
            llm=llm,
            tools=tools,
            system_prompt="",
            agent_name="researcher",
            max_steps=5
        )

        state["task_context"].update(result2["task_context"])
        print(f"\n[Final Result]")
        print(f"  Status: {state['task_context'].get('react_status')}")
        if state["task_context"].get("react_final_answer"):
            print(f"  Answer: {state['task_context'].get('react_final_answer')}")

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

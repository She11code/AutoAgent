"""
Act Node for ReAct Pattern

行动节点负责：
- 执行选定的工具/行动
- 优雅处理工具错误
- 返回结果供观察
"""

from typing import Any, Dict, List

from langchain_core.messages import ToolMessage

from ....core.state import MultiAgentState


async def act_node(
    state: MultiAgentState,
    tools_map: Dict[str, Any],
    agent_name: str = "react_agent",
) -> Dict[str, Any]:
    """
    执行 think 节点决定的行动。

    从 state 中读取：
        - task_context.react_iterations[-1]: 包含 action 和 action_input

    返回：
        - 工具执行结果在 messages 中
        - react_status 设置为 "observing"
    """
    task_context = state.get("task_context", {})
    iterations = task_context.get("react_iterations", [])

    if not iterations:
        return {
            "task_context": {
                "react_status": "failed",
                "last_error": "没有要执行的行动",
            }
        }

    last_iteration = iterations[-1]
    action = last_iteration.get("action")
    action_input = last_iteration.get("action_input", {}) or {}

    # 如果是完成动作，不需要执行
    if action == "finish":
        return {
            "task_context": {
                "react_status": "completed",
            }
        }

    # 查找工具
    tool = tools_map.get(action) if tools_map else None

    if not tool:
        error_msg = f"未知工具: {action}。可用工具: {list(tools_map.keys()) if tools_map else '无'}"
        return {
            "messages": [ToolMessage(
                content=error_msg,
                tool_call_id="error",
                name="error"
            )],
            "task_context": {
                "react_status": "observing",
            }
        }

    # 执行工具
    try:
        # 支持同步和异步工具
        if hasattr(tool, 'ainvoke'):
            result = await tool.ainvoke(action_input)
        elif hasattr(tool, 'invoke'):
            result = tool.invoke(action_input)
        elif callable(tool):
            result = tool(**action_input) if isinstance(action_input, dict) else tool(action_input)
        else:
            result = str(tool)

        # 确保结果是字符串
        if not isinstance(result, str):
            result = str(result)

        tool_message = ToolMessage(
            content=result,
            tool_call_id=f"{action}_call",
            name=action
        )

        return {
            "messages": [tool_message],
            "task_context": {
                "react_status": "observing",
            }
        }

    except Exception as e:
        error_msg = f"工具执行错误 ({action}): {str(e)}"
        return {
            "messages": [ToolMessage(
                content=error_msg,
                tool_call_id="error",
                name=action
            )],
            "task_context": {
                "react_status": "observing",
            }
        }


def create_act_node(
    tools: List[Any],
    agent_name: str = "react_agent",
):
    """创建行动节点函数"""
    # 构建工具映射
    tools_map = {}
    for tool in tools:
        if hasattr(tool, 'name'):
            tools_map[tool.name] = tool
        else:
            tools_map[str(tool)] = tool

    async def node(state: MultiAgentState) -> Dict[str, Any]:
        return await act_node(
            state=state,
            tools_map=tools_map,
            agent_name=agent_name,
        )
    return node

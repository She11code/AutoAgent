"""
Act Node for ReAct Pattern

行动节点负责：
- 执行选定的工具/行动
- 优雅处理工具错误
- 返回结果供观察
"""

import json
from typing import Any, Dict, List

from langchain_core.messages import ToolMessage

from ....core.state import MultiAgentState
from ....utils import react_logger


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
    action_input = last_iteration.get("action_input")

    # 处理 action_input：确保是字典
    if action_input is None:
        action_input = {}
    elif isinstance(action_input, str):
        # LLM 可能返回字符串形式的 JSON，需要解析
        try:
            parsed = json.loads(action_input)
            if isinstance(parsed, dict):
                action_input = parsed
            else:
                # 如果解析结果不是字典，包装成字典
                action_input = {"input": parsed}
        except json.JSONDecodeError:
            # 不是 JSON 字符串，作为原始字符串参数
            action_input = {"input": action_input}

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
        react_logger.warning("[ACT] 工具未找到: %s, 可用工具: %s", action, list(tools_map.keys()))
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

    # 调试输出：工具调用前
    react_logger.debug("[ACT] 调用工具: %s", action)
    react_logger.debug("  action_input 类型: %s", type(action_input).__name__)
    react_logger.debug("  action_input 内容: %s", action_input)
    if hasattr(tool, 'description'):
        react_logger.debug("  工具描述: %s...", tool.description[:200])

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

        # 调试输出：工具调用结果
        react_logger.debug("[ACT] 工具返回成功: %d 字符", len(result))
        react_logger.debug("  结果内容: %s...", result[:500])

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
        import traceback
        error_msg = f"工具执行错误 ({action}): {str(e)}"
        react_logger.error("[ACT] 工具执行失败: %s", str(e))
        react_logger.debug("  堆栈: %s", traceback.format_exc())
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

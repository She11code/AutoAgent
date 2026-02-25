"""
Observe Node for ReAct Pattern

观察节点负责：
- 收集工具执行结果
- 格式化观察结果供推理使用
- 检查错误或失败情况
"""

from typing import Any, Dict

from ....core.state import MultiAgentState
from ....utils import react_logger


async def observe_node(state: MultiAgentState) -> Dict[str, Any]:
    """
    观察上一步行动的结果。

    从 state 中读取：
        - task_context.react_iterations: 迭代记录
        - task_context.plan_steps: 计划步骤
        - messages: 工具执行结果消息

    返回：
        - 更新 react_iterations 中的 observation 字段
        - 如果当前迭代对应计划步骤，更新 plan_steps 状态
        - react_status 设置为 "thinking" 继续循环
    """
    task_context = state.get("task_context", {})
    iterations = task_context.get("react_iterations", [])
    messages = state.get("messages", [])
    plan_steps = task_context.get("plan_steps", [])
    current_plan_index = task_context.get("current_plan_step_index", 0)

    # 如果没有迭代记录，说明是初始状态
    if not iterations:
        return {
            "task_context": {
                "react_status": "thinking",
            }
        }

    # 获取最后一次迭代
    last_iteration = iterations[-1]

    # 调试输出
    react_logger.debug("[OBSERVE] 观察节点:")
    react_logger.debug("  last_iteration action: %s", last_iteration.get('action'))
    react_logger.debug("  action_input: %s", last_iteration.get('action_input'))
    react_logger.debug("  messages count: %d", len(messages))

    # 从消息中提取观察结果（查找最后的工具消息或 AI 消息）
    observation = ""
    for msg in reversed(messages):
        if hasattr(msg, 'type'):
            if msg.type == 'tool':
                observation = msg.content
                break
            elif msg.type == 'ai' and hasattr(msg, 'tool_call_id'):
                # 如果是工具调用的响应
                continue

    # 如果没有找到工具结果，使用最后一条消息
    if not observation and messages:
        last_msg = messages[-1]
        if hasattr(last_msg, 'content'):
            observation = str(last_msg.content)

    # 调试输出：观察结果
    react_logger.debug("  observation 长度: %d 字符", len(observation))
    react_logger.debug("  observation 内容: %s...", observation[:500])

    # 更新最后一次迭代的观察结果
    # 由于使用 deep_merge_dict_reducer，我们需要返回更新后的完整迭代
    updated_iterations = list(iterations)
    if updated_iterations:
        updated_iterations[-1] = {
            **last_iteration,
            "observation": observation
        }

    # 更新计划步骤状态（如果有）
    updated_plan_steps = None
    new_plan_index = current_plan_index
    if plan_steps and last_iteration.get("plan_step_index") is not None:
        step_index = last_iteration["plan_step_index"]
        if step_index < len(plan_steps):
            # 标记当前步骤为完成
            updated_plan_steps = list(plan_steps)
            updated_plan_steps[step_index] = {
                **updated_plan_steps[step_index],
                "status": "completed",
                "result": observation,
            }
            # 推进到下一个计划步骤
            new_plan_index = step_index + 1

    result = {
        "task_context": {
            "react_iterations": updated_iterations,
            "react_status": "thinking",
            "current_plan_step_index": new_plan_index,
        }
    }

    # 如果更新了计划步骤，加入返回
    if updated_plan_steps:
        result["task_context"]["plan_steps"] = updated_plan_steps

    return result


def create_observe_node():
    """创建观察节点函数"""
    return observe_node

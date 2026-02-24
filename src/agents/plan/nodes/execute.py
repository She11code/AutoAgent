"""
Execute Node for Plan Pattern

执行节点负责：
- 执行当前计划步骤
- 更新步骤状态
- 处理执行错误
"""

from typing import Any, Dict, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ....core.state import MultiAgentState


async def execute_node(
    state: MultiAgentState,
    llm: BaseChatModel,
    tools_map: Dict[str, Any],
    agent_name: str = "plan_agent",
) -> Dict[str, Any]:
    """
    执行当前计划步骤。

    从 state 中读取：
        - task_context.plan_steps: 计划
        - task_context.current_step_index: 当前要执行的步骤索引

    返回：
        - 更新后的步骤（包含结果）
        - 执行结果消息
    """
    task_context = state.get("task_context", {})
    plan_steps = task_context.get("plan_steps", [])
    current_index = task_context.get("current_step_index", 0)

    # 检查是否所有步骤都已完成
    if current_index >= len(plan_steps):
        return {
            "task_context": {
                "plan_status": "completed",
            }
        }

    current_step = plan_steps[current_index]

    # 检查依赖是否满足
    dependencies_met = True
    for dep_id in current_step.get("dependencies", []):
        if 0 <= dep_id < len(plan_steps):
            if plan_steps[dep_id].get("status") != "completed":
                dependencies_met = False
                break

    if not dependencies_met:
        return {
            "task_context": {
                "plan_status": "reflecting",
                "reflection_notes": [f"步骤 {current_index} 的依赖未满足"],
                "needs_replan": True,
            }
        }

    # 标记为进行中
    updated_step = {**current_step, "status": "in_progress"}

    # 构建执行上下文
    step_prompt = f"""执行以下步骤：

## 步骤 {current_index}: {current_step['description']}

## 之前的执行结果：
"""
    for i, step in enumerate(plan_steps[:current_index]):
        if step.get("result"):
            step_prompt += f"### 步骤 {i}: {step['description']}\n{step['result']}\n\n"

    # 检查是否有工具可以执行此步骤
    step_description = current_step['description'].lower()
    tool_to_use = None

    if tools_map:
        for tool_name, tool in tools_map.items():
            if tool_name.lower() in step_description:
                tool_to_use = tool
                break

    try:
        # 如果找到合适的工具，使用工具
        if tool_to_use:
            if hasattr(tool_to_use, 'ainvoke'):
                result_text = await tool_to_use.ainvoke({"query": current_step['description']})
            elif hasattr(tool_to_use, 'invoke'):
                result_text = tool_to_use.invoke({"query": current_step['description']})
            else:
                result_text = str(tool_to_use)
        else:
            # 否则使用 LLM 执行
            response = await llm.ainvoke([
                SystemMessage(content="你是一个任务执行专家。"),
                HumanMessage(content=step_prompt + "\n请执行上述步骤并返回结果。")
            ])
            result_text = response.content

        # 确保结果是字符串
        if not isinstance(result_text, str):
            result_text = str(result_text)

        updated_step["status"] = "completed"
        updated_step["result"] = result_text

        # 更新计划步骤列表
        updated_steps = list(plan_steps)
        updated_steps[current_index] = updated_step

        return {
            "messages": [AIMessage(content=result_text, name=agent_name)],
            "task_context": {
                "plan_steps": updated_steps,
                "current_step_index": current_index + 1,
            }
        }

    except Exception as e:
        updated_step["status"] = "failed"
        updated_step["result"] = f"执行失败: {str(e)}"

        updated_steps = list(plan_steps)
        updated_steps[current_index] = updated_step

        return {
            "task_context": {
                "plan_steps": updated_steps,
                "plan_status": "reflecting",
                "reflection_notes": [f"步骤 {current_index} 执行失败: {str(e)}"],
                "needs_replan": True,
            }
        }


def create_execute_node(
    llm: BaseChatModel,
    tools: List[Any],
    agent_name: str = "plan_agent",
):
    """创建执行节点函数"""
    tools_map = {}
    for tool in tools:
        if hasattr(tool, 'name'):
            tools_map[tool.name] = tool
        else:
            tools_map[str(tool)] = tool

    async def node(state: MultiAgentState) -> Dict[str, Any]:
        return await execute_node(
            state=state,
            llm=llm,
            tools_map=tools_map,
            agent_name=agent_name,
        )
    return node

"""
Think Node for ReAct Pattern

思考节点负责：
- 分析当前情况
- 决定下一步行动或提供最终答案
- 更新推理链
"""

from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
from pydantic import BaseModel, Field

from ....core.state import MultiAgentState
from ....utils import react_logger
from ...prompts import load_prompt
from ...utils import build_system_prompt, get_previous_results, extract_chunk_content, parse_json_to_model


class ThinkOutput(BaseModel):
    """思考节点的结构化输出"""
    thought: str = Field(default="", description="推理过程和思考内容")
    action: Optional[str] = Field(
        default=None,
        description="要执行的工具名称，或 'finish' 表示完成任务"
    )
    action_input: Optional[Any] = Field(
        default=None,
        description="工具调用的参数。可以是字典或字符串。如果无参数，使用空字典 {} 或 null"
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="如果 action 是 'finish'，提供最终答案。使用 Markdown 格式。"
    )


async def think_node(
    state: MultiAgentState,
    llm: BaseChatModel,
    tools: List[Any],
    system_prompt: str = "",
    agent_name: str = "react_agent",
    max_steps: int = 5,
) -> Dict[str, Any]:
    """
    思考当前状态并决定下一步行动。

    从 state 中读取：
        - task_context.current_task: 当前任务
        - task_context.react_iterations: 之前的迭代记录
        - task_context.react_current_step: 当前步数
        - task_context.plan_steps: 计划步骤（由 Plan agent 生成）
        - domain_knowledge: 领域知识（用于构建提示）

    返回：
        - 新的 ReActIteration（包含 thought 和 action）
        - react_status: "acting" 或 "completed"
    """
    task_context = state.get("task_context", {})

    # 获取计划步骤
    plan_steps = task_context.get("plan_steps", [])
    current_plan_index = task_context.get("current_plan_step_index", 0)

    # 获取当前任务
    task = task_context.get("current_task", "")
    if not task:
        # 兜底：从最后一条用户消息获取
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                task = msg.content
                break

    iterations = task_context.get("react_iterations", [])
    current_step = task_context.get("react_current_step", 0)

    # 检查步数限制
    if current_step >= max_steps:
        # 达到最大步数，生成总结
        final_answer = "达到最大步数限制。"
        if iterations:
            # 使用最后一次思考作为答案
            for iter_data in reversed(iterations):
                if iter_data.get("observation"):
                    final_answer = iter_data["observation"]
                    break

        return {
            "task_context": {
                "react_status": "completed",
                "react_final_answer": final_answer,
            }
        }

    # 如果有计划步骤，检查是否全部完成
    if plan_steps:
        pending_steps = [s for s in plan_steps if s.get("status") == "pending"]
        if not pending_steps:
            # 所有计划步骤已完成
            completed_steps = [s for s in plan_steps if s.get("status") == "completed"]
            summary = f"所有计划步骤已完成（共 {len(completed_steps)} 步）"
            return {
                "task_context": {
                    "react_status": "completed",
                    "react_final_answer": summary,
                }
            }

    # 格式化计划步骤（如果有）
    plan_text = "无预设计划"
    if plan_steps:
        plan_lines = ["## 执行计划"]
        for i, step in enumerate(plan_steps):
            status_icon = "✅" if step.get("status") == "completed" else "⏳"
            plan_lines.append(
                f"{status_icon} 步骤 {i + 1}: {step.get('description', 'N/A')}"
            )
        plan_text = "\n".join(plan_lines)

    # 获取当前要执行的计划步骤
    current_plan_step = None
    if plan_steps and current_plan_index < len(plan_steps):
        current_plan_step = plan_steps[current_plan_index]

    # 格式化迭代历史
    iterations_text = ""
    for i, iter_data in enumerate(iterations):
        iterations_text += f"\n### 步骤 {i + 1}\n"
        iterations_text += f"**思考**: {iter_data.get('thought', 'N/A')}\n"
        iterations_text += f"**行动**: {iter_data.get('action', 'N/A')}\n"
        if iter_data.get('action_input'):
            iterations_text += f"**参数**: {iter_data.get('action_input')}\n"
        iterations_text += f"**观察**: {iter_data.get('observation', 'N/A')}\n"

    # 格式化工具列表
    tools_text = ""
    if tools:
        for tool in tools:
            if hasattr(tool, 'name'):
                desc = getattr(tool, 'description', 'No description')
                tools_text += f"- **{tool.name}**: {desc}\n"
            else:
                tools_text += f"- {str(tool)}\n"
    else:
        tools_text = "无可用工具（直接回答问题）"

    # 格式化其他 Agent 的上下文
    previous_results = get_previous_results(state)
    if previous_results:
        context_text = ""
        for r in previous_results:
            agent = r.get("agent", "unknown")
            result_preview = r.get("result", "")
            if len(result_preview) > 200:
                result_preview = result_preview[:200] + "..."
            context_text += f"- **{agent}**: {result_preview}\n"
    else:
        context_text = "无"

    # 构建提示
    prompt_template = system_prompt or load_prompt("react/think")

    # 如果有当前计划步骤，将其作为重点任务
    if current_plan_step:
        task_with_plan = f"""{task}

**当前计划步骤**: {current_plan_step.get('description', 'N/A')}
（计划步骤 {current_plan_index + 1}/{len(plan_steps)}）"""
    else:
        task_with_plan = task

    prompt = prompt_template.format(
        task=task_with_plan,
        iterations=iterations_text or "尚未开始",
        tools=tools_text,
        context=context_text
    )

    # 添加计划信息到提示
    if plan_steps:
        prompt = f"{prompt}\n\n{plan_text}"

    # 使用工具函数构建完整系统提示，统一通过 domain_knowledge 注入领域知识
    full_system_prompt = build_system_prompt(
        state,
        prompt,
        include_knowledge=True,  # 统一使用 build_system_prompt 注入领域知识
        include_runtime=False,
    )

    # === 流式调用 LLM ===
    # 不使用 with_structured_output()，因为它不支持流式
    # 改用 astream() + 手动解析 JSON

    # 构建要求 JSON 格式输出的提示
    json_format_hint = """

请严格按照以下 JSON 格式输出你的思考结果：
{
    "thought": "你的推理过程",
    "action": "工具名称或finish",
    "action_input": {"参数": "值"} 或 null,
    "final_answer": "如果action是finish，提供最终答案"
}
"""
    messages = [
        SystemMessage(content=full_system_prompt + json_format_hint),
        HumanMessage(content="请思考并决定下一步行动。")
    ]

    # 流式调用，累积 tokens
    full_content = ""
    async for chunk in llm.astream(messages):
        content = extract_chunk_content(chunk)
        if content:
            full_content += content

    print()  # 换行

    # === 解析 JSON 为 ThinkOutput ===
    result = parse_json_to_model(full_content, ThinkOutput, "THINK")

    # 调试输出
    react_logger.debug("=" * 60)
    react_logger.debug("[THINK] LLM 思考结果:")
    react_logger.debug("  thought: %s", result.thought)
    react_logger.debug("  action: %s", result.action)
    react_logger.debug("  action_input: %s", result.action_input)
    react_logger.debug("  final_answer: %s", result.final_answer)

    # 创建新的迭代记录
    new_iteration = {
        "thought": result.thought,
        "action": result.action,
        "action_input": result.action_input,
        "observation": None,  # 将由 observe 节点填充
        "plan_step_index": current_plan_index if plan_steps else None,
    }

    # 判断是否完成
    if result.action == "finish" or result.final_answer:
        new_iteration["action"] = "finish"
        return {
            "task_context": {
                "react_iterations": [new_iteration],
                "react_current_step": current_step + 1,
                "react_status": "completed",
                "react_final_answer": result.final_answer or "任务完成",
            }
        }

    # 继续执行行动
    return {
        "task_context": {
            "react_iterations": [new_iteration],
            "react_current_step": current_step + 1,
            "react_status": "acting",
        }
    }


def create_think_node(
    llm: BaseChatModel,
    tools: List[Any],
    system_prompt: str = "",
    agent_name: str = "react_agent",
    max_steps: int = 5,
):
    """创建思考节点函数"""
    async def node(state: MultiAgentState) -> Dict[str, Any]:
        return await think_node(
            state=state,
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            agent_name=agent_name,
            max_steps=max_steps,
        )
    return node

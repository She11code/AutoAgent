"""
Reflect Node for Plan Pattern

反思节点负责：
- 分析执行进度
- 决定是否需要重新规划
- 必要时调整计划
"""

from typing import Any, Dict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
from pydantic import BaseModel, Field

from ....core.state import MultiAgentState
from ...prompts import load_prompt
from ...utils import build_system_prompt, extract_chunk_content, parse_json_to_model


class ReflectionOutput(BaseModel):
    """反思节点的结构化输出"""
    should_continue: bool = Field(default=True, description="是否继续当前计划")
    adjustments_needed: bool = Field(default=False, description="是否需要调整计划")
    adjustment_notes: str = Field(default="", description="需要什么调整")
    overall_progress: str = Field(default="", description="目前进度总结")


async def reflect_node(
    state: MultiAgentState,
    llm: BaseChatModel,
    system_prompt: str = "",
    agent_name: str = "plan_agent",
) -> Dict[str, Any]:
    """
    反思计划执行进度。

    从 state 中读取：
        - task_context.plan_steps: 当前计划状态
        - task_context.reflection_notes: 触发反思的原因

    返回：
        - plan_status: "executing" 继续，或 "planning" 重新规划
        - 如需调整，更新计划
    """
    task_context = state.get("task_context", {})

    task = task_context.get("current_task", "")
    plan_steps = task_context.get("plan_steps", [])
    reflection_notes = task_context.get("reflection_notes", [])
    needs_replan = task_context.get("needs_replan", False)

    # 格式化计划状态
    plan_status_text = ""
    completed_count = 0
    failed_count = 0

    for step in plan_steps:
        status = step.get("status", "pending")
        plan_status_text += f"### 步骤 {step['step_id']}: {step['description']}\n"
        plan_status_text += f"状态: {status}\n"
        if step.get("result"):
            result = step.get("result", "")
            if len(result) > 200:
                result_preview = result[:200] + "..."
            else:
                result_preview = result
            plan_status_text += f"结果: {result_preview}\n"
        plan_status_text += "\n"

        if status == "completed":
            completed_count += 1
        elif status == "failed":
            failed_count += 1

    # 触发原因
    trigger = "\n".join(reflection_notes) if reflection_notes else "定期检查"

    # 如果已经标记需要重规划，直接返回
    if needs_replan:
        return {
            "task_context": {
                "plan_status": "planning",
                "needs_replan": True,
                "reflection_notes": [f"需要重新规划: {trigger}"],
            }
        }

    # 构建提示
    prompt_template = system_prompt or load_prompt("plan/reflect")
    prompt = prompt_template.format(
        task=task,
        plan_status=plan_status_text or "无计划",
        trigger=trigger
    )

    # 使用工具函数构建完整系统提示（注入领域知识）
    full_prompt = build_system_prompt(
        state,
        prompt,
        include_knowledge=True,
        include_runtime=False,
    )

    # === 流式调用 LLM ===
    # 不使用 with_structured_output()，因为它不支持流式
    # 改用 astream() + 手动解析 JSON

    # 构建要求 JSON 格式输出的提示
    json_format_hint = """

请严格按照以下 JSON 格式输出你的反思结果：
{
    "should_continue": true或false,
    "adjustments_needed": true或false,
    "adjustment_notes": "需要的调整说明",
    "overall_progress": "目前进度总结"
}
"""
    messages = [
        SystemMessage(content=full_prompt + json_format_hint),
        HumanMessage(content="请反思计划进度。")
    ]

    # 流式调用，累积 tokens
    full_content = ""
    async for chunk in llm.astream(messages):
        content = extract_chunk_content(chunk)
        if content:
            full_content += content

    print()  # 换行

    # === 解析 JSON 为 ReflectionOutput ===
    result = parse_json_to_model(full_content, ReflectionOutput, "REFLECT")

    # 根据反思结果决定下一步
    if result.adjustments_needed:
        # 需要重新规划
        return {
            "task_context": {
                "plan_status": "planning",
                "needs_replan": True,
                "reflection_notes": [result.adjustments_notes],
            }
        }

    # 继续当前计划
    return {
        "task_context": {
            "plan_status": "executing",
            "needs_replan": False,
            "reflection_notes": [result.overall_progress],
        }
    }


def create_reflect_node(
    llm: BaseChatModel,
    system_prompt: str = "",
    agent_name: str = "plan_agent",
):
    """创建反思节点函数"""
    async def node(state: MultiAgentState) -> Dict[str, Any]:
        return await reflect_node(
            state=state,
            llm=llm,
            system_prompt=system_prompt,
            agent_name=agent_name,
        )
    return node

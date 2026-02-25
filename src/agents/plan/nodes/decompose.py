"""
Decompose Node for Plan Pattern

分解节点负责：
- 将复杂任务拆解为子任务
- 创建有序的计划步骤
- 识别步骤间的依赖关系
"""

from typing import Any, Dict, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ....core.state import MultiAgentState
from ...prompts import load_prompt
from ...utils import build_system_prompt, extract_chunk_content, parse_json_to_model


class DecompositionOutput(BaseModel):
    """分解节点的结构化输出"""
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="计划步骤列表，每个步骤包含 description 和 dependencies"
    )
    reasoning: str = Field(default="", description="为什么选择这种分解方式")


async def decompose_node(
    state: MultiAgentState,
    llm: BaseChatModel,
    tools: List[Any],
    system_prompt: str = "",
    agent_name: str = "plan_agent",
) -> Dict[str, Any]:
    """
    将任务分解为计划步骤。

    从 state 中读取：
        - task_context.current_task: 要分解的任务
        - task_context.agent_results: 之前工作的上下文

    返回：
        - plan_steps: PlanStep 对象列表
        - plan_status: "completed" (分解完成，等待执行)
    """
    task_context = state.get("task_context", {})

    # 获取当前任务
    task = task_context.get("current_task", "")
    if not task:
        # 兜底：从最后一条用户消息获取
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                task = msg.content
                break

    # 获取之前的工作上下文
    context = task_context.get("agent_results", [])
    context_text = ""
    for r in context:
        agent_name_ctx = r.get("agent", "unknown")
        result = r.get("result", "")
        if len(result) > 200:
            preview = result[:200] + "..."
        else:
            preview = result
        context_text += f"- {agent_name_ctx}: {preview}\n"

    # 格式化工具列表（用于生成计划时参考）
    tools_text = ""
    if tools:
        for tool in tools:
            if hasattr(tool, 'name'):
                desc = getattr(tool, 'description', 'No description')
                # 截断过长的描述
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                tools_text += f"- **{tool.name}**: {desc}\n"
            else:
                tools_text += f"- {str(tool)}\n"
    else:
        tools_text = "无特定工具，使用通用推理能力"

    # 构建提示
    prompt_template = system_prompt or load_prompt("plan/decompose")
    prompt = prompt_template.format(
        task=task,
        tools=tools_text,
        context=context_text or "无"
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

请严格按照以下 JSON 格式输出你的分解结果：
{
    "steps": [
        {"description": "步骤描述", "dependencies": []}
    ],
    "reasoning": "为什么选择这种分解方式"
}
"""
    messages = [
        SystemMessage(content=full_prompt + json_format_hint),
        HumanMessage(content="请分解这个任务。")
    ]

    # 流式调用，累积 tokens
    full_content = ""
    async for chunk in llm.astream(messages):
        content = extract_chunk_content(chunk)
        if content:
            full_content += content

    print()  # 换行

    # === 解析 JSON 为 DecompositionOutput ===
    result = parse_json_to_model(full_content, DecompositionOutput, "DECOMPOSE")

    # 创建 PlanSteps
    plan_steps = []
    for i, step_data in enumerate(result.steps):
        plan_steps.append({
            "step_id": i,
            "description": step_data.get("description", f"步骤 {i + 1}"),
            "status": "pending",
            "result": None,
            "dependencies": step_data.get("dependencies", []),
        })

    # 如果没有生成步骤，创建一个默认步骤
    if not plan_steps:
        plan_steps.append({
            "step_id": 0,
            "description": task,
            "status": "pending",
            "result": None,
            "dependencies": [],
        })

    return {
        "task_context": {
            "plan_steps": plan_steps,
            "current_step_index": 0,
            "plan_status": "completed",  # 分解完成，等待 ReAct 执行
            "plan_reasoning": result.reasoning,
        }
    }


def create_decompose_node(
    llm: BaseChatModel,
    tools: List[Any],
    system_prompt: str = "",
    agent_name: str = "plan_agent",
):
    """创建分解节点函数"""
    async def node(state: MultiAgentState) -> Dict[str, Any]:
        return await decompose_node(
            state=state,
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            agent_name=agent_name,
        )
    return node

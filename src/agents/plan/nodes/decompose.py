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


class DecompositionOutput(BaseModel):
    """分解节点的结构化输出"""
    steps: List[Dict[str, Any]] = Field(
        description="计划步骤列表，每个步骤包含 description 和 dependencies"
    )
    reasoning: str = Field(description="为什么选择这种分解方式")




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
        - plan_status: "executing"
    """
    task_context = state.get("task_context", {})

    # 获取当前任务
    task = task_context.get("current_task", "")
    if not task:
        assignments = task_context.get("task_assignments", [])
        for assignment in reversed(assignments):
            if assignment.get("agent") == agent_name:
                task = assignment.get("task", "")
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
        tools_text = "无特定工具，使用通用推理能力"

    # 构建提示
    prompt_template = system_prompt or load_prompt("plan/decompose")
    prompt = prompt_template.format(
        task=task,
        tools=tools_text,
        context=context_text or "无"
    )

    # 注入领域知识
    domain_knowledge = state.get("domain_knowledge", {})
    knowledge_content = domain_knowledge.get("content", "")
    if knowledge_content:
        prompt += f"\n\n## 领域知识\n{knowledge_content}"

    # 调用 LLM 获取结构化输出
    structured_llm = llm.with_structured_output(DecompositionOutput)
    result = await structured_llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content="请分解这个任务。")
    ])

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
            "plan_status": "executing",
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

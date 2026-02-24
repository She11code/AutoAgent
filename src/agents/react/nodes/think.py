"""
Think Node for ReAct Pattern

思考节点负责：
- 分析当前情况
- 决定下一步行动或提供最终答案
- 更新推理链
"""

from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ....core.state import MultiAgentState
from ...prompts import load_prompt
from ...utils import build_system_prompt, get_previous_results


class ThinkOutput(BaseModel):
    """思考节点的结构化输出"""
    thought: str = Field(description="推理过程和思考内容")
    action: Optional[str] = Field(
        default=None,
        description="要执行的工具名称，或 'finish' 表示完成任务"
    )
    action_input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="工具调用的参数"
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="如果 action 是 'finish'，提供最终答案"
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
        - domain_knowledge: 领域知识（用于构建提示）

    返回：
        - 新的 ReActIteration（包含 thought 和 action）
        - react_status: "acting" 或 "completed"
    """
    task_context = state.get("task_context", {})

    # 获取当前任务
    task = task_context.get("current_task", "")
    if not task:
        # 尝试从 task_assignments 获取
        assignments = task_context.get("task_assignments", [])
        for assignment in reversed(assignments):
            if assignment.get("agent") == agent_name:
                task = assignment.get("task", "")
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

    # 获取领域知识
    domain_knowledge = state.get("domain_knowledge", {})
    knowledge_text = domain_knowledge.get("content", "无")

    # 构建提示
    prompt_template = system_prompt or load_prompt("react/think")
    prompt = prompt_template.format(
        task=task,
        iterations=iterations_text or "尚未开始",
        knowledge=knowledge_text,
        tools=tools_text,
        context=context_text
    )

    # 使用工具函数构建完整系统提示（知识已由模板控制，不再注入）
    full_system_prompt = build_system_prompt(
        state,
        prompt,
        include_knowledge=False,  # 知识已通过模板参数传入
        include_runtime=False,
    )

    # 调用 LLM 获取结构化输出
    structured_llm = llm.with_structured_output(ThinkOutput)
    result = await structured_llm.ainvoke([
        SystemMessage(content=full_system_prompt),
        HumanMessage(content="请思考并决定下一步行动。")
    ])

    # 创建新的迭代记录
    new_iteration = {
        "thought": result.thought,
        "action": result.action,
        "action_input": result.action_input,
        "observation": None,  # 将由 observe 节点填充
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

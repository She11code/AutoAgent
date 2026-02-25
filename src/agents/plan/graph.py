"""
Plan Agent Subgraph Definition

创建只负责任务分解的编译子图。
该子图可以作为节点添加到父 MultiAgentState 图中。

流程: init -> decompose -> finalize -> END
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from ...core.state import MultiAgentState
from ..prompts import load_prompt
from .nodes.decompose import decompose_node


@dataclass
class PlanAgentConfig:
    """Plan Agent 配置"""
    name: str = "plan_agent"
    llm: Optional[BaseChatModel] = None
    tools: List[Any] = field(default_factory=list)  # 用于生成计划时参考
    system_prompt: str = ""  # 如果为空，使用 load_prompt("plan/decompose")
    max_steps: int = 10


def create_plan_agent(config: PlanAgentConfig) -> Callable:
    """
    创建 Plan Agent 子图。

    子图使用共享的 MultiAgentState，可以直接作为节点添加到父图中。
    Plan Agent 只负责分解任务，不执行。执行由 ReAct Agent 负责。

    Args:
        config: PlanAgentConfig，包含 llm, tools 等

    Returns:
        编译后的子图，可作为节点使用
    """
    async def init_plan(state: MultiAgentState) -> Dict[str, Any]:
        """初始化计划状态"""
        task_context = state.get("task_context", {})

        # 直接从 current_task 获取（由 Supervisor 设置）
        task = task_context.get("current_task", "")

        # 兜底：从最后一条用户消息获取
        if not task:
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, 'type') and msg.type == 'human':
                    task = msg.content
                    break

        return {
            "task_context": {
                "plan_steps": [],
                "current_step_index": 0,
                "plan_status": "planning",
                "current_task": task,
            }
        }

    async def decompose(state: MultiAgentState) -> Dict[str, Any]:
        """分解节点"""
        return await decompose_node(
            state=state,
            llm=config.llm,
            tools=config.tools,
            system_prompt=config.system_prompt,
            agent_name=config.name,
        )

    async def finalize_plan(state: MultiAgentState) -> Dict[str, Any]:
        """编译最终结果"""
        task_context = state.get("task_context", {})
        plan_steps = task_context.get("plan_steps", [])

        # 构建计划摘要
        steps_text = []
        for step in plan_steps:
            step_id = step['step_id']
            description = step['description']
            deps = step.get('dependencies', [])
            deps_text = f" (依赖: {deps})" if deps else ""
            steps_text.append(f"  {step_id + 1}. {description}{deps_text}")

        if steps_text:
            final_result = (
                f"## 任务分解完成\n\n共 {len(plan_steps)} 个步骤:\n"
                + "\n".join(steps_text)
            )
        else:
            final_result = "任务分解完成，但没有生成步骤。"

        return {
            "messages": [AIMessage(content=final_result, name=config.name)],
            "task_context": {
                "plan_status": "completed",
                "agent_results": [{
                    "agent": config.name,
                    "result": final_result,
                    "status": "completed",
                    "plan_steps": plan_steps,
                }]
            }
        }

    # 使用共享的 MultiAgentState 构建子图
    builder = StateGraph(MultiAgentState)

    # 添加节点
    builder.add_node("init", init_plan)
    builder.add_node("decompose", decompose)
    builder.add_node("finalize", finalize_plan)

    # 设置入口点和边
    builder.set_entry_point("init")
    builder.add_edge("init", "decompose")
    builder.add_edge("decompose", "finalize")
    builder.add_edge("finalize", END)

    # 编译并返回
    return builder.compile()


def create_plan_node(
    llm: BaseChatModel,
    tools: List[Any] = None,
    name: str = "plan_agent",
    system_prompt: str = "",
    max_steps: int = 10,
) -> Callable:
    """
    便捷函数：创建 Plan Agent 节点。

    Plan Agent 只负责分解任务，不执行。执行由 ReAct Agent 负责。

    Args:
        llm: 语言模型
        tools: 工具列表（用于生成计划时参考）
        name: Agent 名称
        system_prompt: 系统提示词
        max_steps: 最大步骤数

    Returns:
        可作为节点使用的编译后子图
    """
    config = PlanAgentConfig(
        name=name,
        llm=llm,
        tools=tools or [],
        system_prompt=system_prompt or load_prompt("plan/decompose"),
        max_steps=max_steps,
    )
    return create_plan_agent(config)

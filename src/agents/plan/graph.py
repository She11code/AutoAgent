"""
Plan-Execute Agent Subgraph Definition

创建实现 Plan-Execute 模式的编译子图。
该子图可以作为节点添加到父 MultiAgentState 图中。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from ...core.state import MultiAgentState
from ..prompts import load_prompt
from .nodes.decompose import decompose_node
from .nodes.execute import execute_node
from .nodes.reflect import reflect_node


@dataclass
class PlanAgentConfig:
    """Plan Agent 配置"""
    name: str = "plan_agent"
    llm: Optional[BaseChatModel] = None
    tools: List[Any] = field(default_factory=list)
    system_prompt: str = ""  # 如果为空，使用 load_prompt("plan/decompose")
    max_steps: int = 10
    reflect_on_failure: bool = True


def route_plan_loop(state: MultiAgentState) -> Literal["decompose", "execute", "reflect", "finish"]:
    """
    根据计划状态路由。

    流程: decompose -> execute -> execute -> ... -> reflect(可选) -> finish
    """
    plan_status = state.get("task_context", {}).get("plan_status", "planning")

    if plan_status == "planning":
        return "decompose"
    elif plan_status == "executing":
        return "execute"
    elif plan_status == "reflecting":
        return "reflect"
    else:  # completed, failed
        return "finish"


def create_plan_agent(config: PlanAgentConfig) -> Callable:
    """
    创建 Plan-Execute Agent 子图。

    子图使用共享的 MultiAgentState，可以直接作为节点添加到父图中。

    Args:
        config: PlanAgentConfig，包含 llm, tools 等

    Returns:
        编译后的子图，可作为节点使用
    """
    # 构建工具映射
    tools_map = {}
    for tool in config.tools:
        if hasattr(tool, 'name'):
            tools_map[tool.name] = tool
        else:
            tools_map[str(tool)] = tool

    async def init_plan(state: MultiAgentState) -> Dict[str, Any]:
        """初始化计划状态"""
        task_context = state.get("task_context", {})

        # 从 task_assignments 获取任务
        task = ""
        assignments = task_context.get("task_assignments", [])
        for assignment in reversed(assignments):
            if assignment.get("agent") == config.name:
                task = assignment.get("task", "")
                break

        # 如果没有找到任务，使用用户的最后一条消息
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
                "reflection_notes": [],
                "needs_replan": False,
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

    async def execute(state: MultiAgentState) -> Dict[str, Any]:
        """执行节点"""
        return await execute_node(
            state=state,
            llm=config.llm,
            tools_map=tools_map,
            agent_name=config.name,
        )

    async def reflect(state: MultiAgentState) -> Dict[str, Any]:
        """反思节点"""
        return await reflect_node(
            state=state,
            llm=config.llm,
            agent_name=config.name,
        )

    async def finalize_plan(state: MultiAgentState) -> Dict[str, Any]:
        """编译最终结果"""
        task_context = state.get("task_context", {})
        plan_steps = task_context.get("plan_steps", [])

        # 汇总所有已完成步骤的结果
        results = []
        completed_count = 0
        failed_count = 0

        for step in plan_steps:
            status = step.get("status", "pending")
            step_id = step['step_id']
            description = step['description']
            result_text = step.get('result', '')

            if status == "completed":
                completed_count += 1
                results.append(f"### 步骤 {step_id}: {description}\n{result_text}")
            elif status == "failed":
                failed_count += 1
                results.append(f"### 步骤 {step_id}: {description}\n[失败] {result_text}")

        # 构建最终结果
        if results:
            header = f"## 计划执行完成\n\n完成: {completed_count}, 失败: {failed_count}\n\n"
            final_result = header + "\n\n".join(results)
        else:
            final_result = "计划执行完成，但没有生成结果。"

        return {
            "messages": [AIMessage(content=final_result, name=config.name)],
            "task_context": {
                "agent_results": [{
                    "agent": config.name,
                    "result": final_result,
                    "status": "completed",
                    "steps_completed": completed_count,
                    "steps_failed": failed_count,
                }]
            }
        }

    # 使用共享的 MultiAgentState 构建子图
    builder = StateGraph(MultiAgentState)

    # 添加节点
    builder.add_node("init", init_plan)
    builder.add_node("decompose", decompose)
    builder.add_node("execute", execute)
    builder.add_node("reflect", reflect)
    builder.add_node("finalize", finalize_plan)

    # 设置入口点
    builder.set_entry_point("init")

    # init -> decompose
    builder.add_edge("init", "decompose")

    # decompose 的条件路由
    builder.add_conditional_edges(
        "decompose",
        route_plan_loop,
        {
            "execute": "execute",
            "decompose": "decompose",  # 自循环重试
            "reflect": "reflect",
            "finish": "finalize",
        }
    )

    # execute 的条件路由
    builder.add_conditional_edges(
        "execute",
        route_plan_loop,
        {
            "execute": "execute",  # 继续下一步
            "reflect": "reflect",  # 需要反思
            "decompose": "decompose",  # 重新规划
            "finish": "finalize",  # 完成
        }
    )

    # reflect 的条件路由
    builder.add_conditional_edges(
        "reflect",
        route_plan_loop,
        {
            "execute": "execute",  # 反思后继续
            "decompose": "decompose",  # 需要重新规划
            "reflect": "reflect",  # 继续反思
            "finish": "finalize",
        }
    )

    # finalize -> END
    builder.add_edge("finalize", END)

    # 编译并返回
    return builder.compile()


def create_plan_node(
    llm: BaseChatModel,
    tools: List[Any] = None,
    name: str = "plan_agent",
    system_prompt: str = "",
    max_steps: int = 10,
    reflect_on_failure: bool = True,
) -> Callable:
    """
    便捷函数：创建 Plan Agent 节点。

    Args:
        llm: 语言模型
        tools: 工具列表
        name: Agent 名称
        system_prompt: 系统提示词
        max_steps: 最大步骤数
        reflect_on_failure: 失败时是否反思

    Returns:
        可作为节点使用的编译后子图
    """
    config = PlanAgentConfig(
        name=name,
        llm=llm,
        tools=tools or [],
        system_prompt=system_prompt or load_prompt("plan/decompose"),
        max_steps=max_steps,
        reflect_on_failure=reflect_on_failure,
    )
    return create_plan_agent(config)

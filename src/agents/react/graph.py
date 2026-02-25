"""
ReAct Agent Subgraph Definition

创建实现 ReAct (Reasoning + Acting) 模式的编译子图。
该子图可以作为节点添加到父 MultiAgentState 图中。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from ...core.state import MultiAgentState
from ..prompts import load_prompt
from .nodes.act import act_node
from .nodes.observe import observe_node
from .nodes.think import think_node


@dataclass
class ReActAgentConfig:
    """ReAct Agent 配置"""
    name: str = "react_agent"
    llm: Optional[BaseChatModel] = None
    tools: List[Any] = field(default_factory=list)
    system_prompt: str = ""  # 如果为空，使用 load_prompt("react/think")
    max_steps: int = 5


def route_react_loop(state: MultiAgentState) -> Literal["act", "observe", "think", "finish"]:
    """
    根据 ReAct 状态路由。

    流程: think -> act -> observe -> think -> ... -> finish
    """
    react_status = state.get("task_context", {}).get("react_status", "thinking")

    if react_status == "acting":
        return "act"
    elif react_status == "observing":
        return "observe"
    elif react_status in ("completed", "failed"):
        return "finish"
    else:  # "thinking"
        return "think"


def create_react_agent(config: ReActAgentConfig) -> Callable:
    """
    创建 ReAct Agent 子图。

    子图使用共享的 MultiAgentState，可以直接作为节点添加到父图中。

    Args:
        config: ReActAgentConfig，包含 llm, tools 等

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

    async def init_react(state: MultiAgentState) -> Dict[str, Any]:
        """初始化 ReAct 状态"""
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

        # 获取计划步骤
        plan_steps = task_context.get("plan_steps", [])

        return {
            "task_context": {
                "react_iterations": [],
                "react_current_step": 0,
                "react_max_steps": config.max_steps,
                "react_status": "thinking",
                "current_task": task,
                "react_final_answer": None,
                "plan_steps": plan_steps,
                "current_plan_step_index": 0,
            }
        }

    async def think(state: MultiAgentState) -> Dict[str, Any]:
        """思考节点"""
        return await think_node(
            state=state,
            llm=config.llm,
            tools=config.tools,
            system_prompt=config.system_prompt,
            agent_name=config.name,
            max_steps=config.max_steps,
        )

    async def act(state: MultiAgentState) -> Dict[str, Any]:
        """行动节点"""
        return await act_node(
            state=state,
            tools_map=tools_map,
            agent_name=config.name,
        )

    async def observe(state: MultiAgentState) -> Dict[str, Any]:
        """观察节点"""
        return await observe_node(state)

    async def finalize_react(state: MultiAgentState) -> Dict[str, Any]:
        """准备最终输出"""
        task_context = state.get("task_context", {})
        final_answer = task_context.get("react_final_answer", "任务完成")

        # 收集所有迭代的思考过程
        iterations = task_context.get("react_iterations", [])
        if iterations and not task_context.get("react_final_answer"):
            # 如果没有最终答案，使用最后一次观察
            for iter_data in reversed(iterations):
                if iter_data.get("observation"):
                    final_answer = iter_data["observation"]
                    break

        return {
            "messages": [AIMessage(content=final_answer, name=config.name)],
            "task_context": {
                "agent_results": [{
                    "agent": config.name,
                    "result": final_answer,
                    "status": "completed",
                    "iterations": len(iterations),
                }]
            }
        }

    # 使用共享的 MultiAgentState 构建子图
    builder = StateGraph(MultiAgentState)

    # 添加节点
    builder.add_node("init", init_react)
    builder.add_node("think", think)
    builder.add_node("act", act)
    builder.add_node("observe", observe)
    builder.add_node("finalize", finalize_react)

    # 设置入口点
    builder.set_entry_point("init")

    # init -> think
    builder.add_edge("init", "think")

    # think 节点的条件路由
    builder.add_conditional_edges(
        "think",
        route_react_loop,
        {
            "act": "act",
            "finish": "finalize",
            "think": "think",  # 自循环用于重试
            "observe": "observe",
        }
    )

    # act -> observe
    builder.add_edge("act", "observe")

    # observe -> think (继续循环)
    builder.add_edge("observe", "think")

    # finalize -> END
    builder.add_edge("finalize", END)

    # 编译并返回
    return builder.compile()


def create_react_node(
    llm: BaseChatModel,
    tools: List[Any] = None,
    name: str = "react_agent",
    system_prompt: str = "",
    max_steps: int = 5,
) -> Callable:
    """
    便捷函数：创建 ReAct Agent 节点。

    Args:
        llm: 语言模型
        tools: 工具列表
        name: Agent 名称
        system_prompt: 系统提示词
        max_steps: 最大步数

    Returns:
        可作为节点使用的编译后子图
    """
    config = ReActAgentConfig(
        name=name,
        llm=llm,
        tools=tools or [],
        system_prompt=system_prompt or load_prompt("react/think"),
        max_steps=max_steps,
    )
    return create_react_agent(config)

"""
Agents Module

包含 Supervisor、ReAct、Plan Agent 和工具函数。
"""

# Plan Agent
from .plan import PlanAgentConfig, create_plan_agent, create_plan_node

# ReAct Agent
from .react import ReActAgentConfig, create_react_agent, create_react_node
from .registry import AgentConfig, AgentRegistry, AgentType, create_agent_node
from .supervisor import AgentDecision, SupervisorAgent, create_supervisor_node
from .utils import (
    build_system_prompt,
    create_agent_message,
    create_agent_result,
    get_current_task,
    get_previous_results,
    inject_knowledge,
    inject_runtime_vars,
)

__all__ = [
    # Supervisor
    "SupervisorAgent",
    "AgentDecision",
    "create_supervisor_node",
    # Registry
    "AgentRegistry",
    "AgentType",
    "AgentConfig",
    "create_agent_node",
    # Utils
    "inject_knowledge",
    "inject_runtime_vars",
    "build_system_prompt",
    "get_current_task",
    "get_previous_results",
    "create_agent_message",
    "create_agent_result",
    # ReAct
    "create_react_agent",
    "create_react_node",
    "ReActAgentConfig",
    # Plan
    "create_plan_agent",
    "create_plan_node",
    "PlanAgentConfig",
]

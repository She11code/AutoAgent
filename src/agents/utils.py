"""
Agent 工具函数

提供 Agent 的通用工具函数，替代 BaseAgent 基类。
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from ..core.state import MultiAgentState


def inject_knowledge(state: MultiAgentState, prompt: str) -> str:
    """
    注入领域知识到提示词。

    Args:
        state: 当前状态
        prompt: 原始提示词

    Returns:
        包含领域知识的提示词
    """
    domain_knowledge = state.get("domain_knowledge", {})
    knowledge_content = domain_knowledge.get("content", "")

    if knowledge_content:
        prompt += f"\n\n## 领域知识\n{knowledge_content}"

    return prompt


def inject_runtime_vars(state: MultiAgentState, prompt: str) -> str:
    """
    注入运行态变量到提示词。

    Args:
        state: 当前状态
        prompt: 原始提示词

    Returns:
        包含运行态变量的提示词
    """
    runtime = state.get("runtime", {})
    external_vars = runtime.get("external_variables", {})

    if external_vars:
        json_str = json.dumps(external_vars, ensure_ascii=False, indent=2)
        prompt += f"\n\n## 运行时变量\n```json\n{json_str}\n```"

    return prompt


def build_system_prompt(
    state: MultiAgentState,
    base_prompt: str,
    include_knowledge: bool = True,
    include_runtime: bool = False,
) -> str:
    """
    构建完整的系统提示词。

    Args:
        state: 当前状态
        base_prompt: 基础提示词
        include_knowledge: 是否注入领域知识
        include_runtime: 是否注入运行态变量

    Returns:
        完整的系统提示词
    """
    prompt = base_prompt

    if include_knowledge:
        prompt = inject_knowledge(state, prompt)

    if include_runtime:
        prompt = inject_runtime_vars(state, prompt)

    return prompt


def get_current_task(state: MultiAgentState, agent_name: str) -> Optional[Dict[str, Any]]:
    """
    获取分配给指定 Agent 的任务。

    Args:
        state: 当前状态
        agent_name: Agent 名称

    Returns:
        任务字典或 None
    """
    task_assignments = state.get("task_context", {}).get("task_assignments", [])

    # 反向查找最后一个分配给该 Agent 的任务
    for task in reversed(task_assignments):
        if task.get("agent") == agent_name:
            return task

    return None


def get_previous_results(state: MultiAgentState) -> List[Dict[str, Any]]:
    """
    获取其他 Agent 的执行结果。

    Args:
        state: 当前状态

    Returns:
        Agent 结果列表
    """
    return state.get("task_context", {}).get("agent_results", [])


def create_agent_message(content: str, agent_name: str) -> Dict[str, Any]:
    """
    创建 Agent 消息更新。

    Args:
        content: 消息内容
        agent_name: Agent 名称

    Returns:
        状态更新字典
    """
    return {
        "messages": [AIMessage(content=content, name=agent_name)]
    }


def create_agent_result(
    agent_name: str,
    result: Any,
    status: str = "completed",
) -> Dict[str, Any]:
    """
    创建 Agent 结果更新。

    Args:
        agent_name: Agent 名称
        result: 结果内容
        status: 状态（completed, failed, skipped）

    Returns:
        状态更新字典
    """
    return {
        "task_context": {
            "agent_results": [{
                "agent": agent_name,
                "result": result,
                "status": status,
            }]
        }
    }

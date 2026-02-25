"""
Agent 工具函数

提供 Agent 的通用工具函数，替代 BaseAgent 基类。
"""

import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import BaseModel, ValidationError

from ..core.state import MultiAgentState

T = TypeVar('T', bound=BaseModel)


def extract_chunk_content(chunk: AIMessageChunk) -> Optional[str]:
    """
    从 AIMessageChunk 中提取文本内容。

    支持 Anthropic 流式格式：content 是 [{'text': 'xxx', 'type': 'text'}] 列表
    也支持标准格式：content 是字符串

    Args:
        chunk: AIMessageChunk 对象

    Returns:
        提取的文本内容，如果无法提取则返回 None
    """
    if not hasattr(chunk, 'content'):
        return None

    raw_content = chunk.content

    # 标准格式：content 是字符串
    if isinstance(raw_content, str):
        return raw_content

    # Anthropic 流式格式：content 是列表
    if isinstance(raw_content, list):
        for item in raw_content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text = item.get('text', '')
                if text:
                    return text

    return None


def parse_json_to_model(content: str, model_class: Type[T], node_name: str = "NODE") -> T:
    """
    从 LLM 输出内容中解析 JSON 到 Pydantic 模型。

    支持多种格式：
    1. 纯 JSON
    2. Markdown 代码块中的 JSON
    3. 混合文本中的 JSON

    Args:
        content: LLM 输出的完整内容
        model_class: 目标 Pydantic 模型类
        node_name: 节点名称（用于日志）

    Returns:
        解析后的 Pydantic 模型实例
    """
    json_patterns = [
        r'```json\s*([\s\S]*?)\s*```',  # Markdown JSON 代码块
        r'```\s*([\s\S]*?)\s*```',       # 普通代码块
        r'\{[\s\S]*\}',                   # 裸 JSON
    ]

    for pattern in json_patterns:
        match = re.search(pattern, content)
        if match:
            json_str = match.group(1) if '```' in pattern else match.group(0)
            try:
                data = json.loads(json_str.strip())
                return model_class(**data)
            except (json.JSONDecodeError, ValidationError):
                continue

    # 解析失败，尝试用默认值构造
    try:
        return model_class.model_construct(**{})
    except Exception:
        raise ValueError(f"[{node_name}] 无法解析 JSON 并构造默认模型: {content[:100]}...")


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


def get_current_task(state: MultiAgentState, agent_name: str = None) -> Optional[str]:
    """
    获取当前任务（简化版）

    优先从 task_context.current_task 获取，
    而不是从 task_assignments 查找。

    Args:
        state: 当前状态
        agent_name: 已废弃，保留参数兼容性

    Returns:
        当前任务字符串或空字符串
    """
    task_context = state.get("task_context", {})

    # 1. 优先从 current_task 获取
    task = task_context.get("current_task", "")
    if task:
        return task

    # 2. 兜底：从最后一条用户消息获取
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            return msg.content

    return ""


def get_turn_results(state: MultiAgentState, turn_id: str = None) -> List[Dict[str, Any]]:
    """
    获取指定轮次的 Agent 结果

    Args:
        state: 当前状态
        turn_id: 轮次 ID，为 None 时返回当前轮次结果

    Returns:
        该轮次的 agent_results 列表
    """
    task_context = state.get("task_context", {})
    results = task_context.get("agent_results", [])

    if turn_id is None:
        turn_id = task_context.get("turn_id", "")

    if not turn_id:
        return results[-3:] if results else []

    return [r for r in results if r.get("turn_id") == turn_id]


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

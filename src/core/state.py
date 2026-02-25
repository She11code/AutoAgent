"""
多层次状态管理定义

包含四个层次的状态：
1. RuntimeState - 程序运行态（远程API状态，实时同步）
2. DomainKnowledge - 领域知识层（静态知识注入到System Prompt）
3. TaskContext - 任务上下文（Agent工作空间）
4. MultiAgentState - 完整状态（包含对话记忆层）
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .reducers import deep_merge_dict_reducer, limit_list_reducer


class RuntimeState(TypedDict):
    """
    程序运行态 - 远程API状态

    特点：
    - 需要实时更新
    - 跟踪外部程序的变量
    - 生命周期：单次任务执行期间

    Reducer策略：覆盖更新
    """
    # 远程程序变量（每次LLM调用前同步）
    external_variables: Dict[str, Any]
    # API同步时间戳
    last_sync_timestamp: float
    # 同步状态标记
    sync_status: Literal["pending", "synced", "error"]
    # 最后一次API响应
    last_api_response: Optional[Dict[str, Any]]


class DomainKnowledge(TypedDict):
    """
    领域知识层 - 静态知识注入

    特点：
    - 小型静态知识（<10KB）
    - 生命周期：整个会话
    - 实现方式：直接注入到System Prompt

    Reducer策略：覆盖更新
    """
    # 知识内容
    content: str
    # 知识版本/哈希
    version: str
    # 知识类型标签
    tags: List[str]


class TaskContext(TypedDict):
    """
    Agent任务上下文 - 工作空间

    特点：
    - 跟踪任务分解和执行状态
    - 记录各Agent的输出结果

    Reducer策略：混合（限制追加/覆盖）
    """
    # 当前活跃Agent
    active_agent: str
    # 任务分配记录（限制追加，最多50条）
    task_assignments: Annotated[List[Dict[str, Any]], limit_list_reducer(50)]
    # 各Agent完成的子结果（限制追加，最多50条）
    agent_results: Annotated[List[Dict[str, Any]], limit_list_reducer(50)]
    # 任务状态
    task_status: Literal["planning", "executing", "reviewing", "completed"]
    # 错误信息（只保留最新）
    last_error: Optional[str]
    # 重试计数
    retry_count: int
    # 当前轮次任务描述（每次 Supervisor 分配时覆盖）
    current_task: str
    # 当前轮次分配的目标 Agent
    assigned_agent: str
    # 轮次 ID（用于追踪单次对话）
    turn_id: str
    # 已完成轮次计数
    completed_turns: int


class MultiAgentState(TypedDict):
    """
    完整的多Agent系统状态

    整合所有层次的状态管理：
    - 对话记忆层（messages）：使用 add_messages reducer
    - 程序运行态（runtime）：覆盖更新
    - 领域知识层（domain_knowledge）：覆盖更新
    - 任务上下文（task_context）：混合策略
    """
    # ========== 1. 对话记忆层 ==========
    # 使用 add_messages reducer：支持追加、去重、更新
    messages: Annotated[List[BaseMessage], add_messages]

    # ========== 2. 程序运行态 ==========
    runtime: RuntimeState

    # ========== 3. 领域知识层 ==========
    domain_knowledge: DomainKnowledge

    # ========== 4. Agent任务上下文 ==========
    # 使用 deep_merge_dict_reducer：支持部分字段更新
    task_context: Annotated[TaskContext, deep_merge_dict_reducer]

    # ========== 5. 用户会话信息 ==========
    # 会话ID（用于checkpointer隔离）
    session_id: str
    # 用户ID（用于长期记忆关联）
    user_id: str


# ========== 默认状态工厂函数 ==========

def create_default_runtime_state() -> RuntimeState:
    """创建默认的运行态状态"""
    return RuntimeState(
        external_variables={},
        last_sync_timestamp=0.0,
        sync_status="pending",
        last_api_response=None
    )


def create_default_domain_knowledge() -> DomainKnowledge:
    """创建默认的领域知识状态"""
    return DomainKnowledge(
        content="",
        version="",
        tags=[]
    )


def create_default_task_context() -> TaskContext:
    """创建默认的任务上下文状态"""
    return TaskContext(
        active_agent="",
        task_assignments=[],
        agent_results=[],
        task_status="planning",
        last_error=None,
        retry_count=0,
        current_task="",
        assigned_agent="",
        turn_id="",
        completed_turns=0,
    )


def create_initial_state(
    session_id: str,
    user_id: str,
    messages: Optional[List[BaseMessage]] = None,
    domain_knowledge: Optional[DomainKnowledge] = None,
    runtime: Optional[RuntimeState] = None,
    task_context: Optional[TaskContext] = None,
) -> MultiAgentState:
    """
    创建初始状态

    Args:
        session_id: 会话ID
        user_id: 用户ID
        messages: 初始消息列表
        domain_knowledge: 领域知识
        runtime: 运行态
        task_context: 任务上下文

    Returns:
        完整的初始状态
    """
    return MultiAgentState(
        messages=messages or [],
        runtime=runtime or create_default_runtime_state(),
        domain_knowledge=domain_knowledge or create_default_domain_knowledge(),
        task_context=task_context or create_default_task_context(),
        session_id=session_id,
        user_id=user_id,
    )

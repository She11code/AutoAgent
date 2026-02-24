"""
会话管理器

管理会话的创建、状态初始化和历史记录。
"""

from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.memory import InMemoryStore

from ..core.state import (
    create_default_domain_knowledge,
    create_default_runtime_state,
    create_initial_state,
)


class SessionManager:
    """
    会话管理器

    负责：
    - 创建和管理会话
    - 初始化会话状态
    - 管理长期记忆存储
    """

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver,
        use_store: bool = True,
    ):
        """
        初始化会话管理器

        Args:
            checkpointer: Checkpointer实例
            use_store: 是否使用长期记忆Store
        """
        self.checkpointer = checkpointer
        self.store = InMemoryStore() if use_store else None

    def create_session(
        self,
        session_id: str,
        user_id: str,
        initial_message: Optional[str] = None,
        domain_knowledge: Optional[Dict[str, Any]] = None,
        runtime_variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        创建新会话

        Args:
            session_id: 会话ID
            user_id: 用户ID
            initial_message: 初始用户消息
            domain_knowledge: 领域知识
            runtime_variables: 运行时变量

        Returns:
            包含config和initial_state的字典
        """
        config = {"configurable": {"thread_id": session_id}}

        # 构建初始消息
        messages = []
        if initial_message:
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(content=initial_message))

        # 构建运行态
        runtime = create_default_runtime_state()
        if runtime_variables:
            runtime["external_variables"] = runtime_variables

        # 构建领域知识
        knowledge = create_default_domain_knowledge()
        if domain_knowledge:
            knowledge.update(domain_knowledge)

        # 创建初始状态
        initial_state = create_initial_state(
            session_id=session_id,
            user_id=user_id,
            messages=messages,
            domain_knowledge=knowledge,
            runtime=runtime,
        )

        return {
            "config": config,
            "initial_state": initial_state,
        }

    def get_session_config(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话配置

        Args:
            session_id: 会话ID

        Returns:
            配置字典
        """
        return {"configurable": {"thread_id": session_id}}

    async def save_to_long_term_memory(
        self,
        user_id: str,
        key: str,
        value: Any,
        namespace: tuple = ("memories",),
    ):
        """
        保存到长期记忆

        Args:
            user_id: 用户ID
            key: 记忆键
            value: 记忆值
            namespace: 命名空间
        """
        if self.store is None:
            return

        full_namespace = namespace + (user_id,)
        self.store.put(full_namespace, key, value)

    async def get_from_long_term_memory(
        self,
        user_id: str,
        key: str,
        namespace: tuple = ("memories",),
    ) -> Optional[Any]:
        """
        从长期记忆获取

        Args:
            user_id: 用户ID
            key: 记忆键
            namespace: 命名空间

        Returns:
            记忆值或None
        """
        if self.store is None:
            return None

        full_namespace = namespace + (user_id,)
        item = self.store.get(full_namespace, key)
        return item.value if item else None

    async def search_long_term_memory(
        self,
        user_id: str,
        query: str,
        namespace: tuple = ("memories",),
        limit: int = 10,
    ):
        """
        搜索长期记忆

        Args:
            user_id: 用户ID
            query: 搜索查询
            namespace: 命名空间
            limit: 返回数量限制

        Returns:
            匹配的记忆列表
        """
        if self.store is None:
            return []

        full_namespace = namespace + (user_id,)
        # InMemoryStore的search方法
        try:
            results = self.store.search(full_namespace, query=query, limit=limit)
            return [item.value for item in results]
        except TypeError:
            # 如果不支持query参数，返回所有
            return []

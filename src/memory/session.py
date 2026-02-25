"""
会话管理器

管理会话的创建、状态初始化、元数据和生命周期。
支持 SQLite 持久化会话元数据。
"""

import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.memory import InMemoryStore

from ..core.state import (
    create_default_domain_knowledge,
    create_default_runtime_state,
    create_initial_state,
)


class SessionMeta(Dict[str, Any]):
    """
    会话元数据

    Attributes:
        session_id: 会话唯一标识
        user_id: 所属用户ID
        title: 会话标题
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
    """

    session_id: str
    user_id: str
    title: str
    created_at: float
    updated_at: float


class SessionManager:
    """
    会话管理器

    负责：
    - 创建、查询、删除会话
    - 会话元数据管理（支持 SQLite 持久化）
    - 长期记忆存储
    """

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver,
        metadata_db_path: str,
        use_store: bool = True,
    ):
        """
        初始化会话管理器

        Args:
            checkpointer: Checkpointer实例
            metadata_db_path: 元数据数据库路径
                - 文件路径: "sessions.db" 持久化到文件
                - ":memory:": 内存模式（测试用）
            use_store: 是否使用长期记忆Store
        """
        self.checkpointer = checkpointer
        self.store = InMemoryStore() if use_store else None

        # 元数据持久化
        self._meta_db_path = metadata_db_path
        self._lock = threading.Lock()  # 线程安全锁
        self._init_metadata_db()

    def _init_metadata_db(self):
        """初始化元数据数据库"""
        # check_same_thread=False 允许跨线程访问
        self._meta_conn = sqlite3.connect(self._meta_db_path, check_same_thread=False)
        self._meta_conn.execute("""
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._meta_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON session_meta(user_id)
        """)
        self._meta_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_updated_at ON session_meta(updated_at)
        """)
        self._meta_conn.commit()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, '_meta_conn'):
            self._meta_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ========== 数据库操作方法 ==========

    def _save_meta_to_db(self, meta: SessionMeta) -> None:
        """保存元数据到数据库"""
        with self._lock:
            self._meta_conn.execute("""
                INSERT OR REPLACE INTO session_meta
                (session_id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                meta["session_id"],
                meta["user_id"],
                meta["title"],
                meta["created_at"],
                meta["updated_at"],
            ))
            self._meta_conn.commit()

    def _get_meta_from_db(self, session_id: str) -> Optional[SessionMeta]:
        """从数据库获取元数据"""
        with self._lock:
            cursor = self._meta_conn.execute(
                """SELECT session_id, user_id, title, created_at, updated_at
                   FROM session_meta WHERE session_id = ?""",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return SessionMeta(
                    session_id=row[0],
                    user_id=row[1],
                    title=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
            return None

    def _list_user_sessions_from_db(self, user_id: str) -> List[SessionMeta]:
        """从数据库获取用户所有会话"""
        with self._lock:
            cursor = self._meta_conn.execute(
                """SELECT session_id, user_id, title, created_at, updated_at
                   FROM session_meta
                   WHERE user_id = ?
                   ORDER BY updated_at DESC""",
                (user_id,)
            )
            sessions = []
            for row in cursor.fetchall():
                sessions.append(SessionMeta(
                    session_id=row[0],
                    user_id=row[1],
                    title=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                ))
            return sessions

    def _delete_meta_from_db(self, session_id: str) -> bool:
        """从数据库删除元数据"""
        with self._lock:
            cursor = self._meta_conn.execute(
                "DELETE FROM session_meta WHERE session_id = ?",
                (session_id,)
            )
            self._meta_conn.commit()
            return cursor.rowcount > 0

    # ========== 会话创建 ==========

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

    # ========== 会话元数据管理 ==========

    async def create_session_with_meta(
        self,
        user_id: str,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_message: Optional[str] = None,
        domain_knowledge: Optional[Dict[str, Any]] = None,
        runtime_variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[SessionMeta, Dict[str, Any]]:
        """
        创建会话并记录元数据

        Args:
            user_id: 用户ID
            title: 会话标题（可选，默认自动生成）
            session_id: 会话ID（可选，默认自动生成UUID）
            initial_message: 初始用户消息
            domain_knowledge: 领域知识
            runtime_variables: 运行时变量

        Returns:
            (元数据, {config, initial_state})
        """
        session_id = session_id or str(uuid.uuid4())
        now = time.time()

        meta = SessionMeta(
            session_id=session_id,
            user_id=user_id,
            title=title or f"新会话 {self._format_time(now)}",
            created_at=now,
            updated_at=now,
        )

        # 保存到数据库
        self._save_meta_to_db(meta)

        # 创建会话状态
        result = self.create_session(
            session_id=session_id,
            user_id=user_id,
            initial_message=initial_message,
            domain_knowledge=domain_knowledge,
            runtime_variables=runtime_variables,
        )

        return meta, result

    async def list_user_sessions(self, user_id: str) -> List[SessionMeta]:
        """
        获取用户所有会话，按更新时间倒序

        Args:
            user_id: 用户ID

        Returns:
            会话元数据列表
        """
        return self._list_user_sessions_from_db(user_id)

    async def get_session_meta(self, session_id: str) -> Optional[SessionMeta]:
        """
        获取会话元数据

        Args:
            session_id: 会话ID

        Returns:
            会话元数据或None
        """
        return self._get_meta_from_db(session_id)

    async def update_session_meta(
        self,
        session_id: str,
        title: Optional[str] = None,
    ) -> Optional[SessionMeta]:
        """
        更新会话元数据

        Args:
            session_id: 会话ID
            title: 新标题（可选）

        Returns:
            更新后的元数据或None
        """
        meta = await self.get_session_meta(session_id)
        if meta:
            if title is not None:
                meta["title"] = title
            meta["updated_at"] = time.time()
            self._save_meta_to_db(meta)
            return meta
        return None

    async def touch_session(self, session_id: str) -> bool:
        """
        更新会话最后活跃时间

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        meta = await self.get_session_meta(session_id)
        if meta:
            meta["updated_at"] = time.time()
            self._save_meta_to_db(meta)
            return True
        return False

    async def delete_session(
        self,
        session_id: str,
        app=None,
    ) -> bool:
        """
        删除会话（元数据 + checkpointer 状态）

        Args:
            session_id: 会话ID
            app: 可选的图应用实例（CompiledStateGraph），用于清理 checkpointer 状态

        Returns:
            是否成功删除
        """
        # 1. 获取元数据确认存在
        meta = await self.get_session_meta(session_id)
        if not meta:
            return False

        # 2. 删除元数据
        self._delete_meta_from_db(session_id)

        # 3. 清理 checkpointer 状态（需要 app 实例）
        if app is not None:
            config = {"configurable": {"thread_id": session_id}}
            try:
                # LangGraph 的 checkpointer 清理
                current_state = await app.aget_state(config)
                if current_state.values:
                    # 通过设置为空状态来清理
                    await app.aupdate_state(config, None, as_node="__delete__")
            except Exception:
                pass  # 忽略清理错误

        # 4. 清理长期记忆（按用户维度，不清理）
        # 注：长期记忆是用户级别的，不应该在删除单个会话时清理

        return True

    async def delete_user_sessions(
        self,
        user_id: str,
        app=None,
    ) -> int:
        """
        删除用户所有会话

        Args:
            user_id: 用户ID
            app: 可选的图应用实例

        Returns:
            删除的会话数量
        """
        sessions = await self.list_user_sessions(user_id)
        count = 0
        for session in sessions:
            if await self.delete_session(session["session_id"], app=app):
                count += 1
        return count

    def _format_time(self, timestamp: float) -> str:
        """格式化时间戳"""
        return datetime.fromtimestamp(timestamp).strftime("%m-%d %H:%M")

    # ========== 长期记忆管理 ==========

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

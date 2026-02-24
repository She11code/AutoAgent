"""
记忆配置

提供不同级别的Checkpointer配置：
- 内存存储（开发测试）
- SQLite持久化（本地部署）
- PostgreSQL（生产环境）
"""

from typing import Optional

from langgraph.checkpoint.memory import MemorySaver

# SqliteSaver 需要单独安装: pip install langgraph-checkpoint-sqlite
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    HAS_SQLITE = True
except ImportError:
    SqliteSaver = None  # type: ignore
    HAS_SQLITE = False


class MemoryConfig:
    """
    记忆配置类

    提供创建不同类型Checkpointer的静态方法。
    """

    @staticmethod
    def short_term() -> MemorySaver:
        """
        短期记忆（内存存储）

        适用于开发、测试和临时会话。
        程序重启后数据丢失。

        Returns:
            MemorySaver实例
        """
        return MemorySaver()

    @staticmethod
    def persistent(db_path: str = "./checkpoints.db"):
        """
        持久化短期记忆（SQLite）

        适用于本地部署和需要持久化的场景。

        Args:
            db_path: SQLite数据库文件路径

        Returns:
            SqliteSaver实例

        Raises:
            ImportError: 如果未安装 langgraph-checkpoint-sqlite
        """
        if not HAS_SQLITE or SqliteSaver is None:
            raise ImportError(
                "请安装 langgraph-checkpoint-sqlite: "
                "pip install langgraph-checkpoint-sqlite"
            )
        return SqliteSaver.from_conn_string(db_path)

    @staticmethod
    def production(postgres_uri: str):
        """
        生产级记忆（PostgreSQL）

        适用于生产环境和分布式部署。
        需要安装额外的依赖：langgraph-checkpoint-postgres

        Args:
            postgres_uri: PostgreSQL连接字符串

        Returns:
            PostgresSaver实例
        """
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            return PostgresSaver.from_conn_string(postgres_uri)
        except ImportError:
            raise ImportError(
                "请安装 langgraph-checkpoint-postgres: "
                "pip install langgraph-checkpoint-postgres"
            )


def create_checkpointer(
    backend: str = "memory",
    db_path: Optional[str] = None,
    postgres_uri: Optional[str] = None,
):
    """
    创建Checkpointer的工厂函数

    Args:
        backend: 后端类型 ("memory", "sqlite", "postgres")
        db_path: SQLite数据库路径
        postgres_uri: PostgreSQL连接字符串

    Returns:
        Checkpointer实例

    Example:
        >>> checkpointer = create_checkpointer("memory")
        >>> checkpointer = create_checkpointer("sqlite", db_path="./data/checkpoints.db")
    """
    if backend == "memory":
        return MemoryConfig.short_term()
    elif backend == "sqlite":
        return MemoryConfig.persistent(db_path or "./checkpoints.db")
    elif backend == "postgres":
        if not postgres_uri:
            raise ValueError("PostgreSQL后端需要提供postgres_uri")
        return MemoryConfig.production(postgres_uri)
    else:
        raise ValueError(f"不支持的后端类型: {backend}")

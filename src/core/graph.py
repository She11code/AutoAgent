"""
多Agent协作图构建器

实现Orchestrator-Worker模式：
- Supervisor Agent负责任务分解和路由
- 专业Agent处理具体任务
"""

from typing import Callable, Dict, Set

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .state import MultiAgentState

# SqliteSaver 需要单独安装: pip install langgraph-checkpoint-sqlite
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    HAS_SQLITE = True
except ImportError:
    SqliteSaver = None  # type: ignore
    HAS_SQLITE = False


# ========== 路由函数 ==========

def create_route_supervisor(valid_agents: Set[str]) -> Callable:
    """
    创建 Supervisor 路由决策函数。

    Args:
        valid_agents: 有效的 Agent 名称集合

    Returns:
        路由函数
    """
    def route_supervisor(state: MultiAgentState) -> str:
        next_agent = state["task_context"]["active_agent"]

        if next_agent == "FINISH" or next_agent == "":
            return END

        if next_agent in valid_agents:
            return next_agent

        return END

    return route_supervisor


# ========== 图构建器类 ==========

class MultiAgentGraphBuilder:
    """
    多Agent图构建器

    负责构建完整的StateGraph，包括：
    - 添加所有节点
    - 设置边和条件边
    - 配置入口和出口
    """

    def __init__(
        self,
        supervisor_node: Callable,
        agent_nodes: Dict[str, Callable],
    ):
        """
        初始化图构建器

        Args:
            supervisor_node: Supervisor节点函数
            agent_nodes: Agent节点字典，key为节点名，value为节点函数或子图
        """
        self.supervisor_node = supervisor_node
        self.agent_nodes = agent_nodes
        self.builder = StateGraph(MultiAgentState)

        self._setup_nodes()
        self._setup_edges()

    def add_agent_node(self, name: str, node: Callable) -> None:
        """
        添加 Agent 节点（可以是简单函数或编译后的子图）

        Args:
            name: 节点名称
            node: 节点函数或编译后的子图
        """
        self.agent_nodes[name] = node
        self.builder.add_node(name, node)

    def get_valid_agents(self) -> Set[str]:
        """返回有效的 Agent 名称集合"""
        return set(self.agent_nodes.keys())

    def _setup_nodes(self):
        """设置所有节点"""
        self.builder.add_node("supervisor", self.supervisor_node)

        # 添加所有 Agent 节点
        for name, node in self.agent_nodes.items():
            self.builder.add_node(name, node)

    def _setup_edges(self):
        """设置所有边"""
        # 入口边：START -> supervisor
        self.builder.add_edge(START, "supervisor")

        # 获取有效的 Agent 列表
        valid_agents = self.get_valid_agents()

        # 创建路由映射
        route_map = {name: name for name in valid_agents}
        route_map[END] = END

        # Supervisor条件路由
        self.builder.add_conditional_edges(
            "supervisor",
            create_route_supervisor(valid_agents),
            route_map
        )

        # 所有Agent完成后返回Supervisor
        for agent_name in valid_agents:
            self.builder.add_edge(agent_name, "supervisor")

    def compile(self, checkpointer=None):
        """
        编译图

        Args:
            checkpointer: 可选的Checkpointer用于持久化

        Returns:
            编译后的可执行图
        """
        return self.builder.compile(checkpointer=checkpointer)


# ========== 工厂函数 ==========

def create_app_with_agents(
    agent_nodes: Dict[str, Callable],
    supervisor_node: Callable,
    use_persistence: bool = True,
    db_path: str = ":memory:",
):
    """
    创建应用实例

    支持任意 Agent 类型，包括 ReAct、Plan 等子图。

    Args:
        agent_nodes: Agent节点字典，key为节点名，value为节点函数或子图
        supervisor_node: Supervisor节点函数
        use_persistence: 是否启用持久化
        db_path: 数据库路径

    Returns:
        编译后的应用

    Example:
        from src.agents import create_react_node, create_plan_node, create_supervisor_node

        app = create_app_with_agents(
            supervisor_node=create_supervisor_node(llm),
            agent_nodes={
                "researcher": create_react_node(llm, tools=[search_tool]),
                "planner": create_plan_node(llm, tools=[]),
            }
        )
    """
    builder = MultiAgentGraphBuilder(
        supervisor_node=supervisor_node,
        agent_nodes=agent_nodes,
    )

    checkpointer = _get_checkpointer(use_persistence, db_path)
    return builder.compile(checkpointer=checkpointer)


def _get_checkpointer(use_persistence: bool, db_path: str):
    """获取 Checkpointer"""
    if not use_persistence:
        return None

    if db_path == ":memory:":
        return MemorySaver()

    if HAS_SQLITE and SqliteSaver is not None:
        return SqliteSaver.from_conn_string(db_path)

    return MemorySaver()


def create_simple_app(supervisor_node: Callable, agent_nodes: Dict[str, Callable]):
    """
    创建简单应用实例（无持久化）

    用于快速测试和开发

    Args:
        supervisor_node: Supervisor节点函数
        agent_nodes: Agent节点字典
    """
    return create_app_with_agents(
        supervisor_node=supervisor_node,
        agent_nodes=agent_nodes,
        use_persistence=False,
    )

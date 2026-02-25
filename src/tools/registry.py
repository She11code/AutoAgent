"""
工具注册中心

类似 AgentRegistry，提供工具的中央注册和管理。
"""

from typing import Callable, Dict, List, Optional, Union

from langchain_core.tools import BaseTool, StructuredTool


class ToolRegistry:
    """
    工具注册中心。

    提供工具的中央注册和管理，类似于 AgentRegistry 的设计模式。

    Usage:
        # 注册工具
        ToolRegistry.register(my_tool)
        ToolRegistry.register(my_func, name="echo", description="回显")

        # 获取工具
        tool = ToolRegistry.get("search")
        all_tools = ToolRegistry.get_all()
        tools_map = ToolRegistry.get_tools_map()  # 供 Agent 使用

        # 列出工具
        names = ToolRegistry.list_tools()

        # 清空
        ToolRegistry.clear()
    """

    _tools: Dict[str, BaseTool] = {}

    @classmethod
    def register(
        cls,
        tool: Union[BaseTool, Callable],
        name: Optional[str] = None,
        description: str = "",
    ) -> None:
        """
        注册工具。

        Args:
            tool: LangChain 工具或可调用函数
            name: 工具名称（仅当 tool 是普通函数时需要）
            description: 工具描述（仅当 tool 是普通函数时需要）

        Example:
            # 方式 1: 注册 LangChain 工具
            @tool
            def search(query: str) -> str:
                '''搜索知识库'''
                return "结果..."
            ToolRegistry.register(search)

            # 方式 2: 注册普通函数
            def my_func(query: str) -> str:
                return "结果..."
            ToolRegistry.register(my_func, name="my_tool", description="我的工具")
        """
        if callable(tool) and not isinstance(tool, BaseTool):
            # 自动包装普通函数为 LangChain 工具
            tool_name = name or tool.__name__
            tool_desc = description or tool.__doc__ or f"Tool: {tool_name}"
            # 使用 from_function 自动推断 args_schema
            tool = StructuredTool.from_function(
                func=tool,
                name=tool_name,
                description=tool_desc,
            )

        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """
        获取指定工具。

        Args:
            name: 工具名称

        Returns:
            工具实例，如果不存在返回 None
        """
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> List[BaseTool]:
        """
        获取所有已注册的工具。

        Returns:
            工具列表
        """
        return list(cls._tools.values())

    @classmethod
    def get_tools_map(cls) -> Dict[str, BaseTool]:
        """
        获取工具映射（供 Agent act_node 使用）。

        Returns:
            工具名称到工具实例的映射字典
        """
        return dict(cls._tools)

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        列出所有已注册的工具名称。

        Returns:
            工具名称列表
        """
        return list(cls._tools.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        注销指定工具。

        Args:
            name: 工具名称

        Returns:
            是否成功注销
        """
        if name in cls._tools:
            del cls._tools[name]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """清空所有已注册的工具。"""
        cls._tools.clear()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        检查工具是否已注册。

        Args:
            name: 工具名称

        Returns:
            是否已注册
        """
        return name in cls._tools


def register_tool(name: str, description: str = "") -> Callable:
    """
    装饰器：注册工具到 ToolRegistry。

    Args:
        name: 工具名称
        description: 工具描述（如果为空，使用函数的 docstring 或默认描述）

    Returns:
        装饰器函数

    Example:
        @register_tool("search", "搜索内部知识库")
        def search(query: str) -> str:
            return f"搜索 '{query}' 的结果..."

        # 等价于:
        # from src.tools import create_tool, ToolRegistry
        # tool = create_tool("search", "搜索内部知识库", search)
        # ToolRegistry.register(tool)
    """
    def decorator(func: Callable) -> Callable:
        # 使用 from_function 自动推断 args_schema
        tool_desc = description or func.__doc__ or f"Tool: {name}"
        decorated = StructuredTool.from_function(
            func=func,
            name=name,
            description=tool_desc,
        )
        # 注册到注册中心
        ToolRegistry.register(decorated)
        return decorated

    return decorator

"""
工具模块

提供自定义工具的定义和注册功能，与现有 Agent 系统无缝集成。

Quick Start:
    # 方式 1: 使用 @tool 装饰器（推荐）
    from src.tools import tool, ToolRegistry

    @tool
    def search(query: str) -> str:
        '''搜索内部知识库'''
        return "结果..."

    ToolRegistry.register(search)

    # 方式 2: 使用 @register_tool 装饰器
    from src.tools import register_tool

    @register_tool("search", "搜索内部知识库")
    def search(query: str) -> str:
        return "结果..."

    # 方式 3: 使用 create_tool 函数
    from src.tools import create_tool, ToolRegistry

    def my_func(query: str) -> str:
        return "结果..."

    tool = create_tool("my_tool", "工具描述", my_func)
    ToolRegistry.register(tool)

    # 在 Agent 中使用
    from src.agents import create_react_node

    agent = create_react_node(
        llm=llm,
        tools=ToolRegistry.get_all(),
        name="researcher",
    )
"""

# 从 LangChain 重新导出常用工具类
from langchain_core.tools import BaseTool, StructuredTool, tool

# 本地模块
from .base import ToolError, create_tool
from .registry import ToolRegistry, register_tool

__all__ = [
    # LangChain 工具（重新导出，方便使用）
    "tool",
    "BaseTool",
    "StructuredTool",
    # 本地工具
    "ToolRegistry",
    "register_tool",
    "create_tool",
    "ToolError",
]

"""
工具基类和辅助函数

提供工具定义的基础组件。
"""

from typing import Callable, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class ToolError(Exception):
    """
    工具执行错误。

    用于在工具执行过程中抛出结构化错误信息。

    Example:
        raise ToolError("search", "查询参数不能为空")
    """

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"[{tool_name}] {message}")


def create_tool(
    name: str,
    description: str,
    func: Callable,
    args_schema: Optional[type[BaseModel]] = None,
) -> StructuredTool:
    """
    便捷函数：从普通函数创建工具。

    Args:
        name: 工具名称
        description: 工具描述（用于 LLM 理解工具用途）
        func: 工具执行函数
        args_schema: 可选的参数 Schema（Pydantic BaseModel）

    Returns:
        StructuredTool 实例

    Example:
        def search(query: str) -> str:
            '''搜索内部知识库'''
            return "结果..."

        tool = create_tool(
            name="search",
            description="搜索内部知识库",
            func=search,
        )
    """
    return StructuredTool(
        name=name,
        description=description,
        func=func,
        args_schema=args_schema,
    )

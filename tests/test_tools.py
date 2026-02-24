"""
工具模块测试
"""

import pytest

from src.tools import (
    ToolRegistry,
    ToolError,
    create_tool,
    register_tool,
    tool,
    StructuredTool,
)


class TestToolError:
    """测试 ToolError 异常类"""

    def test_tool_error_creation(self):
        """测试创建工具错误"""
        error = ToolError("search", "查询参数不能为空")
        assert error.tool_name == "search"
        assert error.message == "查询参数不能为空"
        assert "[search]" in str(error)
        assert "查询参数不能为空" in str(error)


class TestCreateTool:
    """测试 create_tool 函数"""

    def test_create_tool_basic(self):
        """测试创建基础工具"""
        def my_func(query: str) -> str:
            return f"结果: {query}"

        my_tool = create_tool(
            name="my_tool",
            description="测试工具",
            func=my_func,
        )

        assert my_tool.name == "my_tool"
        assert my_tool.description == "测试工具"
        assert "test" in my_tool.invoke({"query": "test"})

    def test_create_tool_with_args_schema(self):
        """测试带参数 Schema 的工具"""
        from pydantic import BaseModel, Field

        class MyInput(BaseModel):
            query: str = Field(description="查询内容")
            limit: int = Field(default=10, description="限制数量")

        def my_func(query: str, limit: int = 10) -> str:
            return f"查询: {query}, 限制: {limit}"

        my_tool = create_tool(
            name="my_tool",
            description="测试工具",
            func=my_func,
            args_schema=MyInput,
        )

        assert my_tool.name == "my_tool"
        assert my_tool.args_schema == MyInput


class TestToolRegistry:
    """测试 ToolRegistry 注册中心"""

    def setup_method(self):
        """每个测试前清空注册中心"""
        ToolRegistry.clear()

    def teardown_method(self):
        """每个测试后清空注册中心"""
        ToolRegistry.clear()

    def test_register_and_get(self):
        """测试注册和获取工具"""
        @tool
        def test_func(query: str) -> str:
            """测试工具"""
            return f"结果: {query}"

        ToolRegistry.register(test_func)

        # 验证注册成功
        assert ToolRegistry.is_registered("test_func")
        assert ToolRegistry.get("test_func") is not None
        assert ToolRegistry.get("test_func").name == "test_func"

    def test_register_plain_function(self):
        """测试注册普通函数"""
        def my_func(query: str) -> str:
            return f"结果: {query}"

        ToolRegistry.register(my_func, name="my_tool", description="我的工具")

        assert ToolRegistry.is_registered("my_tool")
        retrieved = ToolRegistry.get("my_tool")
        assert retrieved is not None
        assert "test" in retrieved.invoke({"query": "test"})

    def test_get_all(self):
        """测试获取所有工具"""
        @tool
        def tool1(query: str) -> str:
            """工具1"""
            return query

        @tool
        def tool2(query: str) -> str:
            """工具2"""
            return query

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)

        all_tools = ToolRegistry.get_all()
        assert len(all_tools) == 2
        names = [t.name for t in all_tools]
        assert "tool1" in names
        assert "tool2" in names

    def test_get_tools_map(self):
        """测试获取工具映射"""
        @tool
        def search(query: str) -> str:
            """搜索工具"""
            return query

        ToolRegistry.register(search)

        tools_map = ToolRegistry.get_tools_map()
        assert isinstance(tools_map, dict)
        assert "search" in tools_map
        assert tools_map["search"].name == "search"

    def test_list_tools(self):
        """测试列出工具"""
        @tool
        def tool_a(x: str) -> str:
            """工具A"""
            return x

        @tool
        def tool_b(x: str) -> str:
            """工具B"""
            return x

        ToolRegistry.register(tool_a)
        ToolRegistry.register(tool_b)

        names = ToolRegistry.list_tools()
        assert "tool_a" in names
        assert "tool_b" in names
        assert len(names) == 2

    def test_unregister(self):
        """测试注销工具"""
        @tool
        def temp_tool(x: str) -> str:
            """临时工具"""
            return x

        ToolRegistry.register(temp_tool)
        assert ToolRegistry.is_registered("temp_tool")

        # 注销
        result = ToolRegistry.unregister("temp_tool")
        assert result is True
        assert not ToolRegistry.is_registered("temp_tool")

        # 注销不存在的工具
        result = ToolRegistry.unregister("not_exists")
        assert result is False

    def test_clear(self):
        """测试清空工具"""
        @tool
        def tool1(x: str) -> str:
            """工具1"""
            return x

        @tool
        def tool2(x: str) -> str:
            """工具2"""
            return x

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)

        ToolRegistry.clear()

        assert len(ToolRegistry.list_tools()) == 0
        assert ToolRegistry.get("tool1") is None


class TestRegisterToolDecorator:
    """测试 @register_tool 装饰器"""

    def setup_method(self):
        ToolRegistry.clear()

    def teardown_method(self):
        ToolRegistry.clear()

    def test_register_tool_decorator(self):
        """测试装饰器注册工具"""
        @register_tool("search", "搜索知识库")
        def search(query: str) -> str:
            return f"搜索结果: {query}"

        # 验证已注册
        assert ToolRegistry.is_registered("search")
        retrieved = ToolRegistry.get("search")
        assert retrieved is not None
        assert "test" in retrieved.invoke({"query": "test"})

    def test_register_tool_without_description(self):
        """测试无描述的装饰器"""
        @register_tool("echo")
        def echo(text: str) -> str:
            return text

        assert ToolRegistry.is_registered("echo")


class TestToolIntegration:
    """测试工具与 Agent 的集成"""

    def setup_method(self):
        ToolRegistry.clear()

    def teardown_method(self):
        ToolRegistry.clear()

    def test_tool_has_required_interface(self):
        """测试工具具有所需接口"""
        @register_tool("test", "测试工具")
        def test_func(query: str) -> str:
            return f"结果: {query}"

        tool_instance = ToolRegistry.get("test")

        # 验证接口
        assert hasattr(tool_instance, "name")
        assert hasattr(tool_instance, "description")
        assert hasattr(tool_instance, "invoke")

        # 验证可以用于 Agent 的 tools_map
        tools_map = ToolRegistry.get_tools_map()
        assert "test" in tools_map
        assert tools_map["test"] == tool_instance

    def test_tool_invoke_works(self):
        """测试工具执行"""
        @register_tool("calculator", "计算器")
        def calculate(expression: str) -> str:
            try:
                result = eval(expression)
                return str(result)
            except Exception as e:
                return f"错误: {e}"

        calc = ToolRegistry.get("calculator")
        assert calc is not None

        # 测试执行
        result = calc.invoke({"expression": "2+3"})
        assert "5" in result

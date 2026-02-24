# Tools 工具模块

自定义工具的定义和注册框架，与 Agent 系统无缝集成。

## 快速开始

```python
from src.tools import register_tool, ToolRegistry
from src.agents import create_react_node

# 1. 定义工具
@register_tool("search", """
搜索内部知识库。

参数:
  query: 搜索关键词

返回:
  相关文档列表
""")
def search(query: str) -> str:
    # 你的垂直领域逻辑
    return f"搜索 '{query}' 的结果..."

# 2. 在 Agent 中使用
agent = create_react_node(
    llm=llm,
    tools=ToolRegistry.get_all(),
    name="researcher",
)
```

## API

### @register_tool 装饰器

```python
@register_tool(name: str, description: str = "")
def my_tool(arg: str) -> str:
    ...
```

| 参数 | 说明 |
|------|------|
| `name` | 工具名称，用于 LLM 识别 |
| `description` | 工具描述，写入提示词，建议详细写明参数和返回值 |

### ToolRegistry 注册中心

```python
# 获取所有工具
tools = ToolRegistry.get_all()

# 获取工具映射（供 act_node 使用）
tools_map = ToolRegistry.get_tools_map()

# 获取单个工具
tool = ToolRegistry.get("search")

# 列出所有工具名称
names = ToolRegistry.list_tools()

# 检查工具是否已注册
ToolRegistry.is_registered("search")

# 注销工具
ToolRegistry.unregister("search")

# 清空所有工具
ToolRegistry.clear()
```

## 提示词工程建议

工具描述会直接写入 LLM 提示词，建议包含：

1. **功能说明** - 工具做什么
2. **参数描述** - 每个参数的含义和格式
3. **返回值** - 返回内容的格式
4. **使用场景** - 什么时候该用这个工具

```python
@register_tool("query_database", """
查询产品数据库。

参数:
  product_id: 产品ID，格式为 "P001"
  fields: 要查询的字段列表，如 ["name", "price", "stock"]

返回:
  JSON 格式的产品信息

使用场景:
  - 查询产品详情
  - 检查库存状态
  - 获取价格信息
""")
def query_database(product_id: str, fields: list) -> str:
    ...
```

## 文件结构

```
src/tools/
├── __init__.py    # 模块入口
├── base.py        # ToolError, create_tool
├── registry.py    # ToolRegistry, register_tool
└── README.md      # 本文档
```

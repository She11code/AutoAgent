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
5. **示例** - 参数和返回值示例（使用表格或代码块）

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
├── rimworld.py    # RimWorld 游戏控制工具集
└── README.md      # 本文档
```

## 内置工具集

### RimWorld 工具集 (`rimworld.py`)

用于控制 RimWorld 游戏的 AI 助手工具，通过 WebSocket 连接游戏。

**安装依赖**:
```bash
pip install websocket-client
# 或
pip install -e ".[rimworld]"
```

**连接信息**:
- 协议: WebSocket
- 默认端口: 8080
- 端点: `ws://localhost:8080/ai`

**使用方式**:
```python
# 导入即自动注册
from src.tools.rimworld import *
from src.tools import ToolRegistry

# 查看已注册工具
print(ToolRegistry.list_tools())
```

#### 工具分类

| 分类 | 工具 | 说明 |
|------|------|------|
| **连接管理** | `ping_rimworld` | 测试连接 |
| | `disconnect_rimworld` | 断开连接 |
| **工作系统** | `trigger_work` | 触发工作类型 |
| | `get_supported_work_types` | 获取支持的工作类型 |
| | `get_work_types` | 获取工作类型列表 |
| | `set_work_priority` | 设置工作优先级 |
| | `get_work_priorities` | 获取工作优先级 |
| **地图环境** | `scan_macro_map` | 扫描地图概况 |
| | `get_game_state` | 游戏状态总览 |
| | `get_time_info` | 获取时间信息 |
| | `get_weather_info` | 获取天气信息 |
| **角色查询** | `get_colonists` | 获取殖民者 |
| | `get_pawn_info` | 角色详情 |
| | `get_all_pawns` | 所有角色 |
| | `get_prisoners` | 获取囚犯 |
| | `get_enemies` | 获取敌人 |
| | `get_animals` | 获取动物 |
| **角色控制** | `move_pawn` | 移动角色 |
| | `stop_pawn` | 停止任务 |
| | `attack_target` | 攻击目标 |
| | `equip_tool` | 装备物品 |
| **资源查询** | `get_resources` | 资源总览 |
| | `get_critical_resources` | 关键资源 |
| | `get_wealth` | 财富概览 |
| | `get_food` | 食物统计 |
| | `get_materials` | 材料统计 |
| | `get_medicine` | 药品统计 |
| | `get_weapons` | 武器统计 |
| | `get_apparel` | 衣物统计 |
| | `get_item_by_def` | 按定义查物品 |
| | `get_thing_info` | 物品详情 |
| **物品操作** | `unlock_things` | 解锁物品 |
| | `get_haulables` | 待搬运物品 |
| **植物系统** | `get_trees` | 树木统计 |
| | `get_crops` | 作物统计 |
| | `get_wild_harvestable` | 野生可收获 |
| | `get_plant_by_def` | 按定义查植物 |
| **建筑查询** | `get_production_buildings` | 生产建筑 |
| | `get_power_buildings` | 电力建筑 |
| | `get_defense_buildings` | 防御建筑 |
| | `get_storage_buildings` | 储存建筑 |
| | `get_furniture` | 家具 |
| | `get_building_by_def` | 按定义查建筑 |
| **建造系统** | `get_buildable_defs` | 可建造定义 |
| | `place_blueprint` | 放置蓝图 |
| | `get_blueprints` | 蓝图列表 |
| | `cancel_blueprint` | 取消蓝图 |
| | `get_plans` | 建造计划 |
| | `get_recommended_build_positions` | 推荐位置 |
| **区域管理** | `get_zones` | 区域列表 |
| | `get_zone_info` | 区域详情 |
| | `create_zone` | 创建区域 |
| | `delete_zone` | 删除区域 |
| | `add_cells_to_zone` | 添加格子 |
| | `remove_cells_from_zone` | 移除格子 |
| | `set_growing_zone_plant` | 设置作物 |
| **储存系统** | `get_storage_settings` | 储存设置 |
| | `set_storage_filter` | 物品过滤 |
| | `set_storage_priority` | 储存优先级 |
| | `apply_storage_preset` | 应用预设 |
| | `get_thing_categories` | 物品类别 |
| | `get_storage_presets` | 储存预设 |
| **其他** | `get_areas` | 活动区域 |
| | `get_room_info` | 房间信息 |

#### 常用工作类型

| workType | 说明 | 使用场景 |
|----------|------|----------|
| `Firefighter` | 消防 | 发生火灾时 |
| `Doctor` | 医疗 | 有人受伤/生病时 |
| `Patient` | 就医 | 殖民者需要治疗时 |
| `Hauling` | 搬运 | 物品散落需要整理时 |
| `Cleaning` | 清洁 | 基地有污垢时 |
| `PlantCutting` | 砍树 | 需要木材时 |
| `Growing` | 种植/收获 | 农作物需要管理时 |
| `Mining` | 挖矿 | 需要矿石时 |
| `Construction` | 建造 | 有蓝图需要建造时 |
| `Repair` | 维修 | 建筑损坏时 |
| `Hunting` | 狩猎 | 需要肉类/皮革时 |
| `Cooking` | 烹饪 | 需要食物时 |
| `Research` | 研究 | 需要科技进度时 |

#### 常用 defName 参考

**物品 defName**:
| 类别 | defName | 中文名 |
|------|---------|--------|
| 材料 | Steel | 钢铁 |
| 材料 | WoodLog | 木材 |
| 材料 | Plasteel | 塑钢 |
| 材料 | ComponentIndustrial | 工业组件 |
| 食物 | RawPotatoes | 生土豆 |
| 食物 | MealSimple | 简单餐 |
| 药品 | MedicineIndustrial | 工业药 |

**建筑 defName**:
| 类别 | defName | 中文名 |
|------|---------|--------|
| 生产 | TableButcher | 屠宰台 |
| 生产 | ElectricStove | 电动炉灶 |
| 电力 | SolarGenerator | 太阳能发电机 |
| 电力 | Battery | 蓄电池 |
| 防御 | Sandbags | 沙袋 |
| 防御 | Turret_MiniTurret | 迷你炮塔 |

**作物 defName**:
| defName | 中文名 | 特点 |
|---------|--------|------|
| Plant_Rice | 水稻 | 生长快，产量中 |
| Plant_Potato | 土豆 | 适应性强 |
| Plant_Corn | 玉米 | 产量高，生长慢 |
| Plant_Cotton | 棉花 | 产布料 |
| Plant_Healroot | 草药 | 产药品 |

详细 API 文档请参考项目根目录的 `TOOLS.md`。

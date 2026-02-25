"""
RimWorld AI Mod 工具集

通过 WebSocket 连接到游戏，执行各种控制和查询操作。

依赖: pip install websocket-client

所有工具直接返回游戏服务器的原始响应，不做任何解析。
"""

import json
import threading
from typing import Dict, List, Optional

# 可选依赖处理
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    websocket = None  # type: ignore
    HAS_WEBSOCKET = False

from .registry import register_tool

# ========== 游戏背景知识 ==========
"""
RimWorld 是一款科幻殖民模拟游戏。

## 核心实体层次
Map (地图)
├── Pawns (角色)
│   ├── Colonists (殖民者) - 玩家控制的人
│   ├── Prisoners (囚犯) - 被俘虏的人
│   ├── Enemies (敌人) - 敌对势力
│   └── Animals (动物) - 野生/驯养动物
├── Things (物品)
│   ├── Items (散落物品) - 食物、材料、武器等
│   ├── Plants (植物) - 树木、作物
│   └── Buildings (建筑) - 已建造的建筑
├── Zones (区域)
│   ├── Stockpile (储存区) - 存放物品
│   └── Growing (种植区) - 种植作物
└── Blueprints (蓝图) - 待建造的建筑计划

## 关键 ID 类型
- pawnId: 角色 ID，用于移动、攻击、装备等
- thingId: 物品 ID，用于解锁、装备等
- zoneId: 区域 ID，用于储存区管理
- blueprintId: 蓝图 ID，用于取消建造
"""


class RimWorldClient:
    """RimWorld WebSocket 客户端"""

    def __init__(self, host: str = "localhost", port: int = 8080):
        self.url = f"ws://{host}:{port}/ai"
        self._ws: Optional[websocket.WebSocket] = None

    def connect(self) -> bool:
        """建立连接"""
        try:
            self._ws = websocket.create_connection(self.url, timeout=5)
            return True
        except Exception as e:
            raise ConnectionError(f"无法连接到 RimWorld: {e}")

    def close(self) -> None:
        """关闭连接"""
        if self._ws:
            self._ws.close()
            self._ws = None

    def send(self, action: str, **params) -> str:
        """发送命令并返回原始响应字符串"""
        if not self._ws:
            self.connect()

        msg = {"action": action, **params}
        self._ws.send(json.dumps(msg))
        response = self._ws.recv()
        return response  # 直接返回原始字符串，不解析


# 全局客户端实例（延迟初始化）
_client: Optional[RimWorldClient] = None
_client_lock = threading.Lock()


def get_client() -> RimWorldClient:
    """获取或创建客户端实例（线程安全）"""
    global _client
    if _client is None:
        with _client_lock:
            # 双重检查锁定
            if _client is None:
                _client = RimWorldClient()
    return _client


# ========== 连接管理 ==========

@register_tool("ping_rimworld", """
测试与 RimWorld 游戏的连接状态。

用途: 在执行其他操作前确认连接是否正常。

参数: 无

返回: JSON 响应，包含连接状态
""")
def ping_rimworld() -> str:
    client = get_client()
    return client.send("ping")


@register_tool("disconnect_rimworld", """
断开与 RimWorld 的 WebSocket 连接。

用途: 在会话结束时清理连接资源。

参数: 无

返回: 断开结果状态
""")
def disconnect_rimworld() -> str:
    global _client
    with _client_lock:
        if _client:
            _client.close()
            _client = None
            return '{"status": "disconnected"}'
    return '{"status": "not_connected"}'


# ========== 工作系统 ==========

@register_tool("trigger_work", """
触发指定类型的工作，系统自动分配空闲殖民者执行。

这是管理殖民地生产的核心命令。RimWorld 中的工作类型决定了殖民者会做什么任务。

参数:
  work_type: 工作类型名称 (字符串)

常用工作类型及使用场景:
┌─────────────────┬──────────────────────────────────────┐
│ workType        │ 使用场景                              │
├─────────────────┼──────────────────────────────────────┤
│ Firefighter     │ 发生火灾时，紧急灭火                   │
│ Doctor          │ 有人受伤/生病时，提供医疗              │
│ Patient         │ 殖民者需要治疗时，去病床休息           │
│ Hauling         │ 物品散落需要整理到储存区               │
│ Cleaning        │ 基地有污垢影响环境时                   │
│ PlantCutting    │ 需要木材，砍伐树木                     │
│ Growing         │ 农作物需要种植或收获                   │
│ Mining          │ 需要矿石资源                          │
│ Construction    │ 有蓝图需要建造                        │
│ Repair          │ 建筑或设备损坏需要维修                 │
│ Hunting         │ 需要肉类/皮革，狩猎动物               │
│ Cooking         │ 需要烹饪食物                          │
│ Research        │ 需要推进科技研究                       │
└─────────────────┴──────────────────────────────────────┘

返回: JSON 响应，包含分配的殖民者信息
示例: {"success": true, "data": {"workType": "PlantCutting", "assignedCount": 2}}
""")
def trigger_work(work_type: str) -> str:
    client = get_client()
    return client.send("trigger_work", workType=work_type)


@register_tool("get_supported_work_types", """
获取游戏支持的所有工作类型列表。

用途: 了解当前殖民地可以分配的所有工作类型。

参数: 无

返回: JSON 响应，包含工作类型名称列表
""")
def get_supported_work_types() -> str:
    client = get_client()
    return client.send("get_supported_work_types")


@register_tool("get_work_types", """
获取当前殖民地的所有工作类型及其状态。

用途: 查看哪些工作类型已启用。

参数: 无

返回: JSON 响应，包含工作类型列表
""")
def get_work_types() -> str:
    client = get_client()
    return client.send("get_work_types")


@register_tool("set_work_priority", """
设置单个殖民者的工作优先级。

RimWorld 使用 1-4 的优先级系统，1 最高，4 最低，0 表示禁用。

参数:
  pawn_id: 殖民者 ID (整数)
  work_type: 工作类型名称 (字符串)
  priority: 优先级 0-4 (整数，0=禁用，1=最高，4=最低)

返回: JSON 响应，确认设置结果
""")
def set_work_priority(pawn_id: int, work_type: str, priority: int) -> str:
    client = get_client()
    return client.send("set_work_priority", pawnId=pawn_id, workType=work_type, priority=priority)


@register_tool("get_work_priorities", """
获取指定殖民者的所有工作优先级设置。

参数:
  pawn_id: 殖民者 ID (整数)

返回: JSON 响应，包含该殖民者各工作类型的优先级
""")
def get_work_priorities(pawn_id: int) -> str:
    client = get_client()
    return client.send("get_work_priorities", pawnId=pawn_id)


# ========== 地图和环境感知 ==========

@register_tool("scan_macro_map", """
扫描地图宏观扇区，获取全局概况。

这是了解地图全貌的核心命令。地图被划分为 9 个扇区（8 方向 + 中心），
每个扇区包含地形、资源、危险等信息。

参数: 无

返回结构:
{
  "mapSize": 250,           // 地图尺寸
  "temperature": 10.4,      // 当前温度
  "summary": {
    "colonistCount": 3,     // 殖民者数量
    "terrain": [...],       // 地形统计
    "resources": [...],     // 资源统计
    "hazards": [...]        // 危险因素
  },
  "sectors": {
    "northwest": {          // 9个扇区: north, northeast, east...
      "terrainType": "Forest",
      "safety": "High",
      "resources": [...]
    }
  }
}

用途:
- 开局时了解地图资源分布
- 规划基地选址
- 发现潜在威胁
""")
def scan_macro_map() -> str:
    client = get_client()
    return client.send("scan_macro_map")


@register_tool("get_game_state", """
获取游戏状态总览。

这是一个快速了解全局状态的便捷命令，整合了多个查询的关键信息。

参数: 无

返回: JSON 响应，包含殖民者数量、资源概况、威胁状态等
""")
def get_game_state() -> str:
    client = get_client()
    return client.send("get_game_state")


@register_tool("get_time_info", """
获取游戏时间和昼夜信息。

RimWorld 时间系统:
- 1 游戏小时 = 2500 ticks
- 一天 = 24 小时
- 昼夜影响太阳能发电和植物生长

参数: 无

返回结构:
{
  "tick": 1234567,      // 游戏刻度
  "hour": 14,           // 当前小时 (0-23)
  "isDaytime": true,    // 是否白天
  "sunGlow": 0.85,      // 日照强度 (0-1)
  "season": "Summer",   // 当前季节
  "daysPassed": 20      // 已过天数
}

用途:
- 规划太阳能发电
- 判断是否适合室外活动
- 了解季节变化对农业的影响
""")
def get_time_info() -> str:
    client = get_client()
    return client.send("get_time_info")


@register_tool("get_weather_info", """
获取当前天气信息。

天气影响: 温度、能见度、殖民者心情、作物生长。

参数: 无

返回结构:
{
  "current": "Clear",           // 天气类型
  "rainRate": 0.0,              // 降雨强度
  "snowRate": 0.0,              // 降雪强度
  "windSpeedFactor": 0.5        // 风速因子
}

用途:
- 判断是否适合室外工作
- 预防火灾风险
- 规划风力发电
""")
def get_weather_info() -> str:
    client = get_client()
    return client.send("get_weather_info")


# ========== 角色管理 ==========

@register_tool("get_colonists", """
获取所有殖民者简要列表（轻量）。

这是快速了解殖民地人口状况的命令。如需完整信息，请使用 get_pawn_info。

参数: 无

返回结构:
{
  "count": 3,
  "colonists": [
    {
      "id": 101,
      "name": "John",
      "position": {"x": 100, "z": 120},
      "healthPercent": 1.0,
      "isDowned": false,
      "curJob": "None"
    }
  ]
}

用途:
- 快速了解殖民者位置和当前任务
- 获取 pawnId 用于移动和控制
""")
def get_colonists() -> str:
    client = get_client()
    return client.send("get_colonists")


@register_tool("get_pawn_info", """
获取殖民者完整信息（推荐）。

这是了解殖民者状态的主要命令。不传参数返回所有殖民者，传 pawnId 返回单个殖民者详情。

参数:
  pawn_id: 角色 ID (整数，可选，不传则返回所有殖民者)

返回结构（不传参数时）:
{
  "count": 2,
  "colonists": [
    {
      "id": 101,
      "name": "John",
      "position": {"x": 100, "z": 120},
      "gender": "Male",
      "biologicalAge": 25,
      "healthPercent": 0.85,
      "isDowned": false,
      "curJob": "Growing",
      "skills": [
        {"defName": "Growing", "label": "种植", "level": 12, "passion": "Major"},
        {"defName": "Construction", "label": "建造", "level": 8, "passion": "Minor"}
      ],
      "traits": [
        {"defName": "Industrious", "label": "勤劳", "degree": 1}
      ],
      "needs": {
        "mood": {"curLevel": 0.75, "curLevelPercentage": 0.75},
        "food": {"curLevel": 0.6, "isStarving": false}
      },
      "hediffs": [],
      "equipment": {"apparelCount": 4}
    }
  ]
}

技能激情 (passion) 说明:
- None: 无激情，经验获取慢
- Minor: 小激情，经验获取正常
- Major: 大激情，经验获取快

用途:
- 全面了解殖民者能力和状态
- 根据技能分配合适工作
- 关注心情和健康状态
""")
def get_pawn_info(pawn_id: int = 0) -> str:
    client = get_client()
    if pawn_id:
        return client.send("get_pawn_info", pawnId=pawn_id)
    else:
        return client.send("get_pawn_info")


@register_tool("get_all_pawns", """
获取地图上所有角色列表（包括殖民者、敌人、动物等）。

参数: 无

返回: JSON 响应，包含所有角色信息
""")
def get_all_pawns() -> str:
    client = get_client()
    return client.send("get_all_pawns")


@register_tool("get_prisoners", """
获取所有囚犯列表。

囚犯可以被招募成为殖民者。

参数: 无

返回: JSON 响应，包含囚犯信息
""")
def get_prisoners() -> str:
    client = get_client()
    return client.send("get_prisoners")


@register_tool("get_enemies", """
获取所有敌对角色列表。

在袭击事件发生时使用，了解敌人数量和位置。

参数: 无

返回: JSON 响应，包含敌人信息
""")
def get_enemies() -> str:
    client = get_client()
    return client.send("get_enemies")


@register_tool("get_animals", """
获取地图上的动物列表。

动物分为野生和驯养两类。

参数: 无

返回: JSON 响应，包含动物信息
""")
def get_animals() -> str:
    client = get_client()
    return client.send("get_animals")


# ========== 角色控制 ==========

@register_tool("move_pawn", """
移动殖民者到指定位置。

殖民者会自动寻路到目标位置。

参数:
  pawn_id: 殖民者 ID (整数)
  x: 目标 X 坐标 (整数)
  z: 目标 Z 坐标 (整数)

返回: JSON 响应，确认移动命令

用途:
- 紧急撤离危险区域
- 集结到防御位置
- 探索新区域
""")
def move_pawn(pawn_id: int, x: int, z: int) -> str:
    client = get_client()
    return client.send("move_pawn", pawnId=pawn_id, x=x, z=z)


@register_tool("stop_pawn", """
停止殖民者当前任务。

参数:
  pawn_id: 殖民者 ID (整数)

返回: JSON 响应，确认停止命令

用途:
- 中断危险活动
- 重新分配任务
""")
def stop_pawn(pawn_id: int) -> str:
    client = get_client()
    return client.send("stop_pawn", pawnId=pawn_id)


@register_tool("attack_target", """
命令殖民者攻击指定目标。

参数:
  pawn_id: 殖民者 ID (整数)
  target_id: 目标 ID (整数，可以是敌人或动物)

返回: JSON 响应，确认攻击命令

用途:
- 战斗时指挥攻击
- 狩猎野生动物
""")
def attack_target(pawn_id: int, target_id: int) -> str:
    client = get_client()
    return client.send("attack_target", pawnId=pawn_id, targetId=target_id)


@register_tool("equip_tool", """
装备武器或工具。

参数:
  pawn_id: 殖民者 ID (整数)
  thing_id: 物品 ID (整数)

返回: JSON 响应，确认装备结果

用途:
- 战斗前装备武器
- 工作前装备合适工具
""")
def equip_tool(pawn_id: int, thing_id: int) -> str:
    client = get_client()
    return client.send("equip_tool", pawnId=pawn_id, thingId=thing_id)


# ========== 资源查询 ==========

@register_tool("get_resources", """
获取殖民地资源总览。

参数:
  summary: 是否返回摘要 (布尔值，可选，默认 true)

返回: JSON 响应，包含各类资源的数量统计

用途:
- 快速了解库存状况
- 规划生产和收集
""")
def get_resources(summary: bool = True) -> str:
    client = get_client()
    return client.send("get_resources", summary=summary)


@register_tool("get_critical_resources", """
获取关键资源状态（食物、药品等生存必需品）。

参数: 无

返回: JSON 响应，包含关键资源数量和警告信息

用途:
- 评估殖民地生存状况
- 发现潜在危机
""")
def get_critical_resources() -> str:
    client = get_client()
    return client.send("get_critical_resources")


@register_tool("get_wealth", """
获取殖民地财富概览。

财富值影响袭击难度和贸易价格。

参数: 无

返回: JSON 响应，包含总财富和分类统计
""")
def get_wealth() -> str:
    client = get_client()
    return client.send("get_wealth")


@register_tool("get_food", """
获取所有食物统计。

参数: 无

返回: JSON 响应，包含各类食物数量和营养值

常用食物 defName:
┌──────────────────┬────────┐
│ defName          │ 中文名  │
├──────────────────┼────────┤
│ RawPotatoes      │ 生土豆  │
│ MealSimple       │ 简单餐  │
│ MealFine         │ 精致餐  │
│ MealLavish       │ 奢华餐  │
│ MeatRaw          │ 生肉    │
└──────────────────┴────────┘
""")
def get_food() -> str:
    client = get_client()
    return client.send("get_food")


@register_tool("get_materials", """
获取所有材料统计。

参数: 无

返回: JSON 响应，包含各类材料数量

常用材料 defName:
┌────────────────────────┬────────┐
│ defName                │ 中文名  │
├────────────────────────┼────────┤
│ Steel                  │ 钢铁    │
│ WoodLog                │ 木材    │
│ Plasteel               │ 塑钢    │
│ ComponentIndustrial    │ 工业组件 │
│ Gold                   │ 黄金    │
│ Silver                 │ 白银    │
└────────────────────────┴────────┘
""")
def get_materials() -> str:
    client = get_client()
    return client.send("get_materials")


@register_tool("get_medicine", """
获取所有药品统计。

参数: 无

返回: JSON 响应，包含各类药品数量

常用药品 defName:
┌────────────────────────┬────────┐
│ defName                │ 中文名  │
├────────────────────────┼────────┤
│ MedicineIndustrial     │ 工业药  │
│ MedicineHerbal         │ 草药    │
│ GlitterworldMedicine   │ 闪耀药  │
└────────────────────────┴────────┘
""")
def get_medicine() -> str:
    client = get_client()
    return client.send("get_medicine")


@register_tool("get_weapons", """
获取所有武器统计。

参数: 无

返回: JSON 响应，包含各类武器数量和详情
""")
def get_weapons() -> str:
    client = get_client()
    return client.send("get_weapons")


@register_tool("get_apparel", """
获取所有衣物统计。

参数: 无

返回: JSON 响应，包含各类衣物数量
""")
def get_apparel() -> str:
    client = get_client()
    return client.send("get_apparel")


@register_tool("get_item_by_def", """
按定义名查询特定物品。

参数:
  def_name: 物品定义名 (字符串，如 Steel, WoodLog, RawPotatoes)

返回: JSON 响应，包含该类型所有物品的详细信息
""")
def get_item_by_def(def_name: str) -> str:
    client = get_client()
    return client.send("get_item_by_def", defName=def_name)


@register_tool("get_thing_info", """
获取单个物品的详细信息。

参数:
  thing_id: 物品 ID (整数)

返回: JSON 响应，包含物品详细信息
""")
def get_thing_info(thing_id: int) -> str:
    client = get_client()
    return client.send("get_thing_info", thingId=thing_id)


# ========== 物品操作 ==========

@register_tool("unlock_things", """
解锁被禁止的物品。

被禁止的物品（红色标记）无法被殖民者使用。新落下的物品默认被禁止。

参数:
  thing_id: 指定物品 ID (整数，可选)
  all: 是否解锁所有被禁止物品 (布尔值，可选)

注意: thing_id 和 all 参数二选一

返回: JSON 响应，确认解锁结果

用途:
- 让殖民者能使用新获得的物品
- 快速解锁所有散落物品
""")
def unlock_things(thing_id: int = 0, all: bool = False) -> str:
    client = get_client()
    if all:
        return client.send("unlock_things", all=True)
    else:
        return client.send("unlock_things", thingId=thing_id)


@register_tool("get_haulables", """
获取需要搬运的物品列表。

这些物品不在储存区内，需要殖民者搬运。

参数: 无

返回: JSON 响应，包含待搬运物品列表
""")
def get_haulables() -> str:
    client = get_client()
    return client.send("get_haulables")


# ========== 植物系统 ==========

@register_tool("get_trees", """
获取所有树木统计。

参数: 无

返回: JSON 响应，包含各类树木数量和位置
""")
def get_trees() -> str:
    client = get_client()
    return client.send("get_trees")


@register_tool("get_crops", """
获取所有农作物统计。

参数: 无

返回: JSON 响应，包含作物类型、生长进度、成熟状态

用途:
- 检查哪些作物可以收获
- 了解种植区状况
""")
def get_crops() -> str:
    client = get_client()
    return client.send("get_crops")


@register_tool("get_wild_harvestable", """
获取野生可收获植物列表。

某些野生植物可以直接收获（如浆果、草药）。

参数: 无

返回: JSON 响应，包含可收获植物信息
""")
def get_wild_harvestable() -> str:
    client = get_client()
    return client.send("get_wild_harvestable")


@register_tool("get_plant_by_def", """
按定义名查询特定植物。

参数:
  def_name: 植物定义名 (字符串)

返回: JSON 响应，包含该类型植物信息
""")
def get_plant_by_def(def_name: str) -> str:
    client = get_client()
    return client.send("get_plant_by_def", defName=def_name)


# ========== 建筑查询 ==========

@register_tool("get_production_buildings", """
获取所有生产建筑统计。

参数: 无

返回: JSON 响应，包含工作台、炉灶等生产建筑信息
""")
def get_production_buildings() -> str:
    client = get_client()
    return client.send("get_production_buildings")


@register_tool("get_power_buildings", """
获取所有电力建筑统计。

参数: 无

返回: JSON 响应，包含发电机、电池等电力建筑信息
""")
def get_power_buildings() -> str:
    client = get_client()
    return client.send("get_power_buildings")


@register_tool("get_defense_buildings", """
获取所有防御建筑统计。

参数: 无

返回: JSON 响应，包含沙袋、炮塔等防御建筑信息
""")
def get_defense_buildings() -> str:
    client = get_client()
    return client.send("get_defense_buildings")


@register_tool("get_storage_buildings", """
获取所有储存建筑统计。

参数: 无

返回: JSON 响应，包含货架、储存区等信息
""")
def get_storage_buildings() -> str:
    client = get_client()
    return client.send("get_storage_buildings")


@register_tool("get_furniture", """
获取所有家具统计。

参数: 无

返回: JSON 响应，包含床、桌子、椅子等家具信息
""")
def get_furniture() -> str:
    client = get_client()
    return client.send("get_furniture")


@register_tool("get_building_by_def", """
按定义名查询特定建筑。

参数:
  def_name: 建筑定义名 (字符串)

返回: JSON 响应，包含该类型建筑信息
""")
def get_building_by_def(def_name: str) -> str:
    client = get_client()
    return client.send("get_building_by_def", defName=def_name)


# ========== 建造系统 ==========

@register_tool("get_buildable_defs", """
获取可建造的建筑定义列表。

参数:
  category: 建筑类别 (字符串，可选)

常用类别:
┌────────────┬────────────┐
│ category   │ 说明        │
├────────────┼────────────┤
│ furniture  │ 家具        │
│ production │ 生产建筑    │
│ power      │ 电力建筑    │
│ defense    │ 防御建筑    │
│ temperature│ 温控建筑    │
└────────────┴────────────┘

返回: JSON 响应，包含可建造建筑列表

常用建筑 defName:
┌───────────────────┬────────────┐
│ defName           │ 中文名      │
├───────────────────┼────────────┤
│ TableButcher      │ 屠宰台      │
│ ElectricStove     │ 电动炉灶    │
│ TableStonecutter  │ 切石台      │
│ SolarGenerator    │ 太阳能发电机 │
│ Battery           │ 蓄电池      │
│ PowerConduit      │ 电缆       │
│ Sandbags          │ 沙袋       │
│ Turret_MiniTurret │ 迷你炮塔    │
│ Bed               │ 床         │
│ Table2x2c         │ 桌子       │
└───────────────────┴────────────┘
""")
def get_buildable_defs(category: str = "") -> str:
    client = get_client()
    if category:
        return client.send("get_buildable_defs", category=category)
    return client.send("get_buildable_defs")


@register_tool("place_blueprint", """
放置建造蓝图。

蓝本是建筑的建造计划，殖民者会根据蓝图收集材料并建造。

参数:
  def_name: 建筑定义名 (字符串，如 Wall, SolarGenerator, Battery)
  x: X 坐标 (整数)
  z: Z 坐标 (整数)
  stuff_def_name: 材料定义名 (可选字符串，如 WoodLog, Steel)
  rotation: 旋转方向 (可选字符串，north/south/east/west)

返回: JSON 响应，包含蓝图 ID

示例:
放置太阳能发电机: {"def_name": "SolarGenerator", "x": 100, "z": 100}
放置木墙: {"def_name": "Wall", "x": 100, "z": 100, "stuff_def_name": "WoodLog"}
""")
def place_blueprint(
    def_name: str, x: int, z: int, stuff_def_name: str = "", rotation: str = "north"
) -> str:
    client = get_client()
    params = {"defName": def_name, "x": x, "z": z, "rotation": rotation}
    if stuff_def_name:
        params["stuffDefName"] = stuff_def_name
    return client.send("place_blueprint", **params)


@register_tool("get_blueprints", """
获取所有蓝图列表。

参数: 无

返回: JSON 响应，包含待建造的蓝图信息
""")
def get_blueprints() -> str:
    client = get_client()
    return client.send("get_blueprints")


@register_tool("cancel_blueprint", """
取消指定蓝图。

参数:
  blueprint_id: 蓝图 ID (整数)

返回: JSON 响应，确认取消结果
""")
def cancel_blueprint(blueprint_id: int) -> str:
    client = get_client()
    return client.send("cancel_blueprint", blueprintId=blueprint_id)


@register_tool("get_plans", """
获取所有建造计划。

参数: 无

返回: JSON 响应，包含建造计划信息
""")
def get_plans() -> str:
    client = get_client()
    return client.send("get_plans")


@register_tool("get_recommended_build_positions", """
获取推荐的建筑位置。

系统会分析地图，推荐适合放置指定建筑的位置。

参数:
  def_name: 建筑定义名 (字符串)
  count: 返回位置数量 (可选整数，默认5，最大20)

返回: JSON 响应，包含推荐坐标列表
""")
def get_recommended_build_positions(def_name: str, count: int = 5) -> str:
    client = get_client()
    return client.send("get_recommended_build_positions", defName=def_name, count=count)


# ========== 区域管理 ==========

@register_tool("get_zones", """
获取所有区域列表。

参数:
  detailed: 是否返回详细信息 (布尔值，可选)

返回: JSON 响应，包含区域类型、位置、格子数等信息
""")
def get_zones(detailed: bool = False) -> str:
    client = get_client()
    return client.send("get_zones", detailed=detailed)


@register_tool("get_zone_info", """
获取单个区域的详细信息。

参数:
  zone_id: 区域 ID (整数)

返回: JSON 响应，包含区域详细信息
""")
def get_zone_info(zone_id: int) -> str:
    client = get_client()
    return client.send("get_zone_info", zoneId=zone_id)


@register_tool("create_zone", """
创建新区域。

参数:
  type: 区域类型 (字符串)
  cells: 格子坐标列表 (列表，格式: [{"x": 100, "z": 100}, ...])

区域类型:
┌────────────┬────────────────┐
│ type       │ 用途            │
├────────────┼────────────────┤
│ stockpile  │ 储存区 - 存放物品 │
│ growing    │ 种植区 - 种植作物 │
└────────────┴────────────────┘

返回: JSON 响应，包含新区域 ID

示例:
创建种植区: {"type": "growing", "cells": [{"x": 100, "z": 100}, {"x": 101, "z": 100}]}
""")
def create_zone(type: str, cells: List[Dict[str, int]]) -> str:
    client = get_client()
    return client.send("create_zone", type=type, cells=cells)


@register_tool("delete_zone", """
删除指定区域。

参数:
  zone_id: 区域 ID (整数)

返回: JSON 响应，确认删除结果
""")
def delete_zone(zone_id: int) -> str:
    client = get_client()
    return client.send("delete_zone", zoneId=zone_id)


@register_tool("add_cells_to_zone", """
向区域添加格子。

参数:
  zone_id: 区域 ID (整数)
  cells: 要添加的格子坐标列表 (列表)

返回: JSON 响应，确认添加结果
""")
def add_cells_to_zone(zone_id: int, cells: List[Dict[str, int]]) -> str:
    client = get_client()
    return client.send("add_cells_to_zone", zoneId=zone_id, cells=cells)


@register_tool("remove_cells_from_zone", """
从区域移除格子。

参数:
  zone_id: 区域 ID (整数)
  cells: 要移除的格子坐标列表 (列表)

返回: JSON 响应，确认移除结果
""")
def remove_cells_from_zone(zone_id: int, cells: List[Dict[str, int]]) -> str:
    client = get_client()
    return client.send("remove_cells_from_zone", zoneId=zone_id, cells=cells)


@register_tool("set_growing_zone_plant", """
设置种植区要种植的作物。

参数:
  zone_id: 种植区 ID (整数)
  plant_def_name: 作物定义名 (字符串)

常用作物 defName:
┌──────────────────┬────────┬──────────────────┐
│ defName          │ 中文名  │ 特点              │
├──────────────────┼────────┼──────────────────┤
│ Plant_Rice       │ 水稻    │ 生长快，产量中     │
│ Plant_Potato     │ 土豆    │ 适应性强          │
│ Plant_Corn       │ 玉米    │ 产量高，生长慢     │
│ Plant_Strawberry │ 草莓    │ 可生食           │
│ Plant_Cotton     │ 棉花    │ 产布料           │
│ Plant_Healroot   │ 草药    │ 产药品           │
│ Plant_Haygrass   │ 干草    │ 动物饲料         │
└──────────────────┴────────┴──────────────────┘

返回: JSON 响应，确认设置结果
""")
def set_growing_zone_plant(zone_id: int, plant_def_name: str) -> str:
    client = get_client()
    return client.send("set_growing_zone_plant", zoneId=zone_id, plantDefName=plant_def_name)


# ========== 储存系统 ==========

@register_tool("get_storage_settings", """
获取储存区的设置。

参数:
  zone_id: 储存区 ID (整数)

返回: JSON 响应，包含物品过滤设置
""")
def get_storage_settings(zone_id: int) -> str:
    client = get_client()
    return client.send("get_storage_settings", zoneId=zone_id)


@register_tool("set_storage_filter", """
设置储存区的物品过滤。

参数:
  zone_id: 储存区 ID (整数)
  mode: 过滤模式 (字符串，可选，allowAll/disallowAll)
  categories: 物品类别列表 (列表，可选)
  defs: 物品定义名列表 (列表，可选)
  allow: 是否允许 (布尔值，与 categories/defs 配合使用)

模式说明:
- allowAll: 允许所有物品
- disallowAll: 禁止所有物品
- 配合 categories/defs: 精细控制特定物品

示例:
允许所有: {"zone_id": 15, "mode": "allowAll"}
允许食物和药品: {"zone_id": 15, "categories": ["Foods", "Medicine"], "allow": true}
允许钢铁和木材: {"zone_id": 15, "defs": ["Steel", "WoodLog"], "allow": true}
""")
def set_storage_filter(
    zone_id: int,
    mode: str = "",
    categories: List[str] = None,
    defs: List[str] = None,
    allow: bool = True
) -> str:
    client = get_client()
    params = {"zoneId": zone_id}
    if mode:
        params["mode"] = mode
    if categories:
        params["categories"] = categories
    if defs:
        params["defs"] = defs
    if categories or defs:
        params["allow"] = allow
    return client.send("set_storage_filter", **params)


@register_tool("set_storage_priority", """
设置储存区的优先级。

殖民者会优先将物品放入高优先级的储存区。

参数:
  zone_id: 储存区 ID (整数)
  priority: 优先级 (字符串)

优先级选项:
┌───────────┬────────┬────────────────────┐
│ 优先级    │ 说明    │ 使用场景            │
├───────────┼────────┼────────────────────┤
│ Critical  │ 关键    │ 必须优先填充        │
│ Important │ 重要    │ 重要物资            │
│ Preferred │ 优先    │ 一般优先            │
│ Normal    │ 普通    │ 默认               │
│ Low       │ 低      │ 临时/边缘          │
│ Unstored  │ 不储存  │ 禁止存放           │
└───────────┴────────┴────────────────────┘

返回: JSON 响应，确认设置结果
""")
def set_storage_priority(zone_id: int, priority: str) -> str:
    client = get_client()
    return client.send("set_storage_priority", zoneId=zone_id, priority=priority)


@register_tool("apply_storage_preset", """
应用储存预设配置。

预设是快速配置储存区的方法，一键设置物品过滤。

参数:
  zone_id: 储存区 ID (整数)
  preset_name: 预设名称 (字符串)

储存预设:
┌────────────┬────────────────┐
│ presetName │ 用途            │
├────────────┼────────────────┤
│ all        │ 允许所有物品    │
│ food       │ 只允许食物      │
│ materials  │ 只允许原材料    │
│ weapons    │ 只允许武器      │
│ apparel    │ 只允许衣物      │
│ medicine   │ 只允许药品      │
│ corpses    │ 只允许尸体      │
│ chunks     │ 只允许碎石块    │
└────────────┴────────────────┘

返回: JSON 响应，确认应用结果
""")
def apply_storage_preset(zone_id: int, preset_name: str) -> str:
    client = get_client()
    return client.send("apply_storage_preset", zoneId=zone_id, presetName=preset_name)


@register_tool("get_thing_categories", """
获取物品类别树。

参数:
  parent_category: 父类别 (字符串，可选，用于获取子类别)

返回: JSON 响应，包含物品类别层次结构
""")
def get_thing_categories(parent_category: str = "") -> str:
    client = get_client()
    if parent_category:
        return client.send("get_thing_categories", parentCategory=parent_category)
    return client.send("get_thing_categories")


@register_tool("get_storage_presets", """
获取所有储存预设列表。

参数: 无

返回: JSON 响应，包含可用预设名称和说明
""")
def get_storage_presets() -> str:
    client = get_client()
    return client.send("get_storage_presets")


# ========== 其他查询 ==========

@register_tool("get_areas", """
获取所有活动区域。

活动区域用于限制殖民者或动物的活动范围。

参数: 无

返回: JSON 响应，包含活动区域信息
""")
def get_areas() -> str:
    client = get_client()
    return client.send("get_areas")


@register_tool("get_room_info", """
获取指定位置的房间信息。

参数:
  x: X 坐标 (整数)
  z: Z 坐标 (整数)

返回: JSON 响应，包含房间类型、温度、美观度等信息
""")
def get_room_info(x: int, z: int) -> str:
    client = get_client()
    return client.send("get_room_info", x=x, z=z)

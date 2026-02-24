"""
Agent Registry

提供 Agent 类型的中央注册和管理机制。
支持 REACT、PLAN 等类型的 Agent。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from langchain_core.language_models import BaseChatModel
from langgraph.graph import CompiledGraph


class AgentType(Enum):
    """支持的 Agent 类型"""
    REACT = "react"        # ReAct 模式 Agent
    PLAN = "plan"          # Plan-Execute 模式 Agent
    CUSTOM = "custom"      # 自定义子图


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    agent_type: AgentType
    llm: Optional[BaseChatModel] = None
    tools: List[Any] = field(default_factory=list)
    system_prompt: str = ""
    # ReAct 特定配置
    max_react_steps: int = 5
    # Plan 特定配置
    max_plan_steps: int = 10
    reflect_on_failure: bool = True
    # 自定义配置
    custom_factory: Optional[Callable] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """
    Agent 类型注册中心。

    用法:
        registry = AgentRegistry()

        # 创建 Agent
        node = registry.create_agent(AgentConfig(
            name="my_researcher",
            agent_type=AgentType.REACT,
            llm=my_llm,
            tools=[search_tool]
        ))
    """

    _factories: Dict[AgentType, Callable] = {}

    @classmethod
    def register_factory(cls, agent_type: AgentType, factory: Callable) -> None:
        """
        注册 Agent 类型的工厂函数。

        Args:
            agent_type: Agent 类型
            factory: 工厂函数，接收 AgentConfig 返回节点
        """
        cls._factories[agent_type] = factory

    @classmethod
    def create_agent(cls, config: AgentConfig) -> Union[Callable, CompiledGraph]:
        """
        根据配置创建 Agent 节点。

        Args:
            config: Agent 配置

        Returns:
            可调用节点函数或编译后的子图

        Raises:
            ValueError: 如果没有注册对应类型的工厂
        """
        factory = cls._factories.get(config.agent_type)
        if not factory:
            raise ValueError(f"No factory registered for agent type: {config.agent_type}")
        return factory(config)

    @classmethod
    def list_available_types(cls) -> List[AgentType]:
        """列出所有已注册的 Agent 类型"""
        return list(cls._factories.keys())

    @classmethod
    def is_registered(cls, agent_type: AgentType) -> bool:
        """检查 Agent 类型是否已注册"""
        return agent_type in cls._factories


def create_agent_node(
    name: str,
    agent_type: Union[AgentType, str],
    llm: BaseChatModel,
    **kwargs
) -> Union[Callable, CompiledGraph]:
    """
    便捷函数：创建 Agent 节点。

    Args:
        name: Agent 名称
        agent_type: Agent 类型（REACT, PLAN 或字符串）
        llm: 语言模型
        **kwargs: 其他配置参数

    Returns:
        可调用节点函数或编译后的子图

    Example:
        node = create_agent_node(
            name="researcher",
            agent_type="react",
            llm=ChatAnthropic(),
            tools=[search_tool],
            max_react_steps=5
        )
    """
    # 处理字符串类型的 agent_type
    if isinstance(agent_type, str):
        agent_type = AgentType(agent_type.lower())

    config = AgentConfig(
        name=name,
        agent_type=agent_type,
        llm=llm,
        **kwargs
    )
    return AgentRegistry.create_agent(config)


# ========== 默认工厂函数 ==========

def _create_react_agent(config: AgentConfig) -> CompiledGraph:
    """创建 ReAct Agent"""
    from .react import create_react_node

    return create_react_node(
        llm=config.llm,
        tools=config.tools,
        name=config.name,
        system_prompt=config.system_prompt,
        max_steps=config.max_react_steps,
    )


def _create_plan_agent(config: AgentConfig) -> CompiledGraph:
    """创建 Plan Agent"""
    from .plan import create_plan_node

    return create_plan_node(
        llm=config.llm,
        tools=config.tools,
        name=config.name,
        system_prompt=config.system_prompt,
        max_steps=config.max_plan_steps,
        reflect_on_failure=config.reflect_on_failure,
    )


def _create_custom_agent(config: AgentConfig) -> Union[Callable, CompiledGraph]:
    """创建自定义 Agent"""
    if config.custom_factory:
        return config.custom_factory(config)
    raise ValueError("Custom agent requires custom_factory to be provided")


# 注册默认工厂
AgentRegistry.register_factory(AgentType.REACT, _create_react_agent)
AgentRegistry.register_factory(AgentType.PLAN, _create_plan_agent)
AgentRegistry.register_factory(AgentType.CUSTOM, _create_custom_agent)

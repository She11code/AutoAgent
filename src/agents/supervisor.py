"""
Supervisor Agent

负责：
- 任务分解
- 路由决策
- 结果整合

独立类，不继承 BaseAgent。
"""

from typing import Any, Dict, Optional, Set

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..core.state import MultiAgentState
from .prompts import load_prompt
from .utils import build_system_prompt


class AgentDecision(BaseModel):
    """Supervisor的决策输出"""
    next_agent: str = Field(
        description="下一个要调用的Agent名称，或FINISH表示任务完成"
    )
    task_description: str = Field(
        description="分配给下一个Agent的任务描述"
    )
    reasoning: str = Field(
        description="决策理由"
    )




class SupervisorAgent:
    """
    Supervisor Agent

    独立类，负责任务分解和路由决策。
    """

    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str = "",
        max_iterations: int = 10,
        valid_agents: Optional[Set[str]] = None,
    ):
        """
        初始化Supervisor

        Args:
            llm: 语言模型实例
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            valid_agents: 有效的 Agent 名称集合
        """
        self.name = "supervisor"
        self.llm = llm
        self.system_prompt = system_prompt  # 如果为空，在 _build_system_prompt 中加载默认提示词
        self.max_iterations = max_iterations
        self.valid_agents = valid_agents or set()

    def _check_iteration_limit(self, state: MultiAgentState) -> bool:
        """检查是否达到迭代限制"""
        results = state.get("task_context", {}).get("agent_results", [])
        return len(results) < self.max_iterations

    def _build_context_message(self, state: MultiAgentState) -> str:
        """构建上下文消息"""
        context_parts = []

        # 用户原始请求
        messages = state.get("messages", [])
        user_messages = [m for m in messages if hasattr(m, 'type') and m.type == "human"]
        if user_messages:
            context_parts.append(f"## 用户请求\n{user_messages[-1].content}")

        # 已完成的任务
        results = state.get("task_context", {}).get("agent_results", [])
        if results:
            context_parts.append("## 已完成的任务")
            for r in results:
                result_preview = r.get('result', '')[:200]
                context_parts.append(f"- {r.get('agent')}: {result_preview}...")

        # 当前任务状态
        task_status = state.get("task_context", {}).get("task_status", "planning")
        context_parts.append(f"\n## 当前状态\n任务状态: {task_status}")

        return "\n".join(context_parts)

    def _build_system_prompt(self, state: MultiAgentState) -> str:
        """构建系统提示词"""
        # 格式化可用 Agent 列表
        agents_text = ""
        if self.valid_agents:
            agents_text = "\n".join([f"- **{agent}**" for agent in self.valid_agents])
        else:
            agents_text = "- （未指定可用Agent）"

        # 使用自定义提示词或从文件加载默认提示词
        base_prompt = self.system_prompt or load_prompt("supervisor")
        base_prompt = base_prompt.format(available_agents=agents_text)

        # 注入领域知识
        return build_system_prompt(state, base_prompt, include_knowledge=True)

    async def process(self, state: MultiAgentState) -> Dict[str, Any]:
        """
        处理状态并做出路由决策

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        # 检查迭代限制
        if not self._check_iteration_limit(state):
            return {
                "task_context": {
                    "active_agent": "FINISH",
                    "task_status": "completed",
                }
            }

        # 构建系统提示词
        system_prompt = self._build_system_prompt(state)

        # 构建上下文消息
        context_message = self._build_context_message(state)

        # 调用LLM做决策
        structured_llm = self.llm.with_structured_output(AgentDecision)

        decision = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=context_message)
        ])

        # 验证决策的 Agent 是否有效
        next_agent = decision.next_agent
        if self.valid_agents and next_agent not in self.valid_agents and next_agent != "FINISH":
            next_agent = "FINISH"

        # 构建返回结果
        result = {
            "task_context": {
                "active_agent": next_agent,
                "task_status": "executing" if next_agent != "FINISH" else "completed",
            }
        }

        # 如果不是结束，添加任务分配记录
        if next_agent != "FINISH":
            result["task_context"]["task_assignments"] = [{
                "agent": next_agent,
                "task": decision.task_description,
                "reasoning": decision.reasoning,
            }]

        return result

    async def __call__(self, state: MultiAgentState) -> Dict[str, Any]:
        """使 Agent 可调用"""
        try:
            return await self.process(state)
        except Exception as e:
            return {
                "task_context": {
                    "last_error": f"Supervisor执行失败: {str(e)}",
                }
            }


def create_supervisor_node(
    llm: BaseChatModel,
    valid_agents: Optional[Set[str]] = None,
    **kwargs
) -> SupervisorAgent:
    """
    创建 Supervisor 节点

    Args:
        llm: 语言模型实例
        valid_agents: 有效的 Agent 名称集合
        **kwargs: 其他参数

    Returns:
        SupervisorAgent 实例
    """
    return SupervisorAgent(llm=llm, valid_agents=valid_agents, **kwargs)

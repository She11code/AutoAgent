"""
Supervisor Agent

负责：
- 任务分解
- 路由决策
- 结果整合
- 轮次管理

独立类，不继承 BaseAgent。
"""

import time
from typing import Any, Dict, Optional, Set

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..core.state import MultiAgentState
from ..utils import supervisor_logger
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

    def _should_continue(self, state: MultiAgentState) -> bool:
        """
        判断是否需要继续分配任务

        通过检查消息历史、轮次状态和计划完成情况来决定。
        """
        task_context = state.get("task_context", {})
        messages = state.get("messages", [])

        # 1. 获取最后的 AI 和 Human 消息索引
        last_ai_idx = -1
        last_human_idx = -1
        for i, msg in enumerate(messages):
            msg_type = getattr(msg, 'type', '')
            if msg_type == 'ai':
                last_ai_idx = i
            elif msg_type == 'human':
                last_human_idx = i

        # 2. 如果没有用户消息，无需继续
        if last_human_idx == -1:
            return False

        # 3. 优先检查计划步骤是否全部完成
        # 如果有未完成的计划步骤，必须继续执行（即使 AI 已回复）
        plan_steps = task_context.get("plan_steps", [])
        if plan_steps:
            pending_steps = [s for s in plan_steps if s.get("status") != "completed"]
            if pending_steps:
                # 还有未完成的计划步骤，需要继续执行
                return True

        # 4. 如果 AI 已回复用户最新消息，无需继续
        if last_ai_idx > last_human_idx:
            return False

        # 5. 检查当前轮次是否已有结果
        current_turn = task_context.get("turn_id", "")
        results = task_context.get("agent_results", [])
        current_turn_results = [r for r in results if r.get("turn_id") == current_turn]

        if current_turn_results:
            return False

        return True

    def _build_context_message(self, state: MultiAgentState) -> str:
        """构建上下文消息 - 支持多轮对话"""
        context_parts = []

        # 完整对话历史（最近 10 轮）
        messages = state.get("messages", [])
        recent_messages = messages[-10:]

        if recent_messages:
            context_parts.append("## 对话历史")
            for msg in recent_messages:
                msg_type = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                if len(content) > 200:
                    content = content[:200] + "..."

                if msg_type == "human":
                    context_parts.append(f"用户: {content}")
                elif msg_type == "ai":
                    agent_name = getattr(msg, 'name', 'assistant')
                    context_parts.append(f"{agent_name}: {content}")

        # 当前任务状态
        task_context = state.get("task_context", {})
        current_task = task_context.get("current_task", "")
        if current_task:
            context_parts.append("\n## 当前任务")
            context_parts.append(f"  任务: {current_task}")

        # 已完成的任务 - 只显示最近 3 条
        results = task_context.get("agent_results", [])
        if results:
            context_parts.append("\n## 最近完成的任务")
            for r in results[-3:]:
                result_preview = r.get('result', '')[:150]
                turn_id = r.get('turn_id', 'unknown')
                context_parts.append(f"- [{turn_id}] {r.get('agent')}: {result_preview}...")

        # 计划步骤信息
        plan_steps = task_context.get("plan_steps", [])
        if plan_steps:
            context_parts.append("\n## 计划步骤")
            for i, step in enumerate(plan_steps):
                status = "[x]" if step.get("status") == "completed" else "[ ]"
                context_parts.append(f"  {status} 步骤 {i + 1}: {step.get('description', 'N/A')}")
            # 统计完成情况
            completed = sum(1 for s in plan_steps if s.get("status") == "completed")
            context_parts.append(f"\n  进度: {completed}/{len(plan_steps)} 完成")

        # 当前状态
        task_status = task_context.get("task_status", "planning")
        plan_status = task_context.get("plan_status", "none")
        context_parts.append("\n## 当前状态")
        context_parts.append(f"  任务状态: {task_status}")
        context_parts.append(f"  计划状态: {plan_status}")

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
        # 检查是否需要继续（基于消息状态）
        if not self._should_continue(state):
            return {
                "task_context": {
                    "active_agent": "FINISH",
                    "task_status": "completed",
                }
            }

        # 检查迭代限制
        if not self._check_iteration_limit(state):
            return {
                "task_context": {
                    "active_agent": "FINISH",
                    "task_status": "completed",
                }
            }

        # 生成轮次 ID
        turn_id = f"turn_{int(time.time() * 1000)}"

        # 构建系统提示词
        system_prompt = self._build_system_prompt(state)

        # 构建上下文消息
        context_message = self._build_context_message(state)

        # 调试输出
        supervisor_logger.debug("Supervisor 上下文:")
        supervisor_logger.debug("-" * 40)
        supervisor_logger.debug(context_message)

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
        result: Dict[str, Any] = {
            "task_context": {
                "active_agent": next_agent,
                "task_status": "executing" if next_agent != "FINISH" else "completed",
                # 轮次信息
                "turn_id": turn_id,
                "current_task": decision.task_description if next_agent != "FINISH" else "",
                "assigned_agent": next_agent if next_agent != "FINISH" else "",
            }
        }

        # 如果不是结束，添加任务分配记录（带轮次标记）
        if next_agent != "FINISH":
            result["task_context"]["task_assignments"] = [{
                "turn_id": turn_id,
                "agent": next_agent,
                "task": decision.task_description,
                "reasoning": decision.reasoning,
                "timestamp": time.time(),
            }]
        else:
            # 当直接返回 FINISH 时，需要生成一条最终回复消息
            # 否则 messages 里只有用户的 HumanMessage，API 会返回用户自己的消息
            result["messages"] = [AIMessage(
                content=decision.task_description or decision.reasoning,
                name=self.name,
            )]

        return result

    async def __call__(self, state: MultiAgentState) -> Dict[str, Any]:
        """使 Agent 可调用"""
        try:
            print("[SUPERVISOR] 开始处理...")
            result = await self.process(state)
            tc = result.get('task_context', {})
            print(f"[SUPERVISOR] 处理完成: active_agent={tc.get('active_agent')}")
            return result
        except Exception as e:
            print(f"[SUPERVISOR] 执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "task_context": {
                    "last_error": f"Supervisor执行失败: {str(e)}",
                    "active_agent": "FINISH",
                },
                "messages": [AIMessage(content=f"Supervisor 执行失败: {str(e)}", name=self.name)],
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

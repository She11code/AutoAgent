"""
基础使用示例

展示如何创建和使用多Agent系统（使用 ReAct 和 Plan Agent）。
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# 添加项目根目录到路径
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.state import create_initial_state
from src.core.graph import create_app_with_agents
from src.agents import create_supervisor_node, create_react_node, create_plan_node
from src.knowledge.manager import KnowledgeManager


async def main():
    # 加载环境变量（从项目根目录）
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    # 1. 初始化LLM (Anthropic Claude 兼容 API)
    llm = ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", "glm-5"),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0,
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"),
    )

    # 2. 加载领域知识
    knowledge_mgr = KnowledgeManager()
    knowledge_mgr.load_knowledge(
        "python",
        """
Python是一种高级编程语言，以其简洁的语法和强大的功能著称。
主要特点：
- 动态类型
- 自动内存管理
- 丰富的标准库
- 广泛的第三方生态系统
        """.strip()
    )

    # 3. 创建 Agent 节点
    # 使用 ReAct Agent 进行研究和编码
    researcher_node = create_react_node(
        llm=llm,
        tools=[],  # 可以添加搜索工具等
        name="researcher",
        max_steps=3,
    )
    coder_node = create_react_node(
        llm=llm,
        tools=[],  # 可以添加代码执行工具等
        name="coder",
        max_steps=3,
    )

    # 使用 Plan Agent 进行分析和规划
    analyst_node = create_plan_node(
        llm=llm,
        tools=[],
        name="analyst",
        max_steps=5,
    )
    writer_node = create_react_node(
        llm=llm,
        tools=[],
        name="writer",
        max_steps=3,
    )

    # 4. 创建 Supervisor（指定可用的 Agent）
    supervisor_node = create_supervisor_node(
        llm=llm,
        valid_agents={"researcher", "coder", "analyst", "writer"},
    )

    # 5. 创建应用
    app = create_app_with_agents(
        supervisor_node=supervisor_node,
        agent_nodes={
            "researcher": researcher_node,
            "coder": coder_node,
            "analyst": analyst_node,
            "writer": writer_node,
        },
        use_persistence=True,
    )

    # 6. 创建初始状态
    initial_state = create_initial_state(
        session_id="demo-session-001",
        user_id="demo-user",
        domain_knowledge=knowledge_mgr.get_knowledge("python"),
    )

    # 添加用户消息
    from langchain_core.messages import HumanMessage
    initial_state["messages"] = [
        HumanMessage(content="请帮我写一个Python函数来计算斐波那契数列")
    ]

    # 7. 运行
    print("=" * 50)
    print("开始执行多Agent任务...")
    print("=" * 50)

    config = {"configurable": {"thread_id": "demo-session-001"}}

    result = await app.ainvoke(initial_state, config)

    print("\n" + "=" * 50)
    print("执行完成!")
    print("=" * 50)

    # 打印最终消息
    messages = result.get("messages", [])
    if messages:
        print("\n最终回复:")
        print("-" * 40)
        last_message = messages[-1]
        print(last_message.content)

    # 打印任务执行摘要
    task_context = result.get("task_context", {})
    agent_results = task_context.get("agent_results", [])
    if agent_results:
        print("\n执行摘要:")
        print("-" * 40)
        for r in agent_results:
            print(f"  - {r.get('agent')}: {r.get('status')}")


if __name__ == "__main__":
    asyncio.run(main())

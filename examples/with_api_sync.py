"""
带API同步的使用示例

展示如何使用远程API状态同步功能（使用 ReAct Agent）。
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

import sys
sys.path.insert(0, "..")

from src.core.state import create_initial_state
from src.core.graph import create_app_with_agents
from src.agents import create_supervisor_node, create_react_node
from src.sync.api_client import RemoteAPIClient
from src.sync.sync_layer import SyncLayer, create_sync_wrapper


async def main():
    # 加载环境变量
    load_dotenv()

    # 1. 初始化LLM (Anthropic Claude)
    llm = ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0,
    )

    # 2. 创建API客户端（模拟）
    # 在实际使用中，替换为真实的API地址
    api_client = RemoteAPIClient(
        base_url=os.getenv("REMOTE_API_BASE_URL", "http://localhost:8080"),
        timeout=float(os.getenv("REMOTE_API_TIMEOUT", "30")),
    )

    # 3. 创建同步层
    sync_layer = SyncLayer(api_client, auto_sync=True)

    # 4. 创建 Agent 节点
    # 使用 ReAct Agent 进行代码生成
    coder_node = create_react_node(
        llm=llm,
        tools=[],  # 可以添加代码执行工具
        name="coder",
        max_steps=3,
    )

    # 创建 Supervisor（指定可用的 Agent）
    supervisor_node = create_supervisor_node(
        llm=llm,
        valid_agents={"coder"},
    )

    # 为需要同步的Agent添加同步包装
    # 注意：这里为了演示，实际API不可用时会报错
    # wrapped_coder = create_sync_wrapper(coder_node, sync_layer)

    # 5. 创建应用
    app = create_app_with_agents(
        supervisor_node=supervisor_node,
        agent_nodes={
            "coder": coder_node,
        },
        use_persistence=True,
    )

    # 6. 创建初始状态（包含运行时变量）
    initial_state = create_initial_state(
        session_id="sync-demo-001",
        user_id="demo-user",
        runtime_variables={
            "api_endpoint": "https://api.example.com",
            "timeout": 30,
            "retries": 3,
        }
    )

    from langchain_core.messages import HumanMessage
    initial_state["messages"] = [
        HumanMessage(content="请帮我生成一个调用API的代码示例")
    ]

    print("=" * 50)
    print("带API同步的多Agent系统示例")
    print("=" * 50)
    print("\n注意：此示例需要实际的API服务运行在localhost:8080")
    print("如果API不可用，同步会失败但Agent仍会执行\n")

    # 检查API健康状态
    try:
        is_healthy = await api_client.health_check()
        print(f"API健康状态: {'正常' if is_healthy else '异常'}")
    except Exception as e:
        print(f"API健康检查失败: {e}")

    # 运行（这里使用未包装的版本，因为API可能不可用）
    config = {"configurable": {"thread_id": "sync-demo-001"}}

    try:
        result = await app.ainvoke(initial_state, config)

        print("\n执行完成!")
        messages = result.get("messages", [])
        if messages:
            print("\n最终回复:")
            print(messages[-1].content)

    except Exception as e:
        print(f"\n执行出错: {e}")

    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())

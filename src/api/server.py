"""
FastAPI 服务器

提供 REST API 供 Web 前端调用。
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from src.agents import create_plan_node, create_react_node, create_supervisor_node
from src.core.graph import create_app_with_agents
from src.memory import SessionManager, create_checkpointer
from src.tools import ToolRegistry

# 导入 RimWorld 工具集以触发自动注册
from src.tools.rimworld import *  # noqa: F401, F403

# 全局实例
_agent_app = None
_session_manager: Optional[SessionManager] = None
_settings = None


def get_agent_app():
    """获取 Agent 应用实例"""
    return _agent_app


def get_session_manager() -> Optional[SessionManager]:
    """获取会话管理器"""
    return _session_manager


def get_app_settings():
    """获取应用配置"""
    return _settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _agent_app, _session_manager, _settings

    # 启动时初始化
    _settings = get_settings()
    llm = _settings.get_llm()
    checkpointer = create_checkpointer(
        backend=_settings.memory_backend,
        db_path=_settings.memory_db_path,
    )
    _session_manager = SessionManager(
        checkpointer=checkpointer,
        metadata_db_path="sessions.db",
    )

    # 获取已注册的工具
    registered_tools = ToolRegistry.get_all()
    print(f"已加载 {len(registered_tools)} 个工具: {ToolRegistry.list_tools()}")

    # 创建默认 Agent
    agents = {
        "planner": create_plan_node(
            llm=llm,
            name="planner",
            tools=registered_tools,
            max_steps=10,
        ),
        "executor": create_react_node(
            llm=llm,
            name="executor",
            tools=registered_tools,
            max_steps=5,
        ),
    }
    supervisor = create_supervisor_node(
        llm=llm,
        valid_agents=set(agents.keys()),
    )
    _agent_app = create_app_with_agents(
        supervisor_node=supervisor,
        agent_nodes=agents,
        use_persistence=True,
    )

    print("Auto-Agent API initialized")

    yield

    # 关闭时清理
    if _session_manager:
        _session_manager.close()
        print("Auto-Agent API shutdown")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Auto-Agent API",
        description="Multi-Agent System REST API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS 配置（允许前端跨域访问）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from .routes import router
    app.include_router(router, prefix="/api/v1")

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": "Auto-Agent API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    return app

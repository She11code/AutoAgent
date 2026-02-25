"""
API 路由定义

提供以下端点：
- POST /chat - 发送消息（同步）
- POST /chat/stream - 发送消息（流式 SSE）
- POST /sessions - 创建会话
- GET /sessions/{user_id} - 获取用户会话列表
- GET /sessions/{session_id}/history - 获取会话历史消息
- DELETE /sessions/{session_id} - 删除会话
- GET /health - 健康检查
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .server import get_agent_app, get_session_manager

router = APIRouter()


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field("default", description="会话ID")
    user_id: Optional[str] = Field("default", description="用户ID")


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str = Field(..., description="Agent 回复")
    session_id: str = Field(..., description="会话ID")


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    user_id: str
    title: Optional[str] = None
    created_at: float
    updated_at: float


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[SessionInfo]


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(None, description="会话标题")
    initial_message: Optional[str] = Field(None, description="初始消息")


class SessionCreateResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    title: str


class DeleteResponse(BaseModel):
    """删除响应"""
    status: str
    session_id: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str


class MessageItem(BaseModel):
    """消息项"""
    role: str = Field(..., description="消息角色: user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(None, description="时间戳")


class HistoryResponse(BaseModel):
    """历史消息响应"""
    session_id: str
    messages: List[MessageItem]


# ========== 流式事件类型 ==========

class StreamEventType:
    """流式事件类型常量"""
    NODE_START = "node_start"
    NODE_END = "node_end"
    SUPERVISOR_ROUTE = "supervisor_route"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    PLAN_STEP = "plan_step"
    MESSAGE = "message"
    DONE = "done"
    ERROR = "error"


# 常量配置
TOOL_OUTPUT_MAX_LENGTH = 500


# ========== 路由 ==========

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    发送消息

    发送用户消息到 Agent 系统并获取回复。
    如果 session_id 对应的会话不存在，会自动创建。
    """
    from langchain_core.messages import HumanMessage

    from src.core.state import create_initial_state

    print(f"[CHAT] 收到请求: session={req.session_id}, user={req.user_id}")
    print(f"[CHAT] 消息内容: {req.message[:100]}...")

    agent_app = get_agent_app()
    session_manager = get_session_manager()

    if agent_app is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    # 创建初始状态
    state = create_initial_state(
        session_id=req.session_id,
        user_id=req.user_id,
    )
    state["messages"] = [HumanMessage(content=req.message)]

    # 调用 Agent
    config = {"configurable": {"thread_id": req.session_id}}
    try:
        print("[CHAT] 开始调用 Agent...")
        result = await agent_app.ainvoke(state, config)
        print(f"[CHAT] Agent 返回结果类型: {type(result)}")
        print(f"[CHAT] 消息数量: {len(result.get('messages', []))}")
        for i, msg in enumerate(result.get("messages", [])):
            content_preview = msg.content[:100] if hasattr(msg, 'content') else 'N/A'
            print(f"[CHAT] 消息 {i}: type={type(msg).__name__}, content={content_preview}...")
    except Exception as e:
        print(f"[CHAT] Agent 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # 获取回复
    messages = result.get("messages", [])
    if messages:
        response_text = messages[-1].content
        print(f"[CHAT] 最终回复: {response_text[:100]}...")
    else:
        response_text = "No response"
        print("[CHAT] 没有收到任何消息")

    # 更新会话活跃时间
    if session_manager:
        try:
            await session_manager.touch_session(req.session_id)
        except Exception:
            pass  # 忽略更新错误

    return ChatResponse(response=response_text, session_id=req.session_id)


# ========== 流式聊天端点 ==========

def _serialize_for_json(obj: Any) -> Any:
    """序列化对象为 JSON 兼容格式"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    if hasattr(obj, 'content'):
        # LangChain 消息对象
        return {
            "type": getattr(obj, 'type', 'unknown'),
            "content": obj.content,
            "name": getattr(obj, 'name', None),
        }
    return str(obj)


def _extract_node_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    """从节点更新中提取可序列化的信息"""
    result = {}

    # 提取 task_context 关键信息
    if "task_context" in updates:
        tc = updates["task_context"]
        result["task_context"] = {}
        for key in ["react_status", "active_agent", "plan_status", "current_task",
                    "react_current_step", "react_max_steps", "react_final_answer"]:
            if key in tc:
                result["task_context"][key] = tc[key]

        # 提取最新的迭代信息
        iterations = tc.get("react_iterations", [])
        if iterations:
            last_iter = iterations[-1]
            result["task_context"]["last_iteration"] = {
                "thought": last_iter.get("thought"),
                "action": last_iter.get("action"),
                "action_input": last_iter.get("action_input"),
                "observation": last_iter.get("observation"),
            }

        # 提取计划步骤
        plan_steps = tc.get("plan_steps", [])
        if plan_steps:
            result["task_context"]["plan_steps"] = [
                {
                    "step_id": s.get("step_id"),
                    "description": s.get("description"),
                    "status": s.get("status"),
                }
                for s in plan_steps
            ]

    # 提取消息
    if "messages" in updates:
        result["messages"] = _serialize_for_json(updates["messages"])

    return result


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    流式聊天 - SSE 事件流

    返回 Server-Sent Events (SSE) 流，包含 Agent 执行过程中的各类事件：
    - node_start: 节点开始执行
    - node_end: 节点执行完成（包含状态更新）
    - thinking: 思考过程（ReAct Think 节点）
    - tool_call: 工具调用
    - plan_step: 计划步骤生成
    - message: AI 消息输出
    - done: 执行完成
    - error: 发生错误
    """
    from langchain_core.messages import HumanMessage

    from src.core.state import create_initial_state

    agent_app = get_agent_app()
    session_manager = get_session_manager()

    if agent_app is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    async def generate_events():
        """生成 SSE 事件流"""
        state = create_initial_state(
            session_id=req.session_id,
            user_id=req.user_id,
        )
        state["messages"] = [HumanMessage(content=req.message)]
        config = {"configurable": {"thread_id": req.session_id}}

        final_answer = ""
        accumulated_content = ""

        try:
            start_event = {'type': 'node_start', 'node': 'supervisor', 'agent': 'supervisor'}
            yield f"data: {json.dumps(start_event, ensure_ascii=False)}\n\n"

            # 使用 LangGraph 的流式 API
            # 当 stream_mode 是列表且 subgraphs=True 时，chunk 格式为: (namespace, mode_name, data)
            # - namespace: 命名空间元组（如 () 或 ('executor:uuid',)）
            # - mode_name: "updates" 或 "messages"
            # - data: 该模式对应的数据
            async for chunk in agent_app.astream(
                state,
                config,
                stream_mode=["updates", "messages"],
                subgraphs=True
            ):
                # chunk 格式: (namespace, mode_name, data)
                # 3 元素的 tuple
                if not isinstance(chunk, tuple) or len(chunk) != 3:
                    continue

                namespace, mode_name, data = chunk

                # === 处理 messages 模式 (LLM token 流式输出) ===
                if mode_name == "messages":
                    msg_chunk = None
                    if isinstance(data, tuple) and len(data) >= 1:
                        msg_chunk = data[0]
                    else:
                        msg_chunk = data

                    # 提取 content - 处理多种格式
                    content = None
                    if hasattr(msg_chunk, 'content'):
                        raw_content = msg_chunk.content
                        if isinstance(raw_content, str):
                            content = raw_content
                        elif isinstance(raw_content, list):
                            for item in raw_content:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    content = item.get('text', '')
                                    if content:
                                        break
                    elif isinstance(msg_chunk, str):
                        content = msg_chunk

                    if content and isinstance(content, str):
                        yield f"data: {json.dumps({
                            'type': 'message',
                            'content': content,
                            'done': False
                        }, ensure_ascii=False)}\n\n"
                    continue

                # === 处理 updates 模式 (节点更新) ===
                if mode_name == "updates":
                    if isinstance(data, tuple) and len(data) == 2:
                        namespace, updates = data
                    else:
                        namespace, updates = None, data

                    if not isinstance(updates, dict):
                        continue

                # 解析节点名称
                if isinstance(namespace, tuple):
                    if len(namespace) >= 2:
                        parent_graph, node_name = namespace[0], namespace[1]
                    elif len(namespace) == 1:
                        parent_graph, node_name = None, namespace[0]
                    else:
                        continue
                    agent_name = parent_graph if parent_graph else node_name
                else:
                    node_name = namespace
                    agent_name = node_name

                # 解析 updates 结构
                actual_updates = {}
                subgraph_node = None
                if isinstance(updates, dict):
                    if len(updates) == 1:
                        subgraph_node = list(updates.keys())[0]
                        actual_updates = updates[subgraph_node]
                        if not isinstance(actual_updates, dict):
                            actual_updates = {"value": actual_updates}
                    else:
                        actual_updates = updates

                # 提取可序列化的更新信息
                serialized_updates = _extract_node_updates(actual_updates)

                # 确定用于前端显示的节点类型
                # 如果是子图节点，使用 subgraph_node（如 think、act）
                # 如果是根图节点，使用 agent_name（如 supervisor、executor）
                # 注意：node_name 可能包含 UUID，所以优先使用 agent_name 或 subgraph_node
                if subgraph_node:
                    display_node = subgraph_node
                elif agent_name in ("supervisor", "executor"):
                    display_node = agent_name
                else:
                    # 如果 node_name 包含冒号（如 executor:UUID），提取冒号前的部分
                    display_node = node_name.split(":")[0] if ":" in node_name else node_name

                # 过滤掉对用户无意义的节点
                # init、finalize 是内部节点，不需要显示
                # executor 是包装节点，也不需要单独显示
                skip_nodes = {"init", "finalize", "executor"}
                if display_node in skip_nodes:
                    pass
                else:
                    display_agent = agent_name
                    if display_agent == "executor":
                        display_agent = "ReAct Agent"
                    elif display_agent == "planner":
                        display_agent = "Plan Agent"

                    yield f"data: {json.dumps({
                        'type': 'node_end',
                        'node': display_node,
                        'agent': display_agent,
                        'updates': serialized_updates
                    }, ensure_ascii=False)}\n\n"

                task_context = actual_updates.get("task_context", {})

                # === Supervisor 路由决策 ===
                if node_name == "supervisor" or agent_name == "supervisor":
                    active_agent = task_context.get("active_agent", "")
                    current_task = task_context.get("current_task", "")
                    if active_agent:
                        task_preview = current_task[:200] if current_task else ''
                        route_event = {
                            'type': 'supervisor_route',
                            'agent': active_agent,
                            'task': task_preview
                        }
                        yield f"data: {json.dumps(route_event, ensure_ascii=False)}\n\n"

                # === Think 节点 - 思考内容 ===
                # 使用 subgraph_node 判断（子图内的节点名）
                if subgraph_node == "think" and "react_iterations" in task_context:
                    iterations = task_context["react_iterations"]
                    if iterations:
                        last_iter = iterations[-1]
                        thought = last_iter.get("thought", "")
                        action = last_iter.get("action", "")
                        action_input = last_iter.get("action_input")

                        serialized_input = None
                        if action_input:
                            serialized_input = _serialize_for_json(action_input)
                        thinking_event = {
                            'type': 'thinking',
                            'thought': thought,
                            'action': action,
                            'action_input': serialized_input
                        }
                        yield f"data: {json.dumps(thinking_event, ensure_ascii=False)}\n\n"

                # === Act 节点 - 工具调用 ===
                if subgraph_node == "act" and "messages" in actual_updates:
                    for msg in actual_updates["messages"]:
                        if hasattr(msg, 'name') and hasattr(msg, 'tool_call_id'):
                                # ToolMessage
                                content_len = len(msg.content)
                                if content_len > TOOL_OUTPUT_MAX_LENGTH:
                                    tool_output = msg.content[:TOOL_OUTPUT_MAX_LENGTH]
                                else:
                                    tool_output = msg.content
                                tool_event = {
                                    'type': 'tool_call',
                                    'tool': msg.name,
                                    'tool_output': tool_output
                                }
                                yield f"data: {json.dumps(tool_event, ensure_ascii=False)}\n\n"

                # === Plan 节点 - 任务分解 ===
                if subgraph_node == "decompose" and "plan_steps" in task_context:
                    steps = task_context["plan_steps"]
                    yield f"data: {json.dumps({
                        'type': 'plan_step',
                        'steps': [
                            {'step_id': s.get('step_id'), 'description': s.get('description')}
                            for s in steps
                        ]
                    }, ensure_ascii=False)}\n\n"

                # === 消息输出 ===
                if "messages" in actual_updates:
                    for msg in actual_updates["messages"]:
                        # 检查是否是 AI 消息（兼容多种类型检查方式）
                        msg_type = getattr(msg, 'type', None)
                        msg_class_name = msg.__class__.__name__ if hasattr(msg, '__class__') else ''

                        is_ai_msg = (
                            msg_type == 'ai' or
                            msg_type == 'AIMessage' or
                            'AIMessage' in msg_class_name or
                            'AIMessageChunk' in msg_class_name
                        )

                        if is_ai_msg and hasattr(msg, 'content'):
                            content = msg.content
                            if content and isinstance(content, str):
                                accumulated_content += content
                                yield f"data: {json.dumps({
                                    'type': 'message',
                                    'content': content,
                                    'done': False
                                }, ensure_ascii=False)}\n\n"

                react_status = task_context.get("react_status", "")
                active_agent = task_context.get("active_agent", "")

                if react_status == "completed" or active_agent == "FINISH":
                    new_final_answer = task_context.get("react_final_answer", "")
                    if new_final_answer:
                        final_answer = new_final_answer
                    elif accumulated_content:
                        final_answer = accumulated_content

            if final_answer and not accumulated_content:
                yield f"data: {json.dumps({
                    'type': 'message',
                    'content': final_answer,
                    'done': False
                }, ensure_ascii=False)}\n\n"

            done_event = {
                'type': 'done',
                'final_answer': final_answer or accumulated_content or '任务完成'
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

            # 更新会话活跃时间
            if session_manager:
                try:
                    await session_manager.touch_session(req.session_id)
                except Exception:
                    pass

        except Exception as e:
            yield f"data: {json.dumps({
                'type': 'error',
                'message': str(e)
            }, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(req: SessionCreateRequest):
    """
    创建新会话

    创建一个新的会话并返回会话ID。
    """
    session_manager = get_session_manager()

    if session_manager is None:
        raise HTTPException(status_code=500, detail="Session manager not initialized")

    try:
        meta, _ = await session_manager.create_session_with_meta(
            user_id=req.user_id,
            title=req.title,
            initial_message=req.initial_message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

    return SessionCreateResponse(
        session_id=meta["session_id"],
        title=meta["title"],
    )


@router.get("/sessions/{user_id}", response_model=SessionListResponse)
async def list_sessions(user_id: str):
    """
    获取用户会话列表

    返回指定用户的所有会话，按更新时间倒序排列。
    """
    session_manager = get_session_manager()

    if session_manager is None:
        raise HTTPException(status_code=500, detail="Session manager not initialized")

    try:
        sessions = await session_manager.list_user_sessions(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

    return SessionListResponse(
        sessions=[SessionInfo(**s) for s in sessions]
    )


@router.delete("/sessions/{session_id}", response_model=DeleteResponse)
async def delete_session(session_id: str):
    """
    删除会话

    删除指定会话的元数据和状态数据。
    """
    agent_app = get_agent_app()
    session_manager = get_session_manager()

    if session_manager is None:
        raise HTTPException(status_code=500, detail="Session manager not initialized")

    try:
        success = await session_manager.delete_session(session_id, app=agent_app)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return DeleteResponse(status="deleted", session_id=session_id)


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    健康检查

    返回服务状态。
    """
    return HealthResponse(status="ok")


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    """
    获取会话历史消息

    从 checkpointer 中恢复会话的所有历史消息。
    """
    agent_app = get_agent_app()

    if agent_app is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    try:
        # 从 checkpointer 获取会话状态
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await agent_app.aget_state(config)

        messages = []
        if snapshot and snapshot.values:
            raw_messages = snapshot.values.get("messages", [])
            for msg in raw_messages:
                # 判断消息角色
                if hasattr(msg, 'type'):
                    role = "user" if msg.type == "human" else "assistant"
                else:
                    role = "assistant"  # 默认

                messages.append(MessageItem(
                    role=role,
                    content=msg.content if hasattr(msg, 'content') else str(msg),
                    timestamp=None,  # LangChain消息没有时间戳
                ))

        return HistoryResponse(session_id=session_id, messages=messages)
    except Exception as e:
        print(f"[HISTORY] 获取历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

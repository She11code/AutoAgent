"""
状态同步层

为Agent节点添加远程API状态同步逻辑。
"""

from datetime import datetime
from typing import Any, Callable, Dict

from ..core.state import MultiAgentState, RuntimeState
from .api_client import RemoteAPIClient


class SyncLayer:
    """
    状态同步层

    负责：
    - 在Agent执行前同步远程状态
    - 在Agent执行后推送更新
    """

    def __init__(
        self,
        api_client: RemoteAPIClient,
        auto_sync: bool = True,
    ):
        """
        初始化同步层

        Args:
            api_client: 远程API客户端
            auto_sync: 是否自动同步
        """
        self.api_client = api_client
        self.auto_sync = auto_sync

    async def sync_before(
        self,
        state: MultiAgentState
    ) -> Dict[str, Any]:
        """
        Agent执行前的状态同步

        Args:
            state: 当前状态

        Returns:
            更新的runtime状态
        """
        session_id = state.get("session_id", "default")

        try:
            # 从远程API获取最新状态
            remote_state = await self.api_client.fetch_state(session_id)

            return {
                "runtime": RuntimeState(
                    external_variables=remote_state.get("variables", {}),
                    last_sync_timestamp=datetime.now().timestamp(),
                    sync_status="synced",
                    last_api_response=remote_state,
                )
            }
        except Exception as e:
            return {
                "runtime": RuntimeState(
                    external_variables=state.get("runtime", {}).get("external_variables", {}),
                    last_sync_timestamp=datetime.now().timestamp(),
                    sync_status="error",
                    last_api_response={"error": str(e)},
                ),
                "task_context": {
                    "last_error": f"API同步失败: {str(e)}",
                }
            }

    async def sync_after(
        self,
        state: MultiAgentState,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Agent执行后的状态同步

        Args:
            state: 当前状态
            result: Agent执行结果

        Returns:
            同步后的状态更新
        """
        session_id = state.get("session_id", "default")

        # 准备需要同步回API的数据
        sync_data = {
            "variables": state.get("runtime", {}).get("external_variables", {}),
            "status": result.get("task_context", {}).get("task_status", "unknown"),
            "last_result": result,
        }

        try:
            await self.api_client.push_state(session_id, sync_data)

            return {
                "runtime": {
                    "sync_status": "synced",
                    "last_sync_timestamp": datetime.now().timestamp(),
                }
            }
        except Exception as e:
            return {
                "runtime": {
                    "sync_status": "error",
                },
                "task_context": {
                    "last_error": f"API推送失败: {str(e)}",
                }
            }


def create_sync_wrapper(
    agent_node: Callable,
    sync_layer: SyncLayer,
) -> Callable:
    """
    为Agent节点创建带同步逻辑的包装器

    Args:
        agent_node: 原始Agent节点函数
        sync_layer: 同步层实例

    Returns:
        包装后的节点函数

    Example:
        >>> sync_layer = SyncLayer(api_client)
        >>> wrapped_researcher = create_sync_wrapper(researcher_node, sync_layer)
    """
    async def wrapped_node(state: MultiAgentState) -> Dict[str, Any]:
        # 1. 调用前同步（获取最新状态）
        if sync_layer.auto_sync:
            sync_result = await sync_layer.sync_before(state)
            # 合并同步结果到状态
            state = {
                **state,
                "runtime": {
                    **state.get("runtime", {}),
                    **sync_result.get("runtime", {}),
                }
            }
            if "task_context" in sync_result:
                state["task_context"] = {
                    **state.get("task_context", {}),
                    **sync_result["task_context"],
                }

        # 2. 执行Agent逻辑
        result = await agent_node(state)

        # 3. 调用后同步（推送更新）
        if sync_layer.auto_sync:
            post_sync = await sync_layer.sync_after(state, result)
            # 合并后同步结果
            result = {
                **result,
                "runtime": {
                    **result.get("runtime", {}),
                    **post_sync.get("runtime", {}),
                }
            }
            if "task_context" in post_sync:
                result["task_context"] = {
                    **result.get("task_context", {}),
                    **post_sync["task_context"],
                }

        return result

    return wrapped_node

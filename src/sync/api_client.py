"""
远程API客户端

负责与远程API服务通信，实现状态同步。
"""

from typing import Any, Dict, Optional

import httpx


class RemoteAPIClient:
    """
    远程API客户端

    提供与远程服务通信的方法，用于获取和推送状态。
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        api_key: Optional[str] = None,
    ):
        """
        初始化API客户端

        Args:
            base_url: API基础URL
            timeout: 请求超时时间（秒）
            api_key: 可选的API密钥
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

        # 创建HTTP客户端
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_state(self, session_id: str) -> Dict[str, Any]:
        """
        从远程API获取状态

        Args:
            session_id: 会话ID

        Returns:
            远程状态数据

        Raises:
            httpx.HTTPError: 请求失败时抛出
        """
        url = f"{self.base_url}/state/{session_id}"
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    async def push_state(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将状态推送到远程API

        Args:
            session_id: 会话ID
            state: 要推送的状态数据

        Returns:
            API响应数据

        Raises:
            httpx.HTTPError: 请求失败时抛出
        """
        url = f"{self.base_url}/state/{session_id}"
        response = await self._client.post(url, json=state)
        response.raise_for_status()
        return response.json()

    async def update_variables(
        self,
        session_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新远程变量

        Args:
            session_id: 会话ID
            variables: 变量数据

        Returns:
            API响应数据
        """
        url = f"{self.base_url}/variables/{session_id}"
        response = await self._client.patch(url, json=variables)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """
        检查API健康状态

        Returns:
            True如果服务健康
        """
        try:
            url = f"{self.base_url}/health"
            response = await self._client.get(url)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self):
        """关闭客户端连接"""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

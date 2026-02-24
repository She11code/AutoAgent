"""
应用配置管理

使用Pydantic进行配置验证和管理。
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """
    应用配置

    从环境变量加载配置，支持.env文件。
    """

    # Anthropic Claude配置（主要）
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        alias="ANTHROPIC_MODEL"
    )

    # 可选：OpenAI兼容
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # 远程API配置
    remote_api_base_url: str = Field(default="http://localhost:8080", alias="REMOTE_API_BASE_URL")
    remote_api_timeout: float = Field(default=30.0, alias="REMOTE_API_TIMEOUT")
    remote_api_key: Optional[str] = Field(default=None, alias="REMOTE_API_KEY")

    # 记忆配置
    memory_backend: str = Field(default="memory", alias="MEMORY_BACKEND")
    memory_db_path: str = Field(default="./checkpoints.db", alias="MEMORY_DB_PATH")

    # Agent配置
    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")
    agent_timeout: float = Field(default=60.0, alias="AGENT_TIMEOUT")

    # 知识配置
    knowledge_max_size_kb: int = Field(default=10, alias="KNOWLEDGE_MAX_SIZE_KB")
    knowledge_dir: Optional[str] = Field(default=None, alias="KNOWLEDGE_DIR")

    # 调试
    debug: bool = Field(default=False, alias="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def get_llm(self):
        """
        获取配置的LLM实例（默认使用Anthropic Claude）

        Returns:
            配置好的ChatModel实例
        """
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=self.anthropic_model,
            api_key=self.anthropic_api_key,
            temperature=0,
        )

    def get_llm_openai(self):
        """
        获取OpenAI兼容的LLM实例（备用）

        Returns:
            配置好的ChatModel实例
        """
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.openai_model,
            base_url=self.openai_base_url,
            api_key=self.openai_api_key,
            temperature=0,
        )


@lru_cache
def get_settings() -> Settings:
    """
    获取配置单例

    Returns:
        Settings实例
    """
    return Settings()

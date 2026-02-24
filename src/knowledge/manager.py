"""
领域知识管理器

负责：
- 加载和管理领域知识
- 知识大小限制
- 构建带知识的System Prompt
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from ..core.state import DomainKnowledge, MultiAgentState


class KnowledgeManager:
    """
    领域知识管理器

    支持加载、合并和注入领域知识到System Prompt。
    知识大小限制为10KB。
    """

    MAX_SIZE_KB = 10
    MAX_SIZE_BYTES = MAX_SIZE_KB * 1024

    def __init__(self, knowledge_dir: Optional[str] = None):
        """
        初始化知识管理器

        Args:
            knowledge_dir: 知识文件目录路径
        """
        self.knowledge_dir = Path(knowledge_dir) if knowledge_dir else None
        self._cache: Dict[str, DomainKnowledge] = {}

    def load_knowledge(
        self,
        domain: str,
        content: str,
        tags: Optional[List[str]] = None
    ) -> DomainKnowledge:
        """
        加载领域知识

        自动裁剪到限制大小。

        Args:
            domain: 领域名称
            content: 知识内容
            tags: 知识标签

        Returns:
            DomainKnowledge对象
        """
        # 裁剪内容
        content = self._trim_content(content)

        knowledge = DomainKnowledge(
            content=content,
            version=self._generate_version(content),
            tags=tags or [domain],
        )

        self._cache[domain] = knowledge
        return knowledge

    def load_from_file(self, domain: str, file_path: str) -> DomainKnowledge:
        """
        从文件加载知识

        Args:
            domain: 领域名称
            file_path: 文件路径

        Returns:
            DomainKnowledge对象

        Raises:
            FileNotFoundError: 文件不存在
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"知识文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")
        return self.load_knowledge(domain, content)

    def get_knowledge(self, domain: str) -> Optional[DomainKnowledge]:
        """
        获取指定领域的知识

        Args:
            domain: 领域名称

        Returns:
            DomainKnowledge对象或None
        """
        return self._cache.get(domain)

    def merge_knowledge(
        self,
        domains: List[str],
        separator: str = "\n\n---\n\n"
    ) -> DomainKnowledge:
        """
        合并多个领域的知识

        Args:
            domains: 领域名称列表
            separator: 分隔符

        Returns:
            合并后的DomainKnowledge
        """
        contents = []
        all_tags = []

        for domain in domains:
            knowledge = self._cache.get(domain)
            if knowledge:
                contents.append(f"### {domain}\n{knowledge['content']}")
                all_tags.extend(knowledge['tags'])

        merged_content = separator.join(contents)

        # 确保不超过大小限制
        merged_content = self._trim_content(merged_content)

        return DomainKnowledge(
            content=merged_content,
            version="merged",
            tags=list(set(all_tags)),
        )

    def build_system_prompt(
        self,
        state: MultiAgentState,
        base_prompt: str,
        include_runtime: bool = True
    ) -> str:
        """
        构建包含领域知识和运行态的System Prompt

        Args:
            state: 当前状态
            base_prompt: 基础提示词
            include_runtime: 是否包含运行态变量

        Returns:
            完整的System Prompt
        """
        parts = [base_prompt]

        # 添加领域知识
        knowledge = state.get("domain_knowledge", {})
        content = knowledge.get("content", "")
        if content:
            tags = knowledge.get("tags", [])
            tags_str = ", ".join(tags) if tags else ""
            parts.append("\n\n## 领域知识")
            if tags_str:
                parts.append(f"标签: {tags_str}")
            parts.append(content)

        # 添加运行态变量
        if include_runtime:
            runtime = state.get("runtime", {})
            external_vars = runtime.get("external_variables", {})
            if external_vars:
                import json
                parts.append("\n\n## 当前运行环境状态")
                parts.append("外部程序变量（实时同步）:")
                json_str = json.dumps(external_vars, ensure_ascii=False, indent=2)
                parts.append(f"```json\n{json_str}\n```")

                sync_status = runtime.get("sync_status", "unknown")
                parts.append(f"同步状态: {sync_status}")

        return "\n".join(parts)

    def _trim_content(self, content: str) -> str:
        """
        裁剪内容到限制大小

        Args:
            content: 原始内容

        Returns:
            裁剪后的内容
        """
        content_bytes = content.encode("utf-8")

        if len(content_bytes) <= self.MAX_SIZE_BYTES:
            return content

        # 裁剪策略：保留开头和结尾
        half_size = self.MAX_SIZE_BYTES // 2

        head = content_bytes[:half_size].decode("utf-8", errors="ignore")
        tail = content_bytes[-half_size:].decode("utf-8", errors="ignore")

        return f"{head}\n\n... [内容已裁剪] ...\n\n{tail}"

    def _generate_version(self, content: str) -> str:
        """
        生成知识版本号

        Args:
            content: 知识内容

        Returns:
            版本号（MD5哈希前8位）
        """
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def list_domains(self) -> List[str]:
        """
        列出所有已加载的领域

        Returns:
            领域名称列表
        """
        return list(self._cache.keys())

    def clear_cache(self):
        """清空知识缓存"""
        self._cache.clear()

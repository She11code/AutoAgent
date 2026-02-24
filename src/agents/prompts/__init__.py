"""
提示词加载器

从 MD 文件加载静态提示词模板。
"""

from pathlib import Path

# 提示词目录
PROMPTS_DIR = Path(__file__).parent

# 缓存已加载的提示词
_prompt_cache: dict[str, str] = {}


def load_prompt(prompt_name: str, use_cache: bool = True) -> str:
    """
    从 MD 文件加载提示词模板。

    Args:
        prompt_name: 提示词名称，支持路径格式如 "react/think"
        use_cache: 是否使用缓存

    Returns:
        提示词模板字符串

    Raises:
        FileNotFoundError: 提示词文件不存在
    """
    if use_cache and prompt_name in _prompt_cache:
        return _prompt_cache[prompt_name]

    # 构建文件路径
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8").strip()

    if use_cache:
        _prompt_cache[prompt_name] = content

    return content


def clear_cache() -> None:
    """清除提示词缓存"""
    _prompt_cache.clear()

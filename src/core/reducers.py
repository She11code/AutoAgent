"""
自定义Reducer函数

LangGraph使用Reducer来决定如何合并状态更新。
默认行为是覆盖，但通过Annotated可以指定自定义合并策略。
"""

from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar('T')


def keep_latest_reducer(old: Optional[T], new: Optional[T]) -> Optional[T]:
    """
    只保留最新值的Reducer

    如果新值为None，则保留旧值。

    Args:
        old: 旧值
        new: 新值

    Returns:
        合并后的值

    Example:
        >>> keep_latest_reducer("old", "new")
        'new'
        >>> keep_latest_reducer("old", None)
        'old'
    """
    return new if new is not None else old


def merge_dict_reducer(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    字典合并Reducer（浅合并）

    将新字典的键值合并到旧字典中。

    Args:
        old: 旧字典
        new: 新字典

    Returns:
        合并后的字典

    Example:
        >>> merge_dict_reducer({"a": 1, "b": 2}, {"b": 3, "c": 4})
        {'a': 1, 'b': 3, 'c': 4}
    """
    result = old.copy()
    result.update(new)
    return result


def deep_merge_dict_reducer(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    字典深度合并Reducer

    递归合并嵌套字典。

    Args:
        old: 旧字典
        new: 新字典

    Returns:
        深度合并后的字典
    """
    result = old.copy()
    for key, value in new.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge_dict_reducer(result[key], value)
        else:
            result[key] = value
    return result


def max_int_reducer(old: int, new: int) -> int:
    """
    保留最大值的Reducer

    Args:
        old: 旧值
        new: 新值

    Returns:
        较大的值
    """
    return max(old, new)


def min_int_reducer(old: int, new: int) -> int:
    """
    保留最小值的Reducer

    Args:
        old: 旧值
        new: 新值

    Returns:
        较小的值
    """
    return min(old, new)


def dedupe_list_reducer(old: List[T], new: List[T]) -> List[T]:
    """
    去重列表Reducer

    追加新元素，但跳过已存在的元素。

    Args:
        old: 旧列表
        new: 新列表

    Returns:
        去重后的列表
    """
    if not old:
        return new

    # 检查元素是否可哈希
    try:
        seen = set(old)
        can_hash = True
    except TypeError:
        can_hash = False

    if not can_hash:
        # 元素不可哈希，直接追加
        return old + new

    result = list(old)
    for item in new:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def limit_list_reducer(max_size: int) -> Callable[[List[T], List[T]], List[T]]:
    """
    限制列表大小的Reducer工厂函数

    创建一个Reducer，追加新元素后只保留最后max_size个元素。

    Args:
        max_size: 最大列表大小

    Returns:
        Reducer函数

    Example:
        >>> limit_5 = limit_list_reducer(5)
        >>> limit_5([1, 2, 3], [4, 5, 6, 7])
        [3, 4, 5, 6, 7]
    """
    def reducer(old: List[T], new: List[T]) -> List[T]:
        combined = old + new
        if len(combined) > max_size:
            return combined[-max_size:]
        return combined
    return reducer


def sum_reducer(old: int | float, new: int | float) -> int | float:
    """
    求和Reducer

    Args:
        old: 旧值
        new: 新值

    Returns:
        两者之和
    """
    return old + new


# ========== 常用Reducer实例 ==========

# 限制消息历史为最近100条
limit_messages_100 = limit_list_reducer(100)

# 限制消息历史为最近50条
limit_messages_50 = limit_list_reducer(50)

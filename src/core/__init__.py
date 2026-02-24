"""Core module: State definitions, reducers, and graph builder."""

from .graph import (
    MultiAgentGraphBuilder,
    create_app_with_agents,
    create_route_supervisor,
    create_simple_app,
)
from .reducers import deep_merge_dict_reducer
from .state import (
    DomainKnowledge,
    MultiAgentState,
    RuntimeState,
    TaskContext,
)

__all__ = [
    "MultiAgentState",
    "RuntimeState",
    "DomainKnowledge",
    "TaskContext",
    "deep_merge_dict_reducer",
    "create_app_with_agents",
    "create_simple_app",
    "create_route_supervisor",
    "MultiAgentGraphBuilder",
]

import operator
from typing import Annotated, Literal, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class WorkflowState(TypedDict):
    messages: Annotated[list, add_messages]
    user_request: str
    task_plan: str
    task_items: list[str]
    current_task: str
    task_index: int
    task_batch_offset: int
    execution_results: Annotated[list[dict], operator.add]
    execution_result: str
    review_feedback: str
    review_status: Optional[Literal["approved", "rejected"]]
    executor_status: Optional[Literal["success", "failed"]]
    retry_count: int
    final_response: str
    next_node: str
    coordinator_mode: str
    clarify_question: str


def make_initial_state(user_request: str) -> dict:
    """Create a WorkflowState dict with sensible defaults."""
    return {
        "messages": [],
        "user_request": user_request,
        "task_plan": "",
        "task_items": [],
        "current_task": "",
        "task_index": 0,
        "task_batch_offset": 0,
        "execution_results": [],
        "execution_result": "",
        "review_feedback": "",
        "review_status": None,
        "executor_status": None,
        "retry_count": 0,
        "final_response": "",
        "next_node": "executor",
        "coordinator_mode": "plan",
        "clarify_question": "",
    }


def reset_execution_state() -> dict:
    """Return a state patch that resets execution-related fields for retry."""
    from langgraph.types import Overwrite

    return {
        "execution_results": Overwrite([]),
        "execution_result": "",
        "executor_status": None,
        "review_status": None,
        "task_batch_offset": 0,
    }

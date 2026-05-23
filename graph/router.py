from langgraph.graph import END
from langgraph.types import Send

from config import MAX_PARALLEL_TASKS, MAX_RETRIES
from graph.state import WorkflowState


def dispatch_executors(state: WorkflowState) -> list[Send]:
    task_items = state.get("task_items") or []
    if not task_items:
        task_plan = state.get("task_plan", "").strip()
        task_items = [task_plan] if task_plan else [""]
    task_items = task_items[:MAX_PARALLEL_TASKS]
    return [
        Send("executor", {"current_task": task, "task_index": index})
        for index, task in enumerate(task_items)
        if task.strip()
    ]


def route_after_coordinator(state: WorkflowState):
    next_node = state.get("next_node", "executor")
    if next_node == "end":
        return END
    if next_node == "clarify":
        return "coordinator_clarify"
    if next_node == "coordinator":
        return "coordinator"
    return dispatch_executors(state)


def route_after_coordinator_clarify(state: WorkflowState) -> str:
    return "coordinator"


def route_after_executor_aggregate(state: WorkflowState) -> str:
    if state.get("executor_status") == "failed":
        return "coordinator"
    return "reviewer"


def route_after_reviewer(state: WorkflowState):
    if (
        state.get("review_status") == "rejected"
        and state.get("retry_count", 0) < MAX_RETRIES
    ):
        return dispatch_executors(state)
    return "summarizer"

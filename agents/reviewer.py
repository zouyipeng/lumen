from agents.llm_display import call_agent
from agents.parsers import parse_reviewer_response
from config import get_llm
from graph.state import WorkflowState, reset_execution_state


def reviewer_node(state: WorkflowState) -> dict:
    user_content = (
        f"原始用户需求:\n{state['user_request']}\n\n"
        f"任务计划:\n{state.get('task_plan', '')}\n\n"
        f"执行结果:\n{state.get('execution_result', '')}\n\n"
        "请审核执行结果是否符合预期。"
    )

    response, parsed = call_agent("reviewer", "思考并审核执行结果", get_llm("reviewer"), user_content, parse_reviewer_response)

    result: dict = {
        "messages": [response],
        "review_status": parsed["status"],
        "review_feedback": parsed["feedback"],
    }

    if parsed["status"] == "rejected":
        result["retry_count"] = state.get("retry_count", 0) + 1
        result.update(reset_execution_state())

    return result

from agents.llm_display import call_agent
from agents.parsers import parse_summarizer_response
from config import get_llm
from graph.state import WorkflowState

PHASE_LABELS = {
    "summarize": "思考并汇总最终结果",
    "summarize_force": "思考并汇总（审核未通过）",
}


def summarizer_node(state: WorkflowState) -> dict:
    if state.get("review_status") == "approved":
        mode = "summarize"
        user_content = (
            f"原始用户需求:\n{state['user_request']}\n\n"
            f"任务计划:\n{state.get('task_plan', '')}\n\n"
            f"执行结果:\n{state.get('execution_result', '')}\n\n"
            f"审核摘要:\n{state.get('review_feedback', '')}\n\n"
            "请汇总以上信息，生成给用户的最终回复。使用 FINAL_RESPONSE: 标记。"
        )
    else:
        mode = "summarize_force"
        user_content = (
            f"原始用户需求:\n{state['user_request']}\n\n"
            f"执行结果:\n{state.get('execution_result', '')}\n\n"
            f"审核反馈（已重试 {state.get('retry_count', 0)} 次仍未通过）:\n"
            f"{state.get('review_feedback', '')}\n\n"
            "请汇总当前最佳结果并告知用户审核未完全通过的情况。使用 FINAL_RESPONSE: 标记。"
        )

    response, parsed = call_agent("summarizer", PHASE_LABELS.get(mode, PHASE_LABELS["summarize"]), get_llm("summarizer"), user_content, parse_summarizer_response)

    return {
        "messages": [response],
        "final_response": parsed["final_response"],
        "next_node": "end",
    }

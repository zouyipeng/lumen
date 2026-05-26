from agents.peon import run_peon
from agents.column_reviewer import run_reviewer
from graph.rn_state import RNWorkflowState


def column_processor_node(state: RNWorkflowState) -> dict:
    """Process a single RN column: peon executes → reviewer validates → retry if rejected.

    This node is the target of LangGraph Send fan-out. It internally loops
    peon → reviewer until approved or max retries exceeded.
    """
    column_config = state["column_config"]
    max_retries = state.get("rn_config", {}).get("workflow", {}).get("max_retries", 3)

    peon_result = None
    review_result = None
    review_feedback = ""

    for attempt in range(max_retries + 1):
        # Peon executes (with previous review feedback if retrying)
        peon_result = run_peon(state, column_config, review_feedback=review_feedback)

        # Reviewer validates
        review_result = run_reviewer(column_config, peon_result)

        if review_result["status"] == "approved":
            return {
                "column_results": [{
                    "column_id": column_config["id"],
                    "column_name": column_config["name"],
                    "peon_output": peon_result["output"],
                    "structured_result": peon_result["structured"],
                    "review_status": "approved",
                    "review_feedback": review_result["feedback"],
                    "retry_count": attempt,
                }],
            }

        # Store feedback for next peon attempt
        review_feedback = review_result.get("feedback", "")

    # Max retries exceeded — return last result anyway
    return {
        "column_results": [{
            "column_id": column_config["id"],
            "column_name": column_config["name"],
            "peon_output": peon_result["output"] if peon_result else "",
            "structured_result": peon_result["structured"] if peon_result else {},
            "review_status": "max_retries_exceeded",
            "review_feedback": review_result["feedback"] if review_result else "",
            "retry_count": max_retries,
        }],
    }

import re

# Structured output markers used in agent prompts and parsers.
# Keep in sync with prompts/*.md
MARKER_TASK_PLAN = "TASK_PLAN"
MARKER_USER_QUESTION = "USER_QUESTION"
MARKER_FINAL_RESPONSE = "FINAL_RESPONSE"
MARKER_THINKING = "THINKING"
MARKER_STATUS = "STATUS"
MARKER_RESULT = "RESULT"
MARKER_ERROR = "ERROR"
MARKER_REVIEW = "REVIEW"
MARKER_SUMMARY = "SUMMARY"
MARKER_FEEDBACK = "FEEDBACK"


def extract_section(text: str, marker: str) -> str:
    pattern = rf"{re.escape(marker)}:\s*\n?(.*?)(?:\n[A-Z_]+:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_task_items(task_plan: str) -> list[str]:
    """Split a task plan into sub-tasks by numbered or bulleted list items."""
    if not task_plan or not task_plan.strip():
        return []

    items: list[str] = []
    for line in task_plan.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:\d+\.|[-*])\s+(.+)$", stripped)
        if match:
            items.append(match.group(1).strip())

    if items:
        return items
    return [task_plan.strip()]


def parse_coordinator_response(text: str) -> dict:
    if f"{MARKER_FINAL_RESPONSE}:" in text:
        return {
            "mode": "summarize",
            "final_response": extract_section(text, MARKER_FINAL_RESPONSE),
        }
    if f"{MARKER_USER_QUESTION}:" in text:
        return {
            "mode": "ask_user",
            "question": extract_section(text, MARKER_USER_QUESTION),
        }
    return {
        "mode": "plan",
        "task_plan": extract_section(text, MARKER_TASK_PLAN) or text.strip(),
    }


def parse_executor_response(text: str) -> dict:
    if f"{MARKER_STATUS}: failed" in text:
        return {
            "status": "failed",
            "content": extract_section(text, MARKER_ERROR) or text.strip(),
        }
    return {
        "status": "success",
        "content": extract_section(text, MARKER_RESULT) or text.strip(),
    }


def parse_reviewer_response(text: str) -> dict:
    if f"{MARKER_REVIEW}: rejected" in text:
        return {
            "status": "rejected",
            "feedback": extract_section(text, MARKER_FEEDBACK) or text.strip(),
        }
    return {
        "status": "approved",
        "feedback": extract_section(text, MARKER_SUMMARY) or text.strip(),
    }


def parse_summarizer_response(text: str) -> dict:
    """Parse summarizer output, which only uses FINAL_RESPONSE marker."""
    return {
        "final_response": extract_section(text, MARKER_FINAL_RESPONSE) or text.strip(),
    }

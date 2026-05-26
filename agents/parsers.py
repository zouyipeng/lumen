import re

# Structured output markers used in RN agent prompts and parsers.
# Keep in sync with prompts/rn/*.md
MARKER_RESULT = "RESULT"
MARKER_REVIEW = "REVIEW"
MARKER_SUMMARY = "SUMMARY"
MARKER_FEEDBACK = "FEEDBACK"


def extract_section(text: str, marker: str) -> str:
    pattern = rf"{re.escape(marker)}:\s*\n?(.*?)(?:\n[A-Z_]+:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


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

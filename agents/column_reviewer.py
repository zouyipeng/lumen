from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm_display import call_llm_with_display
from agents.parsers import parse_reviewer_response
from config import get_llm_with_config, load_prompt_from_file


def run_reviewer(column_config: dict, peon_result: dict) -> dict:
    """Execute a reviewer agent for a specific RN column."""
    reviewer_config = column_config["reviewer"]
    llm = get_llm_with_config(reviewer_config)
    system_prompt = load_prompt_from_file(reviewer_config["prompt_file"])

    user_content = (
        f"列: {column_config['name']}\n"
        f"列描述: {column_config.get('description', '')}\n\n"
        f"Peon 输出:\n{peon_result['output']}\n\n"
        "请审核 Peon 的输出是否准确、完整。"
    )

    response = call_llm_with_display(
        f"{column_config['name']} Reviewer", "审核中", llm,
        [SystemMessage(content=system_prompt), HumanMessage(content=user_content)],
    )

    parsed = parse_reviewer_response(response.content)
    return {"status": parsed["status"], "feedback": parsed["feedback"]}

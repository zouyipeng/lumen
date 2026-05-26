import json

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm_display import call_llm_with_display
from agents.parsers import extract_section, MARKER_RESULT
from config import get_llm_with_config, load_prompt_from_file
from graph.rn_state import RNWorkflowState


def _build_peon_user_content(state: RNWorkflowState, column_config: dict) -> str:
    """Build user content for peon based on column type and available data."""
    commits = state.get("commits", [])
    mr_list = state.get("mr_list", [])
    rn_config = state.get("rn_config", {})

    parts = [
        f"版本周期: {state.get('cycle_start_date', '')} ~ {state.get('cycle_end_date', '')}",
        f"任务: {column_config.get('description', column_config.get('name', ''))}",
        "",
    ]

    # Always include commit info
    if commits:
        parts.append("## 提交记录")
        for commit in commits:
            parts.append(
                f"- [{commit.get('short_hash', '')}] {commit.get('message', '')} "
                f"(作者: {commit.get('author', '')}, 日期: {commit.get('date', '')})"
            )
        parts.append("")

    # Include MR info if available
    if mr_list:
        parts.append("## MR 列表")
        for mr in mr_list:
            parts.append(
                f"- MR#{mr.get('id', '')}: {mr.get('title', '')} "
                f"(作者: {mr.get('author', '')}, 分支: {mr.get('source_branch', '')} → {mr.get('target_branch', '')})"
            )
            if mr.get("description"):
                parts.append(f"  描述: {mr['description'][:500]}")
        parts.append("")

    # For open_source_sync, include repo comparison info
    if column_config.get("id") == "open_source_sync":
        repo_config = rn_config.get("repo", {})
        open_source_path = repo_config.get("open_source_repo_path", "")
        if open_source_path:
            parts.append(f"开源仓库路径: {open_source_path}")
            parts.append("请根据提交记录判断哪些提交需要同步到开源仓库。")

    return "\n".join(parts)


def _parse_peon_response(text: str, column_config: dict) -> dict:
    """Parse peon response into structured result."""
    # Extract the RESULT section
    result_text = extract_section(text, MARKER_RESULT)

    if not result_text:
        # Fallback: use the full text after STATUS line
        result_text = text.strip()

    # Try to parse as JSON for structured data
    try:
        structured = json.loads(result_text)
    except json.JSONDecodeError:
        # If not JSON, store as plain text mapped to "all" key
        structured = {"all": result_text}

    return structured


def run_peon(state: RNWorkflowState, column_config: dict, *, review_feedback: str = "") -> dict:
    """Execute a peon agent for a specific RN column."""
    peon_config = column_config["peon"]
    llm = get_llm_with_config(peon_config)
    system_prompt = load_prompt_from_file(peon_config["prompt_file"])

    user_content = _build_peon_user_content(state, column_config)

    # Include reviewer feedback from previous attempt if retrying
    if review_feedback:
        user_content += f"\n\n## 上次审核反馈\n{review_feedback}\n\n请根据反馈修正你的输出。"

    response = call_llm_with_display(
        column_config["name"], "处理中", llm,
        [SystemMessage(content=system_prompt), HumanMessage(content=user_content)],
    )

    structured = _parse_peon_response(response.content, column_config)
    return {"output": response.content, "structured": structured}
